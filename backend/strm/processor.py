import os
import shutil
import asyncio
import urllib.parse
import httpx
from typing import Dict, Any, List
from logger import log_audit
from .constants import VIDEO_EXTENSIONS, META_EXTENSIONS

import logging

logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

class StrmProcessor:
    @staticmethod
    def calculate_strm_content(source_root: str, file_abs_path: str, config: Dict[str, Any]) -> str:
        """计算 STRM 内部 URL (纯计算逻辑，不涉及 IO)"""
        prefix = config.get("content_prefix", "")
        suffix = config.get("content_suffix", "")
        do_url_encode = config.get("url_encode", False)
        
        try:
            relative_path = os.path.relpath(file_abs_path, source_root)
        except ValueError:
            relative_path = os.path.basename(file_abs_path)

        path_part = relative_path.replace("\\", "/")
        
        if do_url_encode:
            path_part = urllib.parse.quote(path_part)
            prefix = urllib.parse.quote(prefix, safe=":/?#[]@!$&'()*+,;=")

        return f"{prefix}{path_part}{suffix}"

    @staticmethod
    async def process_single_file(file_path: str, task_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理单个文件。所有 IO 操作均使用 asyncio.to_thread 以免阻塞主线程。
        """
        source_root = task_config.get("source_dir") or task_config.get("source_path")
        target_root = task_config.get("target_dir") or task_config.get("target_path")
        copy_meta = task_config.get("copy_meta", False)

        # CD2 云路径源适配：webhook/联动推送的文件是挂载视图路径（如 /medata/CloudDrive/115open/...），
        # 而任务的源目录可能是云路径（如 /115open/cscd2md）。此时把源根换算到挂载视图坐标系，
        # 否则 relpath 会产生 ../.. 导致 STRM 写回源目录。
        try:
            _norm_file = os.path.normpath(file_path)
            if source_root and not _norm_file.startswith(os.path.normpath(source_root)):
                mapping_root = (task_config.get("cd2_mapping_path") or "").strip()
                if not mapping_root:
                    from clients.manager import ClientManager
                    _cd2_conf = next((c for c in ClientManager.get_all_clients() if c.get('type') == 'cd2'), None)
                    mapping_root = (_cd2_conf or {}).get('mount_path', '')
                if mapping_root:
                    _local_root = os.path.normpath(mapping_root.rstrip('/') + '/' + os.path.normpath(source_root).lstrip('/'))
                    if _norm_file.startswith(_local_root):
                        source_root = _local_root
        except Exception:
            pass
        
        _overwrite_all = task_config.get("overwrite", False)
        overwrite_strm = task_config.get("overwrite_strm", _overwrite_all)
        overwrite_meta = task_config.get("overwrite_meta", _overwrite_all)

        if not source_root or not target_root:
            return {"status": "error", "message": "Config missing source or target"}
        
        ext = os.path.splitext(file_path)[1].lower()
        
        # 1. 计算相对路径和目标目录 (IO 预检)
        try:
            rel_path = await asyncio.to_thread(os.path.relpath, file_path, source_root)
        except ValueError:
            return {"status": "error", "message": "File not in source root"}
        # 防御：文件不在源目录内时 relpath 会产生 ../ 逃逸，禁止写出到目标目录之外
        if rel_path == os.pardir or rel_path.startswith(os.pardir + os.sep):
            return {"status": "error", "message": "文件不在源目录范围内，请检查源目录或路径换算配置"}
            
        target_subdir = os.path.join(target_root, os.path.dirname(rel_path))
        
        # 异步创建目录
        if not await asyncio.to_thread(os.path.exists, target_subdir):
            await asyncio.to_thread(os.makedirs, target_subdir, exist_ok=True)

        # 2. 准备后缀列表
        video_exts = set(task_config.get("target_extensions") or VIDEO_EXTENSIONS)
        meta_exts = set(task_config.get("meta_extensions") or META_EXTENSIONS)

        # A. 视频转 STRM 逻辑
        if ext in video_exts:
            strm_filename = os.path.splitext(os.path.basename(file_path))[0] + ".strm"
            abs_target_strm = os.path.join(target_subdir, strm_filename)
            
            # 仅判断路径是否存在，不再管时间、大小或其他属性
            if await asyncio.to_thread(os.path.exists, abs_target_strm) and not overwrite_strm:
                return {"status": "skipped", "message": "Exists", "rel_path": os.path.join(os.path.dirname(rel_path), strm_filename)}
                
            content = StrmProcessor.calculate_strm_content(source_root, file_path, task_config)
            try:
                def _write():
                    with open(abs_target_strm, 'w', encoding='utf-8') as f:
                        f.write(content)
                await asyncio.to_thread(_write)
                logger.debug(f"[STRM] 生成成功: {strm_filename}")
                return {"status": "success", "message": "Created STRM", "rel_path": os.path.join(os.path.dirname(rel_path), strm_filename)}
            except Exception as e:
                logger.error(f"[STRM] 生成失败: {strm_filename} - {e}")
                return {"status": "error", "message": str(e)}

        # B. 元数据复制逻辑
        elif copy_meta and ext in meta_exts:
            target_file = os.path.join(target_subdir, os.path.basename(file_path))
            # 仅判断路径是否存在
            if await asyncio.to_thread(os.path.exists, target_file) and not overwrite_meta:
                return {"status": "skipped", "message": "MetaExists", "rel_path": rel_path}

            # CD2 gRPC 云源：元数据文件在云盘上，通过 CD2 下载接口流式取回（不依赖挂载）
            if task_config.get("sync_mode") == "cd2_api":
                try:
                    from config_manager import ConfigManager as _CM
                    from clients.manager import ClientManager as _CMgr
                    _cfg = _CM.get_config()
                    _cd2_conf = next((c for c in _cfg.get("download_clients", []) if c.get("type") == "cd2"), None)
                    if not _cd2_conf:
                        return {"status": "error", "message": "未找到已配置的 CD2 客户端"}
                    _cd2_client = _CMgr.get_client(_cd2_conf.get("id"))
                    if not _cd2_client:
                        return {"status": "error", "message": "CD2 客户端初始化失败"}

                    resp, _size = await asyncio.to_thread(_cd2_client._file_browser.open_download_stream, file_path)
                    try:
                        def _download_meta():
                            with open(target_file, 'wb') as f:
                                for chunk in resp.iter_content(chunk_size=256 * 1024):
                                    if chunk:
                                        f.write(chunk)
                        await asyncio.to_thread(_download_meta)
                    finally:
                        await asyncio.to_thread(resp.close)

                    if await asyncio.to_thread(os.path.getsize, target_file) <= 0:
                        await asyncio.to_thread(os.remove, target_file)
                        return {"status": "error", "message": "元数据下载内容为空"}

                    logger.debug(f"[STRM] CD2 下载元数据: {os.path.basename(file_path)}")
                    return {"status": "success", "message": "Copied Meta (CD2 Downloaded)", "rel_path": rel_path}
                except Exception as ce:
                    logger.error(f"[STRM] CD2 下载元数据失败: {os.path.basename(file_path)} - {ce}")
                    return {"status": "error", "message": f"CD2 元数据下载失败: {ce}"}

            try:
                # 使用 copyfile 仅复制内容
                await asyncio.to_thread(shutil.copyfile, file_path, target_file)
                logger.debug(f"[STRM] 本地复制元数据: {os.path.basename(file_path)}")
                return {"status": "success", "message": "Copied Meta (Local)", "rel_path": rel_path}
            except Exception as e:
                 # 尝试 WebDAV 下载回退模式
                 download_success = False
                 dl_error = None
                 
                 if task_config.get("content_prefix"):
                     try:
                        # 专门为 WebDAV 下载构建 URL，确保正确编码
                        # 1. 获取相对路径
                        try:
                            rel_p = os.path.relpath(file_path, source_root)
                        except:
                            rel_p = os.path.basename(file_path)
                        
                        # 2. 规范化为 Web 路径 (即 / 分隔)
                        rel_p = rel_p.replace("\\", "/")
                        
                        # 3. 根据配置决定是否进行 URL 编码
                        do_url_encode = task_config.get("url_encode", False)
                        if do_url_encode:
                            rel_p_encoded = urllib.parse.quote(rel_p, safe="/")
                        else:
                            rel_p_encoded = rel_p # 保持原样 (UTF-8)

                        # 4. 尝试构建 CD2 专用下载链接
                        # 逻辑 A: 解析 prefix (如果 prefix 是标准 URL)
                        prefix = task_config.get("content_prefix", "")
                        cd2_download_url = None
                        
                        try:
                            parsed = urllib.parse.urlparse(prefix)
                            if parsed.scheme and parsed.netloc:
                                base_url = f"{parsed.scheme}://{parsed.netloc}"
                                cd2_download_url = f"{base_url}/static/http/{parsed.netloc}/False//{rel_p_encoded}"
                        except:
                            pass

                        # 逻辑 B: 智能路径探测 (从 CD2 客户端配置获取挂载点)
                        if not cd2_download_url:
                            try:
                                # 动态导入避免循环依赖
                                from clients.manager import ClientManager
                                all_clients = ClientManager.get_all_clients()
                                # 找到第一个 CD2 客户端
                                cd2_conf = next((c for c in all_clients if c.get('type') == 'cd2'), None)

                                if cd2_conf:
                                    mount_path = cd2_conf.get('mount_path', '').rstrip('/')
                                    cd2_host = cd2_conf.get('url', '').rstrip('/')
                                    
                                    if mount_path and file_path.startswith(mount_path):
                                        # 提取网盘路径并确保开头只有一个 /
                                        cloud_path = file_path[len(mount_path):].replace("\\", "/")
                                        if not cloud_path.startswith('/'):
                                            cloud_path = '/' + cloud_path
                                            
                                        # 提取 host 和 port (用于构造 static URL)
                                        parsed_host = urllib.parse.urlparse(cd2_host)
                                        netloc = parsed_host.netloc 
                                        
                                        # 编码路径
                                        cloud_path_encoded = urllib.parse.quote(cloud_path, safe="/")
                                        
                                        # 构造 URL (恢复双斜杠逻辑: False//)
                                        cd2_download_url = f"{cd2_host}/static/http/{netloc}/False/{cloud_path_encoded}"
                                        log_audit("STRM", "调试", f"匹配到 CD2 挂载点: {mount_path} -> {cd2_download_url}")
                                    else:
                                        # 备用：如果文件不在配置的 mount_path 下，尝试 CloudDrive 关键字回退
                                        marker = "/CloudDrive"
                                        idx = file_path.find(marker)
                                        if idx != -1:
                                            cloud_path = file_path[idx + len(marker):]
                                            parsed_host = urllib.parse.urlparse(cd2_host)
                                            netloc = parsed_host.netloc
                                            cloud_path_encoded = urllib.parse.quote(cloud_path, safe="/")
                                            cd2_download_url = f"{cd2_host}/static/http/{netloc}/False/{cloud_path_encoded}"
                            except Exception as client_e:
                                log_audit("STRM", "警告", f"获取 CD2 配置失败: {client_e}")

                        # 如果成功构造了 CD2 URL，优先使用它
                        if cd2_download_url: 
                             url = cd2_download_url
                        else:
                            # 回退逻辑
                            if prefix.endswith('/') and rel_p_encoded.startswith('/'):
                                url = f"{prefix}{rel_p_encoded[1:]}"
                            elif not prefix.endswith('/') and not rel_p_encoded.startswith('/'):
                                url = f"{prefix}/{rel_p_encoded}"
                            else:
                                url = f"{prefix}{rel_p_encoded}"
                            
                        # 如果前缀本身包含了部分未编码的中文路径（不常见），可能也需要处理，
                        # 但通常前缀是 http://ip:port/dav/ 这种。
                        
                        log_audit("STRM", "下载", f"本地复制失败, 转为WebDAV下载. URL: {url}")
                        
                        # 增加请求头伪装
                        headers = {
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                            "Accept": "*/*"
                        }

                        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True, headers=headers) as client:
                            async with client.stream('GET', url) as resp:
                                resp.raise_for_status()
                                with open(target_file, 'wb') as f:
                                    async for chunk in resp.aiter_bytes():
                                        f.write(chunk)
                        
                        # 验证文件大小
                        if os.path.exists(target_file) and os.path.getsize(target_file) == 0:
                            try:
                                os.remove(target_file)
                            except: pass
                            raise Exception("Downloaded file is empty (0KB)")
                        
                        download_success = True
                        logger.debug(f"[STRM] WebDAV下载元数据: {os.path.basename(file_path)}")
                        return {"status": "success", "message": "Copied Meta (WebDAV Downloaded)", "rel_path": rel_path}
                     except Exception as de:
                        dl_error = de

                 err_msg = f"元数据同步失败: {os.path.basename(file_path)} (复制错误: {e})"
                 if dl_error:
                     err_msg += f" (下载错误: {dl_error})"
                 
                 log_audit("STRM", "错误", err_msg, level="ERROR", details=str(e))
                 return {"status": "error", "message": str(e)}
                 
        return {"status": "ignored", "message": "Not target"}
                 
        return {"status": "ignored", "message": "Not target"}

    @staticmethod
    async def remove_empty_dirs_async(path: str):
        """异步化的空目录清理"""
        if not await asyncio.to_thread(os.path.isdir, path): return
        
        def _cleanup():
            for root, dirs, files in os.walk(path, topdown=False):
                for d in dirs:
                    full_path = os.path.join(root, d)
                    try:
                        if not os.listdir(full_path):
                            os.rmdir(full_path)
                    except: pass
        await asyncio.to_thread(_cleanup)
