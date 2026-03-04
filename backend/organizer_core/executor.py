import os
import shutil
import asyncio
from typing import List, Tuple, Dict, Any
from logger import log_audit
from clients.manager import ClientManager

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
        
        log_audit("整理", "CD2路径", f"正在云端创建目录: {dir_name}", details={"parent": cd2_parent})
        
        # client.create_directory is a gRPC call, run in thread
        success, err = await asyncio.to_thread(client.create_directory, cd2_parent, dir_name)
        
        if success:
            log_audit("整理", "CD2路径", f"  ✅ 目录创建成功: {dir_name}")
            if dir_cache is not None: dir_cache.add(local_path)
            return True
        elif "already exists" in err.lower() or "conflict" in err.lower():
            log_audit("整理", "CD2路径", f"  ℹ️ 目录已存在: {dir_name}")
            if dir_cache is not None: dir_cache.add(local_path)
            return True
        else:
            log_audit("整理", "CD2路径失败", f"  ❌ 创建目录失败: {dir_name} -> {err}", level="ERROR")
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
                    log_audit("整理", "CD2重命名", f"正在原位重命名 (移动前): {src_name} -> {dst_name}")
                    # API Call in thread
                    success, err = await asyncio.to_thread(client.rename_file, client._to_cd2_path(src), dst_name)
                    if not success:
                        log_audit("整理", "CD2重命名失败", f"{src_name} -> {err}", level="ERROR")
                        return f"rename_failed: {err}"
                    log_audit("整理", "CD2重命名", f"  ✅ 原位改名成功: {dst_name}")
                    current_src = os.path.join(os.path.dirname(src), dst_name)
                renamed_src_paths.append(current_src)
            
            # API Batch Move in thread
            try:
                success, err = await asyncio.to_thread(client.move_files, renamed_src_paths, dest_dir)
                if not success:
                    if "already exists" in str(err).lower() or "ALREADY_EXISTS" in str(err):
                        log_audit("整理", "CD2跳过", f"目标已存在，跳过批量移动: {files_desc}", level="WARN")
                        return "skipped"
                    log_audit("整理", "CD2批量移动", f"CD2批量移动失败: {len(items)} 个项目 -> {err}", level="ERROR")
                    return f"batch_action_failed: {err}"
            except Exception as e:
                if "already exists" in str(e).lower() or "ALREADY_EXISTS" in str(e):
                    log_audit("整理", "CD2跳过", f"目标已存在，跳过批量移动: {files_desc}", level="WARN")
                    return "skipped"
                raise e
            
            log_audit("整理", "CD2批量移动", f"CD2批量移动成功: 共 {len(items)} 个项目 (API 校验通过 ✅)")
            for fname in file_names:
                log_audit("整理", "CD2完成", f"  [已移动] {fname}")
            return "success"

        else: # cd2_copy
            # --- Copy Logic: Batch Copy -> Rename at Destination ---
            src_paths = [src for src, _ in items]
            # API Batch Copy in thread
            try:
                success, err = await asyncio.to_thread(client.copy_files, src_paths, dest_dir)
                if not success:
                    if "already exists" in str(err).lower() or "ALREADY_EXISTS" in str(err):
                        log_audit("整理", "CD2跳过", f"目标已存在，跳过批量复制: {files_desc}", level="WARN")
                        return "skipped"
                    log_audit("整理", "CD2批量复制", f"CD2批量复制失败: {len(items)} 个项目 -> {err}", level="ERROR")
                    return f"batch_action_failed: {err}"
            except Exception as e:
                if "already exists" in str(e).lower() or "ALREADY_EXISTS" in str(e):
                    log_audit("整理", "CD2跳过", f"目标已存在，跳过批量复制: {files_desc}", level="WARN")
                    return "skipped"
                raise e
            
            log_audit("整理", "CD2批量复制", f"CD2批量复制成功: 共 {len(items)} 个项目 (API 校验通过 ✅)")
            for fname in file_names:
                log_audit("整理", "CD2完成", f"  [已复制] {fname}")

            # 2. Rename at destination
            if any(os.path.basename(src) != os.path.basename(dst) for src, dst in items):
                log_audit("整理", "CD2重命名", f"检测到命名变化，开始目标位重命名流程...")
                for i, (src, dst) in enumerate(items):
                    src_name = os.path.basename(src)
                    dst_name = os.path.basename(dst)
                    if src_name != dst_name:
                        path_at_dest = os.path.join(dest_dir, src_name)
                        log_audit("整理", "CD2重命名", f"  正在改名: {src_name} -> {dst_name}")
                        success, err = await asyncio.to_thread(client.rename_file, client._to_cd2_path(path_at_dest), dst_name)
                        if not success:
                            log_audit("整理", "CD2重命名失败", f"    ❌ 改名失败: {src_name} -> {err}", level="ERROR")
                            if i == 0: return f"rename_failed: {err}"
                        else:
                            log_audit("整理", "CD2重命名", f"    ✅ 改名成功: {dst_name}")
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
                    log_audit("整理", "清理空目录", f"已清理源空目录: {os.path.basename(path)}")
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
    async def execute_action(src: str, dst: str, action: str, conflict: str, dir_cache: set = None, source_root: str = None) -> str:
        """
        Execute single file action asynchronously.
        """
        # I/O checks in thread
        if not await asyncio.to_thread(os.path.exists, src): return "src_not_found"
        src_size = await asyncio.to_thread(os.path.getsize, src)

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

                target_parent = os.path.dirname(dst)
                await FileExecutor._ensure_cd2_dir(cd2_client, target_parent, dir_cache)

                action_label = "移动" if action == "cd2_move" else "复制"
                if action == "cd2_move":
                    success, msg = await asyncio.to_thread(cd2_client.move_file, src, dst)
                else: # cd2_copy
                    success, msg = await asyncio.to_thread(cd2_client.copy_file, src, dst)
                
                if not success:
                    if "already exists" in str(msg).lower() or "ALREADY_EXISTS" in str(msg):
                        log_audit("整理", f"CD2跳过", f"目标位已存在: {os.path.basename(src)}", level="WARN")
                        return "skipped"
                    log_audit("整理", f"CD2{action_label}失败", f"{os.path.basename(src)} -> {msg}", level="ERROR", details={"src": src, "dst": dst})
                    return f"cd2_failed: {msg}"
                
                log_audit("整理", f"CD2{action_label}成功", f"{os.path.basename(src)} (API校验成功 ✅)", details={"src": src, "dst": dst})
                return "success"
            
            # --- Standard OS Operations ---
            elif action in ["move", "copy", "link"]:
                target_dir = os.path.dirname(dst)
                await asyncio.to_thread(os.makedirs, target_dir, exist_ok=True)
                
                src_name = os.path.basename(src)
                dst_name = os.path.basename(dst)
                action_label = {"move": "移动", "copy": "复制", "link": "硬链"}.get(action, action)
                
                if src_name != dst_name:
                    log_audit("整理", f"文件{action_label}", f"正在{action_label}并改名: {src_name} -> {dst_name}")
                else:
                    log_audit("整理", f"文件{action_label}", f"正在{action_label}: {src_name}")

                if action == "move":
                    try:
                        await asyncio.to_thread(shutil.move, src, dst)
                    except Exception as e:
                        # Fallback for cross-device move where metadata sync might fail
                        log_audit("整理", "物理执行警告", f"标准移动失败，尝试强制复制模式: {str(e)}", level="WARN")
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
                        log_audit("整理", "物理执行失败", f"{action_label}: {os.path.basename(src)} -> {error_msg}", level="ERROR")
                        return "hardlink_failed_cross_device" if e.errno == 18 else f"failed_{e.errno}"
            
            # --- Verification ---
            if not await asyncio.to_thread(os.path.exists, dst):
                log_audit("整理", "校验失败", f"文件未出现在目标位置: {os.path.basename(dst)}", level="ERROR")
                return "failed_verification_not_found"
            
            dst_size = await asyncio.to_thread(os.path.getsize, dst)
            if action != "move" and action != "link":
                if src_size != dst_size:
                    log_audit("整理", "校验失败", f"大小不一致: {src_size} != {dst_size}", level="ERROR")
                    return f"failed_size_mismatch({src_size}!={dst_size})"
            
            stat_info = await asyncio.to_thread(os.stat, dst)
            mode = oct(stat_info.st_mode)[-3:]
            
            audit_details = {"action": action, "src": src, "dst": dst, "size": f"{dst_size / 1024 / 1024:.2f} MB", "mode": mode, "status": "Verified"}
            log_audit("整理", "物理执行成功", f"{action_label}成功: {os.path.basename(src)} (校验通过 ✅)", details=audit_details)
            return "success"
        except Exception as e: 
            log_audit("整理", "物理执行异常", f"{action} 出错: {str(e)}", level="ERROR")
            return f"failed: {str(e)}"