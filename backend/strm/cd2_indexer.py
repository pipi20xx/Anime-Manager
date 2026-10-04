import asyncio
import logging
from typing import List, Dict, Any, Optional
from clients.cd2 import CD2Client

logger = logging.getLogger("CD2Indexer")

class CD2Indexer:
    def __init__(self, client: CD2Client, max_workers: int = 20):
        """
        使用统一的 CD2Client 实例进行初始化
        """
        self.client = client
        self.max_workers = max_workers
        self.is_running = True
        # 最近一次 scan_path 中拉取失败的目录（网盘限流/风控等），供调用方如实上报
        self.failed_dirs: set = set()

    async def scan_path(self, root_path: str, force_refresh: bool = False, on_progress=None) -> Dict[str, List[Dict[str, Any]]]:
        """
        并发扫描指定路径，返回扁平化的目录映射: { "parent_path": [children_items...] }
        """
        # 1. 确保已登录
        if not self.client.logged_in or not self.client.token:
            if not await self.client.login_async():
                logger.error("CD2 Indexer failed to login.")
                return {}

        # 2. 获取 Stub
        stub = await self.client._get_async_stub()
        pb2 = self.client.pb2

        # 规范化路径
        if root_path != "/" and root_path.endswith("/"):
            root_path = root_path.rstrip("/")

        tree_data = {}
        self.failed_dirs = set()
        queue = asyncio.Queue()
        await queue.put(root_path)
        
        active_tasks = 0
        lock = asyncio.Lock()
        enqueued_dirs = {root_path}

        async def worker():
            nonlocal active_tasks
            while self.is_running:
                try:
                    path = await asyncio.wait_for(queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    async with lock:
                        if active_tasks == 0: break
                    continue

                async with lock: active_tasks += 1
                try:
                    # 实时回调进度
                    if on_progress:
                        await on_progress(path)

                    # 锁定缓存优先：锁定的目录直接用快照（0 API），子目录照常入队
                    items = None
                    try:
                        from cd2_dir_cache import get_snapshot_entries
                        items = await get_snapshot_entries(path)
                    except Exception as ce:
                        logger.debug(f"[CD2Indexer] 缓存查询失败 {path}: {ce}")

                    if items is None:
                        items = await self._fetch_dir(stub, pb2, path, force_refresh)
                        if items is None:
                            self.failed_dirs.add(path)
                        # --- 增加限流延迟（走缓存的不需要） ---
                        import random
                        await asyncio.sleep(random.uniform(0.3, 0.6))

                    if items is not None:
                        tree_data[path] = items
                        for item in items:
                            if item['is_dir']:
                                p = item['path']
                                async with lock:
                                    if p not in enqueued_dirs:
                                        enqueued_dirs.add(p)
                                        await queue.put(p)
                except Exception as e:
                    logger.error(f"Worker error on {path}: {e}")
                finally:
                    async with lock: active_tasks -= 1
                    queue.task_done()

        # 启动并发 workers
        workers = [asyncio.create_task(worker()) for _ in range(self.max_workers)]
        await queue.join()
        for w in workers: w.cancel()
            
        return tree_data

    async def _fetch_dir(self, stub, pb2, path: str, force: bool) -> Optional[List[Dict[str, Any]]]:
        result = []
        try:
            req = pb2.ListSubFileRequest(path=path, forceRefresh=force)
            metadata = self.client.get_metadata()
            # 异步流式迭代（字段提取与 CD2FileBrowser.list_dir 保持同源同形，
            # 保证锁定快照无论由哪条路径写入，条目结构一致）
            call = stub.GetSubFiles(req, metadata=metadata, timeout=60)
            async for resp in call:
                if not resp.subFiles: continue
                for f in resp.subFiles:
                    result.append({
                        'name': f.name,
                        'path': f.fullPathName or f.path or f"/{f.name}",
                        'is_dir': bool(f.isDirectory) or int(f.fileType) == 0,
                        'size': int(f.size),
                        'write_time': int(f.writeTime.seconds) if f.HasField("writeTime") else 0,
                        'is_forbidden': bool(f.isForbidden),
                        'can_offline_download': bool(getattr(f, "canOfflineDownload", False)),
                    })
            return result
        except Exception as e:
            logger.warning(f"Fetch failed for {path}: {e}")
            return None