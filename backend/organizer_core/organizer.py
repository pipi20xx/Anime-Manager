import os
import json
import re
import asyncio
from typing import Dict, Any, Generator, List

from logger import log_audit
from .executor import FileExecutor
from .processor import FileProcessor

class Organizer:
    VIDEO_EXTS = ['.mkv', '.mp4', '.avi', '.mov', '.ts', '.wmv', '.flv', '.m2ts']
    _STOPPED_TASKS = set()

    @staticmethod
    def stop_task(task_id: str):
        Organizer._STOPPED_TASKS.add(task_id)

    @staticmethod
    def _walk_recursive(source_dir: str, ignore_file_regex: List[str], ignore_dir_regex: List[str], 
                     dir_exists_cache: set, queue: asyncio.Queue, should_stop_func) -> bool:
        """
        使用 os.scandir 递归遍历目录
        性能提升：2-3 倍（相比 os.walk）
        返回 True 表示应该停止扫描
        """
        try:
            with os.scandir(source_dir) as entries:
                dirs = []
                for entry in entries:
                    name = entry.name
                    
                    if name.startswith('.'):
                        continue
                    
                    if entry.is_dir(follow_symlinks=False):
                        dirs.append(name)
                    elif entry.is_file(follow_symlinks=False):
                        f_path = os.path.join(source_dir, name)
                        
                        if ignore_file_regex and Organizer._is_regex_match(name, ignore_file_regex):
                            continue
                        
                        ext = os.path.splitext(name)[1].lower()
                        if ext in Organizer.VIDEO_EXTS:
                            queue.put_nowait(f_path)
                            
                            if should_stop_func():
                                return True
        except (PermissionError, OSError):
            pass
        
        for d in dirs:
            if ignore_dir_regex and Organizer._is_regex_match(d, ignore_dir_regex):
                continue
            
            if should_stop_func():
                return True
            
            if Organizer._walk_recursive(os.path.join(source_dir, d), ignore_file_regex, 
                                       ignore_dir_regex, dir_exists_cache, queue, should_stop_func):
                return True
        
        return False

    @staticmethod
    async def run_task(task: Dict[str, Any], dry_run: bool = True, task_id: str = None) -> Generator[str, None, None]:
        """
        流式执行整理任务。
        """
        if task_id and task_id in Organizer._STOPPED_TASKS:
            Organizer._STOPPED_TASKS.remove(task_id)

        context = FileProcessor.load_context(task)
        if not context["rule"]:
            yield json.dumps({"type": "error", "message": f"Rule {task.get('rule_id')} not found"}) + "\n"
            return

        source_dir = task.get("source_dir")
        ignore_file_regex = task.get("ignore_file_regex", [])
        ignore_dir_regex = task.get("ignore_dir_regex", [])
        
        dir_exists_cache = set()
        context["dir_cache"] = dir_exists_cache
        
        processed_count = 0
        start_msg = f"开始任务: {task.get('name', '手动整理')}"
        log_audit("整理", "流式处理", start_msg, details=f"Source: {source_dir}")
        yield json.dumps({"type": "start", "message": start_msg}) + "\n"

        def should_stop():
            return task_id in Organizer._STOPPED_TASKS

        file_queue = asyncio.Queue(maxsize=100)
        
        def scan_wrapper():
            return Organizer._walk_recursive(
                source_dir, ignore_file_regex, ignore_dir_regex,
                dir_exists_cache, file_queue, should_stop
            )

        scan_task = asyncio.create_task(asyncio.to_thread(scan_wrapper))
        
        try:
            while True:
                try:
                    f_path = await asyncio.wait_for(file_queue.get(), timeout=0.1)
                    
                    if ignore_file_regex and Organizer._is_regex_match(os.path.basename(f_path), ignore_file_regex):
                        yield json.dumps({"type": "skip", "source": f_path, "reason": "匹配文件忽略正则"}) + "\n"
                        continue
                    
                    results = await FileProcessor.organize_video_file(f_path, task, context, dry_run)
                    for res in results:
                        yield json.dumps(res) + "\n"
                        if res.get("status") in ["success", "preview"]:
                            processed_count += 1
                except asyncio.TimeoutError:
                    if scan_task.done():
                        break
        finally:
            if not scan_task.done():
                scan_task.cancel()
                try:
                    await scan_task
                except asyncio.CancelledError:
                    pass

        if should_stop():
            log_audit("整理", "任务取消", f"任务 {task_id} 已由用户停止")
            yield json.dumps({"type": "error", "message": "任务已手动停止"}) + "\n"
            Organizer._STOPPED_TASKS.remove(task_id)
            return

        log_audit("整理", "任务完成", f"任务流执行结束，共处理 {processed_count} 个项目")
        yield json.dumps({"type": "finish", "count": processed_count}) + "\n"

    @staticmethod
    async def execute_batch(items: List[Dict[str, Any]], conflict_mode: str, task_id: str = None) -> Generator[str, None, None]:
        processed = 0
        dir_cache = set()
        yield json.dumps({"type": "start", "message": "开始执行正式任务"}) + "\n"
        for item in items:
            # 检查中断
            if task_id and task_id in Organizer._STOPPED_TASKS:
                yield json.dumps({"type": "error", "message": "批处理任务已手动停止"}) + "\n"
                Organizer._STOPPED_TASKS.remove(task_id)
                return

            await asyncio.sleep(0.01)

            src, dst, action = item.get("source"), item.get("target"), item.get("action", "move")
            res = await FileExecutor.execute_action(src, dst, action, conflict_mode, dir_cache)
            
            if res == "success":
                processed += 1
                # [Audit] 记录关键文件操作
                log_audit("整理", "文件操作", f"成功{action}: {os.path.basename(src)} -> {os.path.basename(dst)}", level="INFO")
            else:
                 log_audit("整理", "操作失败", f"{action}失败: {os.path.basename(src)} -> {FileExecutor.get_status_message(res)}", level="ERROR")

            yield json.dumps({
                "type": "item", "status": "success" if res == "success" else "error", 
                "source": src, "target": dst, "msg": FileExecutor.get_status_message(res)
            }) + "\n"
        
        log_audit("整理", "批量执行结束", f"物理操作执行完毕，共成功处理 {processed} 个文件")
        yield json.dumps({"type": "finish", "count": processed}) + "\n"

    @staticmethod
    def _is_regex_match(text: str, patterns: List[str]) -> bool:
        if not patterns: return False
        for p in patterns:
            if not p: continue
            try:
                if re.search(p, text, re.I): return True
            except: pass
        return False

    # 保持对外的 organize_video_file 接口兼容性
    @staticmethod
    async def organize_video_file(v_path: str, task: Dict[str, Any], context: Dict[str, Any] = None, dry_run: bool = True) -> List[Dict[str, Any]]:
        return await FileProcessor.organize_video_file(v_path, task, context, dry_run)
