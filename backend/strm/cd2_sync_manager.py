import os
import json
import asyncio
import logging
import shutil
import unicodedata
import httpx
import urllib.parse
from typing import Dict, Any, List, Set, AsyncGenerator
from .cd2_indexer import CD2Indexer
from .constants import VIDEO_EXTENSIONS, META_EXTENSIONS
from .processor import StrmProcessor
from .engine import StrmTaskEngine
from .scanners import ListScanner
from clients.cd2 import CD2Client
from logger import log_audit
from notification import NotificationManager

logger = logging.getLogger("CD2SyncManager")

def normalize_path(path: str) -> str:
    """统一路径格式：规范化 Unicode 编码并清理分隔符"""
    if not path: return ""
    # 使用 NFC 规范化（Linux/Windows 常用）
    normalized = unicodedata.normalize('NFC', path)
    return os.path.normpath(normalized).lstrip(os.sep)

class CD2SyncManager:
    @staticmethod
    async def generate_via_api(config: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """
        基于 CD2 API 的快照比对同步模式 (流式)
        """
        import time
        start_time = time.time()
        
        # 1. 基础配置与路径规范化
        source_root = os.path.normpath(config.get("source_dir") or config.get("source_path") or "")
        target_root = os.path.normpath(config.get("target_dir") or config.get("target_path") or "")
        copy_meta = config.get("copy_meta", False)
        clean_target = config.get("clean_target", False)
        
        # 严格清理映射路径
        mapping_root_raw = config.get("cd2_mapping_path") or ""
        cd2_conf = config.get("cd2_config", {})
        if not mapping_root_raw:
            mapping_root_raw = cd2_conf.get("mount_path", "")
        
        mapping_root = os.path.normpath(mapping_root_raw.strip()).rstrip(os.sep)

        log_audit("STRM", "API同步启动", f"正在启动快照比对同步: {source_root}")
        yield json.dumps({"type": "start", "message": "正在解析路径并建立连接..."}) + "\n"

        # --- 自动路径换算 (CD2 内部路径) ---
        cd2_internal_path = source_root
        if mapping_root and source_root.startswith(mapping_root):
            cd2_internal_path = source_root[len(mapping_root):]
            if not cd2_internal_path.startswith('/'):
                cd2_internal_path = '/' + cd2_internal_path
        
        cd2_internal_path = cd2_internal_path.replace('//', '/')

        # 2. 登录并扫描云端 (CD2)
        client_config = {
            "name": "STRM_Indexer",
            "url": cd2_conf.get("host", ""),
            "username": cd2_conf.get("user", ""),
            "password": cd2_conf.get("pass", ""),
            "mount_path": mapping_root
        }
        client = CD2Client(client_config)
        if not await client.login_async():
            yield json.dumps({"type": "error", "message": "CD2 登录失败"}) + "\n"
            return

        indexer = CD2Indexer(client, max_workers=1)
        
        # --- 实时日志采集机制 ---
        log_queue = asyncio.Queue()
        async def on_scan_progress(path):
            await log_queue.put(path)

        # 启动扫描任务
        scan_task = asyncio.create_task(indexer.scan_path(cd2_internal_path, force_refresh=config.get("force_refresh", False), on_progress=on_scan_progress))
        
        cloud_tree = None
        scan_count = 0
        while not scan_task.done():
            try:
                # 等待进度更新或任务结束
                path_progress = await asyncio.wait_for(log_queue.get(), timeout=0.5)
                scan_count += 1
                
                # 同步到前端
                yield json.dumps({"type": "info", "message": f"正在扫描云端目录: {path_progress}"}) + "\n"
                
                # 每扫 1 个目录都同步到控制台审计日志 (如果嫌多可以加取模判断)
                log_audit("STRM", "扫描进度", f"正在扫描第 {scan_count} 个目录: {path_progress}")
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Log polling error: {e}")
                break

        # 确保取出队列中剩余的所有日志
        while not log_queue.empty():
            p = log_queue.get_nowait()
            yield json.dumps({"type": "info", "message": f"正在扫描云端目录: {p}"}) + "\n"

        cloud_tree = await scan_task
        await client.close_async()

        if not cloud_tree:
            yield json.dumps({"type": "error", "message": "未能获取到云端数据"}) + "\n"
            return

        # 3. 扫描本地目标目录快照 (用于比对)
        yield json.dumps({"type": "info", "message": "正在构建本地目标目录快照..."}) + "\n"
        existing_files: Set[str] = set()
        if os.path.exists(target_root):
            for root, _, files in os.walk(target_root):
                rel_d = os.path.relpath(root, target_root)
                if rel_d == ".": rel_d = ""
                for f in files:
                    p = normalize_path(os.path.join(rel_d, f))
                    existing_files.add(p)
        
        # 4. 任务分拣
        stats = {
            "strm_created": 0, "strm_skipped": 0, 
            "meta_copied": 0, "meta_skipped": 0, 
            "deleted": 0, "errors": 0
        }
        video_exts = set(VIDEO_EXTENSIONS)
        meta_exts = set(META_EXTENSIONS)
        if config.get("target_extensions"):
             video_exts = set(e.lower() if e.startswith('.') else f".{e.lower()}" for e in config.get("target_extensions"))
        if config.get("meta_extensions"):
             meta_exts = set(e.lower() if e.startswith('.') else f".{e.lower()}" for e in config.get("meta_extensions"))

        strm_tasks = [] 
        meta_tasks = [] 
        all_valid_rel_paths: Set[str] = set()

        for parent_path, items in cloud_tree.items():
            try:
                rel_dir = os.path.relpath(os.path.normpath(parent_path), os.path.normpath(cd2_internal_path))
                if rel_dir == ".": rel_dir = ""
            except: rel_dir = ""

            for item in items:
                if item['is_dir']: continue
                file_name = item['name']
                ext = os.path.splitext(file_name)[1].lower()
                local_file_path = os.path.join(source_root, rel_dir, file_name)

                if ext in video_exts:
                    strm_name = os.path.splitext(file_name)[0] + ".strm"
                    # --- 核心改进：比对路径规范化 ---
                    rel_strm_path = normalize_path(os.path.join(rel_dir, strm_name))
                    all_valid_rel_paths.add(rel_strm_path)
                    
                    if rel_strm_path not in existing_files or config.get("overwrite_strm", config.get("overwrite", False)):
                        strm_tasks.append((local_file_path, rel_strm_path, file_name))
                    else:
                        stats["strm_skipped"] += 1
                        # 逐行打印跳过日志，满足用户对“完整详细”日志的需求
                        log_audit("STRM", "跳过", f"STRM 已存在: {file_name}")
                        yield json.dumps({"type": "log", "action": "SKIP_STRM", "status": "info", "path": rel_strm_path}) + "\n"

                elif copy_meta and ext in meta_exts:
                    rel_meta_path = normalize_path(os.path.join(rel_dir, file_name))
                    all_valid_rel_paths.add(rel_meta_path)
                    
                    if rel_meta_path not in existing_files or config.get("overwrite_meta", config.get("overwrite", False)):
                        meta_tasks.append((local_file_path, rel_meta_path, file_name))
                    else:
                        # 成功跳过
                        stats["meta_skipped"] += 1
                        log_audit("STRM", "跳过", f"元数据已存在: {file_name}")
                        yield json.dumps({"type": "log", "action": "SKIP_COPY", "status": "info", "path": rel_meta_path}) + "\n"

        strm_tasks_paths = [t[0] for t in strm_tasks]
        meta_tasks_paths = [t[0] for t in meta_tasks]
        
        # 5. 执行阶段一：生成 STRM
        engine = StrmTaskEngine(config, stats=stats)
        
        if strm_tasks_paths:
            msg = f"第一阶段：开始生成 {len(strm_tasks_paths)} 个 STRM 文件..."
            log_audit("STRM", "阶段开始", msg)
            yield json.dumps({"type": "info", "message": msg}) + "\n"
            
            # 使用 ListScanner 喂入需要处理的文件
            # STRM 生成不限流，use_interval=False
            async for line in engine.run(ListScanner(strm_tasks_paths), is_last_stage=False, use_interval=False):
                yield line
        
        # 6. 执行阶段二：同步元数据
        if meta_tasks_paths:
            msg = f"第二阶段：开始同步 {len(meta_tasks_paths)} 个元数据文件..."
            log_audit("STRM", "阶段开始", msg)
            yield json.dumps({"type": "info", "message": msg}) + "\n"
            
            # 最后一个阶段 is_last_stage=True (默认值)，引擎会负责清理冗余文件和发送完成通知
            # 元数据同步使用限流，use_interval=True (默认)
            engine.all_valid_rel_paths = all_valid_rel_paths
            async for line in engine.run(ListScanner(meta_tasks_paths), is_last_stage=True, use_interval=True):
                yield line
        else:
            # 如果没有元数据任务，我们也需要收尾（清理和通知）
            if strm_tasks_paths:
                engine.all_valid_rel_paths = all_valid_rel_paths
                # 运行一个空扫描器来触发 finalize 逻辑
                async for line in engine.run(ListScanner([]), is_last_stage=True):
                    yield line
            else:
                # 没有任何任务
                duration = time.time() - start_time
                stats["duration"] = f"{duration:.1f}s"
                yield json.dumps({"type": "finish", "stats": stats}) + "\n"
