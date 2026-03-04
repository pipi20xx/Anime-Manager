import os
import json
import asyncio
from typing import AsyncGenerator, Dict, Any

from .processor import StrmProcessor
from .engine import StrmTaskEngine
from .scanners import LocalScanner, ListScanner
from .tree_sync_manager import TreeSyncManager

class StrmGenerator:
    @staticmethod
    def calculate_strm_content(source_root: str, file_abs_path: str, config: Dict[str, Any]) -> str:
        """保持向前兼容"""
        return StrmProcessor.calculate_strm_content(source_root, file_abs_path, config)

    @staticmethod
    async def process_single_file(file_path: str, task_config: Dict[str, Any]) -> Dict[str, Any]:
        """保持向前兼容"""
        return await StrmProcessor.process_single_file(file_path, task_config)

    @staticmethod
    async def run_task_background(config: Dict[str, Any]):
        """后台异步执行任务封装"""
        async for _ in StrmGenerator.generate(config):
            pass

    @staticmethod
    async def generate(config: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """
        主生成器入口：负责任务路由分发
        """
        sync_mode = config.get("sync_mode", "full") 

        # 方案 A: 目录树文件模式
        if sync_mode == "tree_file":
            async for line in TreeSyncManager.generate_via_tree(config):
                yield line
            return

        # 方案 B: 显式列表模式
        if sync_mode == "list" and "file_list" in config:
            engine = StrmTaskEngine(config)
            async for line in engine.run(ListScanner(config["file_list"])):
                yield line
            return

        # 方案 C: 默认全量扫描模式
        source_dir = os.path.normpath(config.get("source_dir") or config.get("source_path") or "")
        engine = StrmTaskEngine(config)
        scanner = LocalScanner(source_dir)
        async for line in engine.run(scanner):
            yield line
