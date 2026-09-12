import os
import shutil
import asyncio
import logging
from typing import List, Tuple, Dict, Any
from clients.manager import ClientManager

logger = logging.getLogger(__name__)

class FileExecutor:
    @staticmethod
    async def _ensure_cd2_dir(client, local_path: str, dir_cache: set):
        """
        Recursively ensure directory exists using CD2 API (Async Wrapper).
        """
        if not local_path or local_path == "/" or (dir_cache is not None and local_path in dir_cache):
            return True
            
        # Run synchronous os.path.exists in thread
        exists = await asyncio.to_thread(os.path.exists, local_path)
        if exists:
            if dir_cache is not None: dir_cache.add(local_path)
            return True

        # Recursive parent check
        parent = os.path.dirname(local_path)
        await FileExecutor._ensure_cd2_dir(client, parent, dir_cache)
        
        # Create this level
        cd2_parent = client._to_cd2_path(parent)
        dir_name = os.path.basename(local_path)
        
        logger.debug(f"正在云端创建目录: {dir_name}")
        
        # client.create_directory is a gRPC call, run in thread
        success, err = await asyncio.to_thread(client.create_directory, cd2_parent, dir_name)
        
        if success:
            logger.debug(f"  ✅ 目录创建成功: {dir_name}")
            if dir_cache is not None: dir_cache.add(local_path)
            return True
        elif "already exists" in err.lower() or "conflict" in err.lower():
            logger.debug(f"  ℹ️ 目录已存在: {dir_name}")
            if dir_cache is not None: dir_cache.add(local_path)
            return True
        else:
            logger.error(f"  ❌ 创建目录失败: {dir_name} -> {err}")
            return False

    @staticmethod
    async def _execute_cd2_batch(client, items: List[Tuple[str, str]], action: str) -> str:
        """
        Special optimized batch handler for CD2 (Async).
        """
        dest_dir = os.path.dirname(items[0][1])
        
        # 1. Ensure Directory
        await FileExecutor._ensure_cd2_dir(client, dest_dir, None)

        action_label = "移动" if action == "cd2_move" else "复制"
        file_names = [os.path.basename(src) for src, _ in items]
        files_desc = ", ".join(file_names)

        if action == "cd2_move":
            # --- Move Logic: Rename at Source -> Batch Move ---
            renamed_src_paths = []
            for src, dst in items:
                src_name = os.path.basename(src)
                dst_name = os.path.basename(dst)
                current_src = src
                if src_name != dst_name:
                    logger.debug(f"正在原位重命名 (移动前): {src_name} -> {dst_name}")
                    # API Call in thread
                    success, err = await asyncio.to_thread(client.rename_file, client._to_cd2_path(src), dst_name)
                    if not success:
                        logger.error(f"{src_name} -> {err}")
                        return f"rename_failed: {err}"
                    logger.debug(f"  ✅ 原位改名成功: {dst_name}")
                    current_src = os.path.join(os.path.dirname(src), dst_name)
                renamed_src_paths.append(current_src)
            
            # API Batch Move in thread
            try:
                success, err = await asyncio.to_thread(client.move_files, renamed_src_paths, dest_dir)
                if not success:
                    if "already exists" in str(err).lower() or "ALREADY_EXISTS" in str(err):
                        logger.warning(f"目标已存在，跳过批量移动: {files_desc}")
                        return "skipped"
                    logger.error(f"CD2批量移动失败: {len(items)} 个项目 -> {err}")
                    return f"batch_action_failed: {err}"
            except Exception as e:
                if "already exists" in str(e).lower() or "ALREADY_EXISTS" in str(e):
                    logger.warning(f"目标已存在，跳过批量移动: {files_desc}")
                    return "skipped"
                raise e
            
            logger.debug(f"CD2批量移动成功: 共 {len(items)} 个项目 (API 校验通过 ✅)")
            for fname in file_names:
                logger.debug(f"  [已移动] {fname}")
            return "success"

        else: # cd2_copy
            # --- Copy Logic: Batch Copy -> Rename at Destination ---
            src_paths = [src for src, _ in items]
            # API Batch Copy in thread
            try:
                success, err = await asyncio.to_thread(client.copy_files, src_paths, dest_dir)
                if not success:
                    if "already exists" in str(err).lower() or "ALREADY_EXISTS" in str(err):
                        logger.warning(f"目标已存在，跳过批量复制: {files_desc}")
                        return "skipped"
                    logger.error(f"CD2批量复制失败: {len(items)} 个项目 -> {err}")
                    return f"batch_action_failed: {err}"
            except Exception as e:
                if "already exists" in str(e).lower() or "ALREADY_EXISTS" in str(e):
                    logger.warning(f"目标已存在，跳过批量复制: {files_desc}")
                    return "skipped"
                raise e
            
            logger.debug(f"CD2批量复制成功: 共 {len(items)} 个项目 (API 校验通过 ✅)")
            for fname in file_names:
                logger.debug(f"  [已复制] {fname}")

            # 2. Rename at destination
            if any(os.path.basename(src) != os.path.basename(dst) for src, dst in items):
                logger.debug(f"检测到命名变化，开始目标位重命名流程...")
                for i, (src, dst) in enumerate(items):
                    src_name = os.path.basename(src)
                    dst_name = os.path.basename(dst)
                    if src_name != dst_name:
                        path_at_dest = os.path.join(dest_dir, src_name)
                        logger.debug(f"  正在改名: {src_name} -> {dst_name}")
                        success, err = await asyncio.to_thread(client.rename_file, client._to_cd2_path(path_at_dest), dst_name)
                        if not success:
                            logger.error(f"    ❌ 改名失败: {src_name} -> {err}")
                            if i == 0: return f"rename_failed: {err}"
                        else:
                            logger.debug(f"    ✅ 改名成功: {dst_name}")
            return "success"

    @staticmethod
    def get_status_message(code: str) -> str:
        """
        将内部状态码转换为用户友好的中文消息。
        """
        if not code: return "未知错误"
        if code == "success": return "成功"
        if code == "preview": return "预览成功"
        if code == "skipped_conflict": return "目标已存在 (跳过)"
        if code == "src_not_found": return "源文件不存在"
        if code == "same_file": return "源文件与目标文件相同"
        if code == "overwrite_failed": return "覆盖失败"
        if code == "skipped": return "已跳过 (目标已存在)"
        if code == "cd2_client_not_found": return "未找到 CD2 客户端"
        if code == "hardlink_failed_cross_device": return "跨设备硬链失败 (不支持跨盘)"
        if code == "failed_verification_not_found": return "校验失败: 目标文件未找到"
        if code.startswith("failed_size_mismatch"):
            return f"校验失败: 大小不一致 ({code.split('(', 1)[-1].rstrip(')') if '(' in code else ''})"
        if code.startswith("failed"): 
            return f"物理执行失败: {code.split(':', 1)[-1] if ':' in code else code}"
        if code.startswith("rename_failed"):
            return f"重命名失败: {code.split(':', 1)[-1] if ':' in code else code}"
        if code.startswith("batch_action_failed"):
            return f"批量执行失败: {code.split(':', 1)[-1] if ':' in code else code}"
        if code.startswith("cd2_failed"): 
            return f"CD2 操作失败: {code.split(':', 1)[-1] if ':' in code else code}"
        return code

    @staticmethod
    async def _cleanup_empty_parents(path: str, root_limit: str):
        """
        从 path 开始向上递归清理空文件夹，直到撞到 root_limit 为止。
        安全第一：不删 root_limit，且遇到非空目录立即停止。
        """
        if not path or not root_limit: return
        
        # 规范化路径并去除结尾斜杠
        path = os.path.abspath(path).rstrip(os.path.sep)
        root_limit = os.path.abspath(root_limit).rstrip(os.path.sep)
        
        # 如果 path 已经超出了 root_limit 或者就是 root_limit，直接停止
        if not path.startswith(root_limit) or path == root_limit:
            return

        try:
            # 检查目录是否为空 (排除隐藏文件)
            def _is_effectively_empty(p):
                if not os.path.exists(p) or not os.path.isdir(p): return False
                try:
                    items = os.listdir(p)
                except: return False
                # 过滤掉常见的系统垃圾文件
                actual_items = [i for i in items if i not in ['.DS_Store', 'Thumbs.db', '@eaDir'] and not i.startswith('._')]
                return len(actual_items) == 0

            is_empty = await asyncio.to_thread(_is_effectively_empty, path)
            
            if is_empty:
                # 只在确实为空时尝试删除
                try:
                    await asyncio.to_thread(os.rmdir, path)
                    logger.debug(f"已清理源空目录: {os.path.basename(path)}")
                except OSError:
                    # 即使判定为空，rmdir 也可能因为权限或并发项而失败，这种情况下直接停止递归即可
                    return
                
                # 递归向上处理父目录
                parent = os.path.dirname(path)
                await FileExecutor._cleanup_empty_parents(parent, root_limit)
        except:
            # 任何异常都停止清理，确保安全
            pass

    @staticmethod
    async def _execute_cd2_via(client, src: str, dst: str, action: str, conflict: str,
                               source_via: str, target_via: str, dir_cache: set = None) -> str:
        """
        via 路由矩阵：按源/目标归属域选择底层通道。
        - cd2→cd2:   纯 gRPC（ensure_dir + 原位改名 + MoveFile/CopyFile）
        - cd2→local: gRPC CopyFile 经挂载写入本地（cd2_move 后 DeleteFile 云端源）
        - local→cd2: Remote Upload 磁盘数据源（流式分块，免挂载）
        """
        action_label = "移动" if action == "cd2_move" else "复制"
        browser = client._file_browser

        # via 路由直接走底层连接，需确保客户端已登录（token 写入 metadata）
        if not client.logged_in:
            ok = await asyncio.to_thread(client.login)
            if not ok:
                return "cd2_failed: CD2 登录失败"

        dst_dir = os.path.dirname(dst) or "/"
        dst_name = os.path.basename(dst)

        # ---------- cd2 → cd2 ----------
        if source_via == "cd2" and target_via == "cd2":
            ok, msg = await asyncio.to_thread(browser.ensure_dir, dst_dir)
            if not ok: return f"cd2_failed: {msg}"

            if await asyncio.to_thread(browser.path_exists, dst):
                if conflict == "skip": return "skipped_conflict"
                if conflict == "overwrite":
                    ok, msg = await asyncio.to_thread(browser.delete_files, [dst])
                    if not ok: return f"cd2_failed: 目标覆盖删除失败: {msg}"

            if action == "cd2_copy":
                ok, msg = await asyncio.to_thread(browser.transfer_files, [src], dst_dir, "copy", 1)
                if not ok: return f"cd2_failed: {msg}"
                # 复制后目标位为原文件名，需要改名
                copied_path = f"{dst_dir.rstrip('/')}/{os.path.basename(src)}"
                if os.path.basename(src) != dst_name:
                    ok, msg = await asyncio.to_thread(browser.rename, copied_path, dst_name)
                    if not ok: return f"cd2_failed: {msg}"
            else:
                if os.path.basename(src) != dst_name:
                    ok, msg = await asyncio.to_thread(browser.rename, src, dst_name)
                    if not ok: return f"cd2_failed: {msg}"
                    src = f"{os.path.dirname(src).rstrip('/')}/{dst_name}"
                ok, msg = await asyncio.to_thread(browser.transfer_files, [src], dst_dir, "move", 1)
                if not ok: return f"cd2_failed: {msg}"
            return "success"

        # ---------- cd2 → local（免挂载：GetDownloadUrlPath 直下载，挂载复制兜底） ----------
        if source_via == "cd2" and target_via == "local":
            if conflict == "skip" and await asyncio.to_thread(os.path.exists, dst):
                return "skipped_conflict"
            if conflict == "overwrite" and await asyncio.to_thread(os.path.exists, dst):
                await asyncio.to_thread(os.remove, dst)

            target_parent = os.path.dirname(dst)
            await asyncio.to_thread(os.makedirs, target_parent, exist_ok=True)

            # 主通道：获取下载地址流式下载（优先云存储直链）
            ok, result = await asyncio.to_thread(browser.download_file, src, dst)
            if ok:
                if action == "cd2_move":
                    ok_del, msg_del = await asyncio.to_thread(browser.delete_files, [src])
                    if not ok_del:
                        return f"cd2_failed: 下载成功但删除云端源文件失败: {msg_del}"
                return "success"

            # 兜底：下载失败时回退"经 CD2 挂载 CopyFile"（需要 mount_path 配置）
            logger.warning(f"CD2 直下载失败，尝试经挂载复制兜底: {result}")
            mount_path = (client.config or {}).get("mount_path", "")
            if not mount_path:
                return f"cd2_failed: {result}"

            cd2_dst_dir = client._to_cd2_path(target_parent)
            ok, msg = await asyncio.to_thread(browser.ensure_dir, cd2_dst_dir)
            if not ok: return f"cd2_failed: {msg}"

            ok, msg = await asyncio.to_thread(browser.transfer_files, [src], cd2_dst_dir, "copy", 1)
            if not ok: return f"cd2_failed: {msg}"

            copied_cloud = f"{cd2_dst_dir.rstrip('/')}/{os.path.basename(src)}"
            if os.path.basename(src) != dst_name:
                ok, msg = await asyncio.to_thread(browser.rename, copied_cloud, dst_name)
                if not ok: return f"cd2_failed: {msg}"

            if action == "cd2_move":
                ok, msg = await asyncio.to_thread(browser.delete_files, [src])
                if not ok: return f"cd2_failed: 删除云端源文件失败: {msg}"
            return "success"

        # ---------- local → cd2（Remote Upload 磁盘数据源） ----------
        if source_via == "local" and target_via == "cd2":
            if not await asyncio.to_thread(os.path.exists, src):
                return "src_not_found"

            ok, msg = await asyncio.to_thread(browser.ensure_dir, dst_dir)
            if not ok: return f"cd2_failed: {msg}"

            if await asyncio.to_thread(browser.path_exists, dst):
                if conflict == "skip": return "skipped_conflict"
                if conflict == "overwrite":
                    ok, msg = await asyncio.to_thread(browser.delete_files, [dst])
                    if not ok: return f"cd2_failed: 目标覆盖删除失败: {msg}"

            from clients.cd2.remote_upload import RemoteUploadManager
            result = await asyncio.to_thread(
                RemoteUploadManager.get_instance().upload_local_file_sync,
                client._conn, src, dst,
            )
            if not result.get("success"):
                return f"cd2_failed: {result.get('error') or result.get('status_text')}"
            return "success"

        return "cd2_failed: 不支持的 via 组合"

    @staticmethod
    async def execute_action(src: str, dst: str, action: str, conflict: str, dir_cache: set = None, source_root: str = None,
                             source_via: str = "local", target_via: str = "local") -> str:
        """
        Execute single file action asynchronously.
        source_via/target_via: 'local' | 'cd2'，决定 CD2 类动作的底层通道。
        """
        # 云源：本地 FS 存在性检查跳过（数据可能只在云端）
        if source_via != "cd2":
            if not await asyncio.to_thread(os.path.exists, src): return "src_not_found"
        src_size = None
        if source_via != "cd2":
            src_size = await asyncio.to_thread(os.path.getsize, src)

        if target_via != "cd2":
            if await asyncio.to_thread(os.path.exists, dst):
                try:
                    is_same = await asyncio.to_thread(os.path.samefile, src, dst)
                    if is_same: return "same_file"
                except: pass
                if conflict == "skip": return "skipped_conflict"
                if conflict == "overwrite":
                    try:
                        if await asyncio.to_thread(os.path.isdir, dst):
                            await asyncio.to_thread(shutil.rmtree, dst)
                        else:
                            await asyncio.to_thread(os.remove, dst)
                    except: return "overwrite_failed"

        try:
            # --- CD2 Native API Operations ---
            if action in ["cd2_move", "cd2_copy"]:
                all_clients = await asyncio.to_thread(ClientManager.get_all_clients)
                cd2_client = None
                matched_mount = ""

                for c_conf in all_clients:
                    if c_conf.get('type') == 'cd2':
                        mount_path = c_conf.get('mount_path')
                        if mount_path and os.path.abspath(src).startswith(os.path.abspath(mount_path)):
                            cd2_client = await asyncio.to_thread(ClientManager.get_client, c_conf.get('id'))
                            matched_mount = mount_path
                            break

                if not cd2_client:
                    cd2_configs = [c for c in all_clients if c.get('type') == 'cd2']
                    if len(cd2_configs) == 1:
                        cd2_client = await asyncio.to_thread(ClientManager.get_client, cd2_configs[0].get('id'))
                    else: return "cd2_client_not_found"

                if source_via == "cd2" or target_via == "cd2":
                    # --- via 路由矩阵（显式归属域优先） ---
                    return await FileExecutor._execute_cd2_via(
                        cd2_client, src, dst, action, conflict, source_via, target_via, dir_cache
                    )

                # --- 旧版挂载路径模式（老任务兼容，行为不变） ---
                target_parent = os.path.dirname(dst)
                await FileExecutor._ensure_cd2_dir(cd2_client, target_parent, dir_cache)

                action_label = "移动" if action == "cd2_move" else "复制"
                if action == "cd2_move":
                    success, msg = await asyncio.to_thread(cd2_client.move_file, src, dst)
                else: # cd2_copy
                    success, msg = await asyncio.to_thread(cd2_client.copy_file, src, dst)

                if not success:
                    if "already exists" in str(msg).lower() or "ALREADY_EXISTS" in str(msg):
                        logger.warning(f"目标位已存在: {os.path.basename(src)}")
                        return "skipped"
                    logger.error(f"{os.path.basename(src)} -> {msg}")
                    return f"cd2_failed: {msg}"

                logger.debug(f"{os.path.basename(src)} (API校验成功 ✅)")
                return "success"
            
            # --- Standard OS Operations ---
            elif action in ["move", "copy", "link"]:
                target_dir = os.path.dirname(dst)
                await asyncio.to_thread(os.makedirs, target_dir, exist_ok=True)
                
                src_name = os.path.basename(src)
                dst_name = os.path.basename(dst)
                action_label = {"move": "移动", "copy": "复制", "link": "硬链"}.get(action, action)
                
                if src_name != dst_name:
                    logger.debug(f"正在{action_label}并改名: {src_name} -> {dst_name}")
                else:
                    logger.debug(f"正在{action_label}: {src_name}")

                if action == "move":
                    try:
                        await asyncio.to_thread(shutil.move, src, dst)
                    except Exception as e:
                        # Fallback for cross-device move where metadata sync might fail
                        logger.warning(f"标准移动失败，尝试强制复制模式: {str(e)}")
                        await asyncio.to_thread(shutil.copy, src, dst)
                        await asyncio.to_thread(os.remove, src)
                elif action == "copy":
                    await asyncio.to_thread(shutil.copy, src, dst)
                elif action == "link":
                    try: 
                        await asyncio.to_thread(os.link, src, dst)
                    except OSError as e:
                        if e.errno == 18:
                            error_msg = "跨设备硬链失败 (不支持跨盘硬链，请改用移动或复制)"
                        else:
                            error_msg = f"硬链失败: {str(e)}"
                        logger.error(f"{action_label}: {os.path.basename(src)} -> {error_msg}")
                        return "hardlink_failed_cross_device" if e.errno == 18 else f"failed_{e.errno}"
            
            # --- Verification ---
            # 云目标没有本地 FS 视图，CD2 API 返回成功即认定成功
            if target_via != "cd2":
                if not await asyncio.to_thread(os.path.exists, dst):
                    logger.error(f"文件未出现在目标位置: {os.path.basename(dst)}")
                    return "failed_verification_not_found"

                dst_size = await asyncio.to_thread(os.path.getsize, dst)
                if action != "move" and action != "link" and src_size is not None:
                    if src_size != dst_size:
                        logger.error(f"大小不一致: {src_size} != {dst_size}")
                        return f"failed_size_mismatch({src_size}!={dst_size})"

                stat_info = await asyncio.to_thread(os.stat, dst)
                mode = oct(stat_info.st_mode)[-3:]

            audit_details = {"action": action, "src": src, "dst": dst, "status": "Verified", "via": f"{source_via}->{target_via}"}
            logger.debug(f"{action_label}成功: {os.path.basename(src)} (校验通过 ✅)")
            return "success"
        except Exception as e: 
            logger.error(f"{action} 出错: {str(e)}")
            return f"failed: {str(e)}"