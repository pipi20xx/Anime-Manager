import os
import asyncio
import threading
import unicodedata
from typing import List, Dict, Any, Optional, Callable

class LocalScanner:
    """
    本地目录深度扫描器 (使用 os.scandir 优化性能)
    """
    def __init__(self, source_dir: str):
        self.source_dir = os.path.normpath(source_dir)
        self.api_calls = 0  # API 调用计数器

    def _walk_recursive(self, dir_path: str, queue_put_func):
        """
        使用 os.scandir 递归遍历目录
        性能提升：2-3 倍（相比 os.walk）
        """
        self.api_calls += 1  # 每次 scandir 计为 1 次 API 调用
        
        try:
            with os.scandir(dir_path) as entries:
                dirs = []
                for entry in entries:
                    name = entry.name
                    
                    if name.startswith('.'):
                        continue
                    
                    if entry.is_dir(follow_symlinks=False):
                        dirs.append(name)
                    elif entry.is_file(follow_symlinks=False):
                        file_abs = os.path.join(dir_path, name)
                        queue_put_func(file_abs)
        except (PermissionError, OSError):
            pass
        
        return dirs

    async def __call__(self, queue: asyncio.Queue):
        if not os.path.exists(self.source_dir):
            await queue.put(Exception(f"源目录不存在: {self.source_dir}"))
            await queue.put(None)
            return

        loop = asyncio.get_event_loop()

        def producer():
            try:
                should_stop = False

                def queue_put(file_path):
                    try:
                        future = asyncio.run_coroutine_threadsafe(queue.put(file_path), loop)
                        future.result()
                    except:
                        nonlocal should_stop
                        should_stop = True
                
                def walk_recursive_wrapper(dir_path):
                    if should_stop:
                        return
                    dirs = self._walk_recursive(dir_path, queue_put)
                    for d in dirs:
                        if should_stop:
                            break
                        walk_recursive_wrapper(os.path.join(dir_path, d))
                
                walk_recursive_wrapper(self.source_dir)
                
                # 输出 API 调用统计
                from logger import log_audit
                log_audit("STRM", "扫描统计", 
                         f"扫描完成，共调用 {self.api_calls} 次 API (os.scandir)", 
                         level="INFO")
                
                asyncio.run_coroutine_threadsafe(queue.put(None), loop).result()
            except Exception as e:
                asyncio.run_coroutine_threadsafe(queue.put(e), loop)

        threading.Thread(target=producer, daemon=True).start()

class ListScanner:
    """
    显式列表扫描器
    直接处理传入的文件路径列表
    """
    def __init__(self, file_paths: List[str]):
        self.file_paths = file_paths

    async def __call__(self, queue: asyncio.Queue):
        for path in self.file_paths:
            await queue.put(path)
        await queue.put(None)

class FolderScanner:
    """
    特定单层目录扫描器
    """
    def __init__(self, folder_path: str, recursive: bool = False):
        self.folder_path = folder_path
        self.recursive = recursive

    async def __call__(self, queue: asyncio.Queue):
        if not os.path.exists(self.folder_path):
            await queue.put(None)
            return
            
        if not self.recursive:
            for f in os.listdir(self.folder_path):
                if f.startswith('.'): continue
                p = os.path.join(self.folder_path, f)
                if os.path.isfile(p):
                    await queue.put(p)
            await queue.put(None)
        else:
            await LocalScanner(self.folder_path)(queue)

class TreeFileScanner:
    """
    基于文本目录树文件的扫描器 (例如从 CD2/tree 命令生成的 txt)
    """
    def __init__(self, tree_file_path: str, source_root: str):
        self.tree_file_path = tree_file_path
        self.source_root = source_root

    @staticmethod
    def _parse_tree(file_path: str) -> List[str]:
        if not os.path.exists(file_path):
            return []

        try:
            with open(file_path, 'r', encoding='utf-16') as f:
                lines = f.readlines()
        except Exception:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
            except Exception:
                return []

        paths = []
        stack = []
        
        for line in lines:
            line = line.rstrip()
            if not line: continue
            
            last_pipe_idx = line.rfind('|')
            if last_pipe_idx == -1: continue
            
            depth = last_pipe_idx // 2
            dash_idx = line.find('—', last_pipe_idx)
            if dash_idx == -1:
                dash_idx = line.find('-', last_pipe_idx)
            
            if dash_idx == -1: continue
            
            if line[dash_idx:dash_idx+2] == '——':
                name = line[dash_idx+2:].strip()
            else:
                name = line[dash_idx+1:].strip()
            
            if not name: continue

            while len(stack) > depth:
                stack.pop()
            
            stack.append(name)
            
            if '.' in name:
                # 恢复跳过根节点的逻辑：
                # 如果树是 |——长篇系列/海贼王/1.mp4，且 source_root 是 /.../长篇系列
                # 则我们需要相对路径为 海贼王/1.mp4 (即去掉 stack[0])
                if len(stack) > 1:
                    rel_path = os.path.join(*stack[1:])
                    paths.append(rel_path)
                
        return paths

    async def __call__(self, queue: asyncio.Queue):
        rel_paths = await asyncio.to_thread(self._parse_tree, self.tree_file_path)
        for rel in rel_paths:
            abs_path = os.path.join(self.source_root, rel)
            await queue.put(abs_path)
        await queue.put(None)