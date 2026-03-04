import os
import shutil
import asyncio
import urllib.parse
import httpx
from typing import Dict, Any, List
from logger import log_audit
from .constants import VIDEO_EXTENSIONS, META_EXTENSIONS

import logging

# Silence httpx info logs
logging.getLogger("httpx").setLevel(logging.WARNING)

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
                log_audit("STRM", "生成", f"生成成功: {strm_filename}")
                return {"status": "success", "message": "Created STRM", "rel_path": os.path.join(os.path.dirname(rel_path), strm_filename)}
            except Exception as e:
                log_audit("STRM", "错误", f"生成失败: {strm_filename}", level="ERROR", details=str(e))
                return {"status": "error", "message": str(e)}

        # B. 元数据复制逻辑
        elif copy_meta and ext in meta_exts:
            target_file = os.path.join(target_subdir, os.path.basename(file_path))
            # 仅判断路径是否存在
            if await asyncio.to_thread(os.path.exists, target_file) and not overwrite_meta:
                return {"status": "skipped", "message": "MetaExists", "rel_path": rel_path}

            try:
                # 使用 copyfile 仅复制内容
                await asyncio.to_thread(shutil.copyfile, file_path, target_file)
                log_audit("STRM", "同步", f"本地复制元数据成功: {os.path.basename(file_path)}")
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
                        log_audit("STRM", "同步", f"WebDAV下载成功: {os.path.basename(file_path)}")
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
