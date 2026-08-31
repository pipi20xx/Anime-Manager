import os
import time
import shutil
import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)

_warned_no_roots = False

class FileItem(BaseModel):
    name: str
    path: str
    is_dir: bool
    size: Optional[int] = None
    mtime: Optional[float] = None
    extension: Optional[str] = None

class FileExplorer:
    @staticmethod
    def _ensure_allowed(*paths: str) -> None:
        """校验路径是否位于配置的允许根目录（organizer_allowed_roots）内；为空时不限制"""
        global _warned_no_roots
        try:
            from config_manager import ConfigManager
            roots = ConfigManager.get_config().get("organizer_allowed_roots") or []
        except Exception:
            roots = []
        if not roots:
            if not _warned_no_roots:
                _warned_no_roots = True
                logger.warning(
                    "未配置 organizer_allowed_roots，文件管理接口可访问任意路径；建议在系统设置中配置允许的根目录"
                )
            return
        allowed = [os.path.realpath(os.path.expanduser(r)) for r in roots if str(r).strip()]
        for p in paths:
            real = os.path.realpath(p)
            if not any(real == r or real.startswith(r + os.sep) for r in allowed):
                raise PermissionError(f"路径不在允许的根目录内: {p}")

    @staticmethod
    def list_directory(path: str) -> Dict[str, Any]:
        """
        列出指定目录下的文件和文件夹。
        :param path: 要浏览的绝对路径
        :return: 包含目录信息和文件列表的字典
        """
        if not path:
            path = "/"

        # 规范化路径
        path = os.path.abspath(path)
        FileExplorer._ensure_allowed(path)

        if not os.path.exists(path):
            raise FileNotFoundError(f"Path not found: {path}")
            
        if not os.path.isdir(path):
            raise NotADirectoryError(f"Path is not a directory: {path}")

        items: List[FileItem] = []
        
        try:
            with os.scandir(path) as it:
                for entry in it:
                    try:
                        stat = entry.stat()
                        is_dir = entry.is_dir()
                        
                        item = FileItem(
                            name=entry.name,
                            path=entry.path,
                            is_dir=is_dir,
                            size=stat.st_size if not is_dir else None,
                            mtime=stat.st_mtime,
                            extension=os.path.splitext(entry.name)[1].lower() if not is_dir else None
                        )
                        items.append(item)
                    except PermissionError:
                        # 忽略无权限访问的文件/目录
                        continue
        except PermissionError:
            raise PermissionError(f"Permission denied accessing: {path}")

        # 排序：文件夹在前，然后按文件名排序
        items.sort(key=lambda x: (not x.is_dir, x.name.lower()))
        
        # 构建面包屑导航所需的父级路径
        parent = os.path.dirname(path)
        
        return {
            "current_path": path,
            "parent_path": parent,
            "items": [item.dict() for item in items]
        }

    @staticmethod
    def delete_item(path: str):
        """删除文件或目录"""
        FileExplorer._ensure_allowed(path)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Path not found: {path}")

        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)

    @staticmethod
    def copy_item(src: str, dst: str):
        """复制文件或目录"""
        FileExplorer._ensure_allowed(src, dst)
        if not os.path.exists(src):
            raise FileNotFoundError(f"Source path not found: {src}")

        # 如果 dst 是一个已存在的目录，shutil.copy2 会把文件拷入该目录
        # 但如果是目录复制，需要 dst 不存在或者使用 copytree
        if os.path.isdir(src):
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)

    @staticmethod
    def move_item(src: str, dst: str):
        """移动/重命名文件或目录"""
        FileExplorer._ensure_allowed(src, dst)
        if not os.path.exists(src):
            raise FileNotFoundError(f"Source path not found: {src}")

        shutil.move(src, dst)

    @staticmethod
    def get_file_info(path: str) -> Dict[str, Any]:
        """获取文件或目录的详细信息"""
        FileExplorer._ensure_allowed(path)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Path not found: {path}")
            
        stat = os.stat(path)
        is_dir = os.path.isdir(path)
        
        return {
            "name": os.path.basename(path),
            "path": path,
            "is_dir": is_dir,
            "size": stat.st_size if not is_dir else None,
            "mtime": stat.st_mtime,
            "ctime": stat.st_ctime,
            "atime": stat.st_atime,
            "extension": os.path.splitext(path)[1].lower() if not is_dir else None,
            "mode": oct(stat.st_mode)
        }
