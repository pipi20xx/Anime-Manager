import os
import json
import asyncio
import time
from typing import Dict, Any, AsyncGenerator, List, Set

from .engine import StrmTaskEngine
from .scanners import TreeFileScanner, ListScanner
from .constants import VIDEO_EXTENSIONS, META_EXTENSIONS
from logger import log_audit
from notification import NotificationManager

class TreeSyncManager:
    """
    专门负责基于文本目录树文件的同步管理器
    支持两阶段处理：先 STRM，后元数据
    """
    @staticmethod
    async def generate_via_tree(config: Dict[str, Any]) -> AsyncGenerator[str, None]:
        start_time = time.time()
        tree_file = config.get("tree_file_path")
        source_dir = os.path.normpath(config.get("source_dir") or config.get("source_path") or "")
        
        if not tree_file or not os.path.exists(tree_file):
            yield json.dumps({"type": "error", "message": f"目录树文件不存在: {tree_file}"}) + "\n"
            return

        yield json.dumps({"type": "info", "message": f"正在解析目录树文件: {os.path.basename(tree_file)}"}) + "\n"
        log_audit("STRM", "目录树解析", f"文件: {tree_file}")

        # 1. 预解析获取所有相对路径
        # 复用 TreeFileScanner 的静态解析方法
        rel_paths = await asyncio.to_thread(TreeFileScanner._parse_tree, tree_file)
        
        # 2. 任务分拣
        video_exts = set(config.get("target_extensions") or VIDEO_EXTENSIONS)
        meta_exts = set(config.get("meta_extensions") or META_EXTENSIONS)
        copy_meta = config.get("copy_meta", False)
        
        strm_list = []
        meta_list = []
        all_valid_rel_paths = set()
        
        for rel in rel_paths:
            ext = os.path.splitext(rel)[1].lower()
            abs_path = os.path.join(source_dir, rel)
            
            if ext in video_exts:
                strm_list.append(abs_path)
                # 记录 STRM 的目标路径用于后续冗余清理
                strm_rel = os.path.splitext(rel)[0] + ".strm"
                all_valid_rel_paths.add(os.path.normpath(strm_rel))
            elif copy_meta and ext in meta_exts:
                meta_list.append(abs_path)
                all_valid_rel_paths.add(os.path.normpath(rel))

        # 3. 初始化引擎和统计
        stats = {
            "strm_created": 0, "strm_skipped": 0, 
            "meta_copied": 0, "meta_skipped": 0, 
            "deleted": 0, "errors": 0
        }
        engine = StrmTaskEngine(config, stats=stats)
        engine.all_valid_rel_paths = all_valid_rel_paths

        # 4. 执行阶段一：STRM
        if strm_list:
            msg = f"第一阶段：开始生成 {len(strm_list)} 个 STRM 文件..."
            log_audit("STRM", "阶段开始", msg)
            yield json.dumps({"type": "info", "message": msg}) + "\n"
            # STRM 生成不限流，use_interval=False
            async for line in engine.run(ListScanner(strm_list), is_last_stage=False, use_interval=False):
                yield line
        
        # 5. 执行阶段二：元数据
        if meta_list:
            msg = f"第二阶段：开始同步 {len(meta_list)} 个元数据文件..."
            log_audit("STRM", "阶段开始", msg)
            yield json.dumps({"type": "info", "message": msg}) + "\n"
            # 元数据同步使用限流，use_interval=True (默认)
            async for line in engine.run(ListScanner(meta_list), is_last_stage=True, use_interval=True):
                yield line
        else:
            # 即使没有元数据任务，也要执行收尾（清理冗余和发送通知）
            async for line in engine.run(ListScanner([]), is_last_stage=True):
                yield line
