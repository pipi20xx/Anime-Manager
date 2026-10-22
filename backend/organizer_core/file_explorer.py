import os
import time
import shutil
import logging
from fnmatch import fnmatch
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)

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
        try:
            from config_manager import ConfigManager
            roots = ConfigManager.get_config().get("organizer_allowed_roots") or []
        except Exception:
            roots = []
        if not roots:
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

    # ---- 复制到 / 移动到（对齐 CD2 的同名冲突策略）----
    CONFLICT_OVERWRITE = 0
    CONFLICT_RENAME = 1
    CONFLICT_SKIP = 2

    @staticmethod
    def _normalize(path: str) -> str:
        return os.path.abspath(os.path.expanduser((path or "").strip()))

    @staticmethod
    def _unique_dest(dst: str, is_dir: bool) -> str:
        """生成不冲突的目标名：name.ext -> name (1).ext"""
        parent = os.path.dirname(dst)
        base = os.path.basename(dst)
        stem, ext = (base, "") if is_dir else os.path.splitext(base)
        i = 1
        while True:
            candidate = os.path.join(parent, f"{stem} ({i}){ext}")
            if not os.path.exists(candidate):
                return candidate
            i += 1

    @staticmethod
    def _resolve_conflict(dst: str, is_dir: bool, conflict_policy: int) -> Optional[str]:
        """目标已存在时按策略处理；返回最终目标路径，None 表示跳过"""
        if not os.path.exists(dst):
            return dst
        if conflict_policy == FileExplorer.CONFLICT_SKIP:
            return None
        if conflict_policy == FileExplorer.CONFLICT_OVERWRITE:
            if os.path.isdir(dst) and not os.path.islink(dst):
                shutil.rmtree(dst)
            else:
                os.remove(dst)
            return dst
        return FileExplorer._unique_dest(dst, is_dir)

    @staticmethod
    def transfer_item(src: str, dest_dir: str, action: str = "move",
                      conflict_policy: int = 1) -> Dict[str, Any]:
        """
        把 src 复制/移动到 dest_dir 下（保持原名），支持同名冲突策略。
        :param action: "move" 或 "copy"
        :param conflict_policy: 0=覆盖 1=自动重命名 2=跳过（默认自动重命名）
        """
        if action not in ("move", "copy"):
            raise ValueError(f"不支持的操作类型: {action}")

        src = FileExplorer._normalize(src)
        dest_dir = FileExplorer._normalize(dest_dir)
        FileExplorer._ensure_allowed(src, dest_dir)

        if not os.path.exists(src):
            raise FileNotFoundError(f"源路径不存在: {src}")
        if os.path.dirname(src) == src:
            raise ValueError("不能对根目录执行此操作")
        if not os.path.isdir(dest_dir):
            raise NotADirectoryError(f"目标目录不存在: {dest_dir}")

        is_dir = os.path.isdir(src)
        # 目录不能复制/移动进自身或其子目录
        if is_dir and (dest_dir == src or dest_dir.startswith(src + os.sep)):
            raise ValueError("目标目录不能是源目录本身或其子目录")

        dst = os.path.join(dest_dir, os.path.basename(src))
        if dst == src:
            raise ValueError("源路径与目标路径相同")

        final_dst = FileExplorer._resolve_conflict(dst, is_dir, conflict_policy)
        if final_dst is None:
            return {"status": "skipped", "src": src, "dst": dst,
                    "message": "目标已存在同名项，已跳过"}

        if action == "copy":
            if is_dir:
                shutil.copytree(src, final_dst)
            else:
                shutil.copy2(src, final_dst)
        else:
            shutil.move(src, final_dst)

        verb = "复制" if action == "copy" else "移动"
        logger.info(f"[FileExplorer] {verb}: {src} -> {final_dst}")
        return {"status": "success", "src": src, "dst": final_dst, "message": f"已{verb}"}

    @staticmethod
    def rename_item(path: str, new_name: str) -> Dict[str, Any]:
        """在同一目录内重命名（new_name 只能是名称，不能含路径分隔符）"""
        path = FileExplorer._normalize(path)
        FileExplorer._ensure_allowed(path)

        if not os.path.exists(path):
            raise FileNotFoundError(f"路径不存在: {path}")
        if os.path.dirname(path) == path:
            raise ValueError("不能重命名根目录")

        new_name = (new_name or "").strip()
        if not new_name:
            raise ValueError("新名称不能为空")
        if new_name in (".", "..") or os.sep in new_name or (os.altsep and os.altsep in new_name):
            raise ValueError("新名称不能包含路径分隔符")

        dst = os.path.join(os.path.dirname(path), new_name)
        if dst == path:
            return {"status": "success", "src": path, "dst": path, "message": "名称未变化"}
        if os.path.exists(dst):
            raise FileExistsError(f"同名文件或文件夹已存在: {new_name}")

        os.rename(path, dst)
        logger.info(f"[FileExplorer] 重命名: {path} -> {dst}")
        return {"status": "success", "src": path, "dst": dst, "message": "已重命名"}

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

    # 判定"实际为空"时默认忽略的系统垃圾文件/目录
    _BUILTIN_IGNORED = {'.DS_Store', 'Thumbs.db', '@eaDir'}

    @staticmethod
    def _is_ignored(name: str, ignore_patterns: List[str]) -> bool:
        """判断文件/目录名是否属于"不算内容"的忽略项（内置系统垃圾 + 自定义通配符规则）"""
        if name in FileExplorer._BUILTIN_IGNORED or name.startswith('._'):
            return True
        return any(fnmatch(name, pat.strip()) for pat in ignore_patterns if pat and pat.strip())

    @staticmethod
    def _find_empty_dirs(path: str, ignore_patterns: List[str]) -> List[Dict[str, Any]]:
        """
        自底向上找出 path 子树中所有"实际为空"的目录（不含 path 本身）。
        空目录内允许只包含忽略项（如 .DS_Store、@eaDir、匹配自定义规则的文件），
        这些忽略项会随目录一并清理；只含空子目录的父目录同样视为空。
        """
        results: List[Dict[str, Any]] = []
        empty_set = set()
        for root, dirs, files in os.walk(path, topdown=False):
            if os.path.abspath(root) == os.path.abspath(path):
                continue
            try:
                entries = os.listdir(root)
            except OSError:
                continue
            junk, remaining = [], 0
            for e in entries:
                if FileExplorer._is_ignored(e, ignore_patterns):
                    junk.append(e)
                elif os.path.join(root, e) in empty_set:
                    continue
                else:
                    remaining += 1
            if remaining == 0:
                empty_set.add(os.path.abspath(root))
                results.append({
                    "path": root,
                    "name": os.path.basename(root) or root,
                    "junk_files": junk,
                })
        return results

    @staticmethod
    def scan_empty_dirs(path: str, ignore_patterns: Optional[List[str]] = None) -> Dict[str, Any]:
        """扫描目录子树中所有"实际为空"的文件夹（预览用，不做任何修改）"""
        FileExplorer._ensure_allowed(path)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Path not found: {path}")
        if not os.path.isdir(path):
            raise NotADirectoryError(f"Path is not a directory: {path}")

        patterns = [p for p in (ignore_patterns or []) if str(p).strip()]
        items = FileExplorer._find_empty_dirs(path, patterns)
        return {"count": len(items), "items": items}

    @staticmethod
    def clean_empty_dirs(path: str, ignore_patterns: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        清理目录子树中所有"实际为空"的文件夹。
        每个目录删除前重新校验（防止扫描后有新文件写入），先删忽略项再 rmdir，
        单个目录失败不影响其余；path 本身永远不会被删除。
        """
        FileExplorer._ensure_allowed(path)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Path not found: {path}")
        if not os.path.isdir(path):
            raise NotADirectoryError(f"Path is not a directory: {path}")

        patterns = [p for p in (ignore_patterns or []) if str(p).strip()]
        candidates = FileExplorer._find_empty_dirs(path, patterns)

        deleted: List[str] = []
        failed: List[Dict[str, str]] = []
        deleted_set = set()
        for item in candidates:
            d = item["path"]
            try:
                entries = os.listdir(d)
                removable, ok = [], True
                for e in entries:
                    full = os.path.join(d, e)
                    if FileExplorer._is_ignored(e, patterns):
                        removable.append(e)
                    elif full in deleted_set:
                        continue
                    else:
                        ok = False
                        break
                if not ok:
                    failed.append({"path": d, "error": "目录包含未忽略的内容，已跳过"})
                    continue
                for e in removable:
                    full = os.path.join(d, e)
                    if os.path.isdir(full) and not os.path.islink(full):
                        shutil.rmtree(full)
                    else:
                        os.remove(full)
                os.rmdir(d)
                deleted_set.add(d)
                deleted.append(d)
            except OSError as e:
                failed.append({"path": d, "error": str(e)})

        return {"count": len(deleted), "deleted": deleted, "failed": failed}

    # ---------- 批量按扩展名删除文件 ----------

    # 预览列表最多返回的条目数（实际删除不受此限制）
    BATCH_DELETE_PREVIEW_LIMIT = 2000

    @staticmethod
    def _normalize_extensions(extensions: Optional[List[str]]) -> List[str]:
        """
        归一化扩展名列表，兼容多种写法：
        '.jpg' / 'jpg' / 'JPG' / '*.jpg' → '.jpg'；多项可用 ; , ， ； 分隔。
        '*' / '.*' / 'all' → '*'（匹配所有文件）。返回空列表表示"不限制扩展名"。
        """
        result: List[str] = []
        for raw in (extensions or []):
            text = str(raw).replace('；', ';').replace('，', ',').replace(',', ';')
            for part in text.split(';'):
                ext = part.strip().lower()
                if not ext:
                    continue
                if ext in ('*', '.*', 'all'):
                    ext = '*'
                elif ext.startswith('*.'):
                    ext = ext[1:]
                elif not ext.startswith('.'):
                    ext = '.' + ext
                if ext not in result:
                    result.append(ext)
        return result

    @staticmethod
    def _extension_matches(name: str, extensions: List[str]) -> bool:
        """文件名是否命中扩展名规则；extensions 为空视为命中所有文件"""
        if not extensions:
            return True
        lower = name.lower()
        return any(lower.endswith(ext) or fnmatch(lower, ext) for ext in extensions)

    @staticmethod
    def _should_delete_file(name: str, delete_exts: List[str], exclude_exts: List[str]) -> bool:
        """
        判定文件是否应被批量删除。
        优先级：不想删除的扩展名（exclude）> 要删除的扩展名（delete）。
        """
        if exclude_exts and FileExplorer._extension_matches(name, exclude_exts):
            return False
        return FileExplorer._extension_matches(name, delete_exts)

    @staticmethod
    def _iter_matching_files(path: str, delete_exts: List[str], exclude_exts: List[str], recursive: bool = True):
        """生成器：产出目录（可含子目录）中所有命中规则的文件 (full_path, name, size, mtime)"""
        if recursive:
            for root, _dirs, files in os.walk(path):
                for name in files:
                    if not FileExplorer._should_delete_file(name, delete_exts, exclude_exts):
                        continue
                    full = os.path.join(root, name)
                    try:
                        st = os.stat(full)
                    except OSError:
                        continue
                    yield full, name, st.st_size, st.st_mtime
            return

        try:
            entries = list(os.scandir(path))
        except OSError:
            return
        for entry in entries:
            try:
                if not entry.is_file():
                    continue
            except OSError:
                continue
            if not FileExplorer._should_delete_file(entry.name, delete_exts, exclude_exts):
                continue
            try:
                st = entry.stat()
            except OSError:
                continue
            yield entry.path, entry.name, st.st_size, st.st_mtime

    @staticmethod
    def scan_files_by_ext(path: str, delete_extensions: Optional[List[str]] = None,
                          exclude_extensions: Optional[List[str]] = None,
                          recursive: bool = True) -> Dict[str, Any]:
        """
        扫描目录（可含子目录）中符合扩展名规则的文件，仅预览不删除。
        规则：delete_extensions 为空=所有文件；exclude_extensions 优先，命中则永不删除。
        """
        FileExplorer._ensure_allowed(path)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Path not found: {path}")
        if not os.path.isdir(path):
            raise NotADirectoryError(f"Path is not a directory: {path}")

        delete_exts = FileExplorer._normalize_extensions(delete_extensions)
        exclude_exts = FileExplorer._normalize_extensions(exclude_extensions)

        limit = FileExplorer.BATCH_DELETE_PREVIEW_LIMIT
        items: List[Dict[str, Any]] = []
        count = 0
        total_size = 0
        for full, name, size, mtime in FileExplorer._iter_matching_files(path, delete_exts, exclude_exts, recursive):
            count += 1
            total_size += size
            if len(items) < limit:
                items.append({"path": full, "name": name, "size": size, "mtime": mtime})

        return {
            "count": count,
            "items": items,
            "total_size": total_size,
            "truncated": count > len(items),
            "preview_limit": limit,
        }

    @staticmethod
    def delete_files_by_ext(path: str, delete_extensions: Optional[List[str]] = None,
                            exclude_extensions: Optional[List[str]] = None,
                            recursive: bool = True) -> Dict[str, Any]:
        """
        批量删除目录（可含子目录）中符合扩展名规则的文件。
        只删文件、不动文件夹；每个文件删除前重新校验规则与存在性（防扫描后变动）；
        单个文件失败不影响其余。
        """
        FileExplorer._ensure_allowed(path)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Path not found: {path}")
        if not os.path.isdir(path):
            raise NotADirectoryError(f"Path is not a directory: {path}")

        delete_exts = FileExplorer._normalize_extensions(delete_extensions)
        exclude_exts = FileExplorer._normalize_extensions(exclude_extensions)

        deleted: List[str] = []
        failed: List[Dict[str, str]] = []
        freed = 0
        for full, _name, size, _mtime in FileExplorer._iter_matching_files(path, delete_exts, exclude_exts, recursive):
            try:
                # 重新校验：扫描后文件可能已被删除/改名
                if not os.path.isfile(full):
                    continue
                if not FileExplorer._should_delete_file(os.path.basename(full), delete_exts, exclude_exts):
                    continue
                os.remove(full)
                deleted.append(full)
                freed += size
            except OSError as e:
                failed.append({"path": full, "error": str(e)})

        return {"count": len(deleted), "deleted": deleted, "failed": failed, "freed_bytes": freed}
