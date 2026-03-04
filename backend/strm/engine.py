import os
import json
import asyncio
import time
from typing import AsyncGenerator, Dict, Any, List, Set, Optional, Callable, Awaitable
from logger import log_audit
from notification import NotificationManager
from .processor import StrmProcessor
from .constants import META_EXTENSIONS

class StrmTaskEngine:
    """
    高性能 STRM 处理引擎
    负责：队列管理、消费者循环、统计、通知、清理逻辑。
    """
    def __init__(self, config: Dict[str, Any], stats: Optional[Dict[str, Any]] = None):
        self.config = config
        self.stats = stats or {
            "strm_created": 0, 
            "strm_skipped": 0, 
            "meta_copied": 0, 
            "meta_skipped": 0, 
            "deleted": 0, 
            "errors": 0,
            "duration": "0s"
        }
        self.all_valid_rel_paths: Set[str] = set()
        self.queue = asyncio.Queue(maxsize=200)
        self.start_time = 0
        self.target_dir = os.path.normpath(config.get("target_dir") or config.get("target_path") or "")

    async def run(self, scanner_func: Callable[[asyncio.Queue], Awaitable[None]], 
                  processor_func: Optional[Callable[[str, Dict[str, Any]], Awaitable[Dict[str, Any]]]] = None,
                  is_last_stage: bool = True,
                  use_interval: bool = True) -> AsyncGenerator[str, None]:
        """
        运行引擎
        :param scanner_func: 一个异步函数，负责往 self.queue 中塞入待处理的文件路径。
        :param processor_func: 可选，自定义处理逻辑函数。
        :param is_last_stage: 是否是最后一个阶段。如果是，则会执行清理逻辑、计算总耗时并发送通知。
        :param use_interval: 是否使用配置中的限流间隔。
        """
        if self.start_time == 0:
            self.start_time = time.time()
        
        yield json.dumps({"type": "start", "message": "启动处理引擎..."}) + "\n"
        
        # 默认处理器
        process_file = processor_func or StrmProcessor.process_single_file
        
        # 1. 启动生产者 (后台任务)
        scanner_task = asyncio.create_task(scanner_func(self.queue))
        
        # 2. 消费者循环
        while True:
            item = await self.queue.get()
            
            # 结束标志
            if item is None:
                break
            
            # 异常处理
            if isinstance(item, Exception):
                yield json.dumps({"type": "error", "message": f"扫描过程出错: {str(item)}"}) + "\n"
                break

            # 使用指定的处理器处理单个文件
            res = await process_file(item, self.config)
            for line in self._handle_result(item, res):
                yield line
            
            self.queue.task_done()
            
            # 智能限流逻辑：
            # 1. 只有开启了 use_interval 且设置了间隔
            # 2. 只有在真正成功处理了元数据 (status == "success") 时才休眠
            # 3. 如果是跳过 (skipped)，则不休眠，立即处理下一个
            interval = float(self.config.get("process_interval") or 0)
            msg = res.get("message", "")
            status = res.get("status")
            
            if use_interval and interval > 0 and status == "success" and ("Meta" in msg or "Downloaded" in msg):
                info_msg = f"限流保护: 为文件 {os.path.basename(item)} 等待 {interval}s..."
                log_audit("STRM", "限流", info_msg)
                yield json.dumps({"type": "info", "message": info_msg}) + "\n"
                await asyncio.sleep(interval)
            else:
                # 瞬间跳过或处理 STRM
                await asyncio.sleep(0.001)

        # 等待扫描任务彻底结束
        await scanner_task

        if not is_last_stage:
            # 如果不是最后一个阶段，只汇报当前小结，不执行清理和结束通知
            yield json.dumps({"type": "info", "message": "阶段任务完成，准备进入下一阶段..."}) + "\n"
            return

        # 3. 冗余清理
        if self.config.get("clean_target") and os.path.exists(self.target_dir):
            async for line in self._cleanup_phase():
                yield line

        if self.config.get("clean_empty_dirs"):
            await StrmProcessor.remove_empty_dirs_async(self.target_dir)

        # 4. 完成
        self._finalize()
        yield json.dumps({"type": "finish", "stats": self.stats}) + "\n"

    def _handle_result(self, item: str, res: Dict[str, Any]) -> AsyncGenerator[str, None]:
        status = res.get("status")
        msg = res.get("message")
        rel_path = res.get("rel_path")

        if status == "success":
            if msg == "Created STRM":
                self.stats["strm_created"] += 1
                log_audit("STRM", "生成", f"成功: {os.path.basename(item)}")
            elif "Meta" in msg:
                self.stats["meta_copied"] += 1
                log_audit("STRM", "同步", f"成功: {os.path.basename(item)} ({msg})")
            
            if rel_path:
                self.all_valid_rel_paths.add(os.path.normpath(rel_path))
            
            yield json.dumps({
                "type": "log", 
                "path": os.path.basename(item), 
                "status": "success", 
                "message": msg
            }) + "\n"
        
        elif status == "skipped":
            if msg == "MetaExists":
                self.stats["meta_skipped"] += 1
            elif msg == "Exists":
                self.stats["strm_skipped"] += 1
            
            log_audit("STRM", "跳过", f"已存在: {os.path.basename(item)}")
            
            if rel_path:
                self.all_valid_rel_paths.add(os.path.normpath(rel_path))
            
            yield json.dumps({
                "type": "log", 
                "path": os.path.basename(item), 
                "status": "skipped", 
                "message": f"跳过 (已存在): {msg}"
            }) + "\n"

        elif status == "error":
            self.stats["errors"] += 1
            yield json.dumps({"type": "log", "path": os.path.basename(item), "status": "error", "message": msg}) + "\n"

    async def _cleanup_phase(self) -> AsyncGenerator[str, None]:
        yield json.dumps({"type": "info", "message": "正在比对并清理本地冗余文件..."}) + "\n"
        
        def _cleanup():
            deleted = 0
            copy_meta = self.config.get("copy_meta", False)
            meta_extensions = set(self.config.get("meta_extensions") or META_EXTENSIONS)
            now = time.time()
            # 保护期：10分钟内创建或修改的文件不清理
            protection_window = 600 
            
            for root, _, files in os.walk(self.target_dir):
                for f in files:
                    if f.startswith('.'): continue
                    full_p = os.path.join(root, f)
                    rel_p = os.path.normpath(os.path.relpath(full_p, self.target_dir))
                    
                    if rel_p not in self.all_valid_rel_paths:
                        # 检查文件时间，如果是刚刚生成的，跳过清理
                        try:
                            mtime = os.path.getmtime(full_p)
                            if now - mtime < protection_window:
                                continue
                        except: pass

                        ext = os.path.splitext(f)[1].lower()
                        # 只删除 .strm 或者开启了元数据复制时的元数据文件
                        if ext == '.strm' or (copy_meta and ext in meta_extensions):
                            try:
                                os.remove(full_p)
                                deleted += 1
                                log_audit("STRM", "清理", f"删除冗余文件: {f}")
                            except: pass
            return deleted
        
        self.stats["deleted"] = await asyncio.to_thread(_cleanup)

    def _finalize(self):
        duration = time.time() - self.start_time
        self.stats["duration"] = f"{duration:.1f}s"
        self.stats["source"] = self.config.get("source_dir") or self.config.get("source_path")
        self.stats["target"] = self.target_dir
        
        # 发送通知
        asyncio.create_task(
            NotificationManager.push_strm_finish_notification(
                self.config.get("name", "任务"), 
                self.stats
            )
        )
        log_audit("STRM", "任务完成", f"总耗时: {self.stats['duration']}")
