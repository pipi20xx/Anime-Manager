import logging
import os
import posixpath
from typing import Dict, Any, List, Optional

from logger import log_audit

logger = logging.getLogger(__name__)

# MoveFileRequest/CopyFileRequest.ConflictPolicy: Overwrite=0; Rename=1; Skip=2
_CONFLICT_POLICY = {0: "Overwrite", 1: "Rename", 2: "Skip"}


class CD2FileBrowser:
    """
    CD2 文件浏览与文件操作（直接使用 CD2 内部路径，不做本地路径转换）。
    与 file_ops.py（面向本地挂载路径的整理操作）分开。
    """
    def __init__(self, connection):
        self.connection = connection

    def list_dir(self, path: str = "/", force_refresh: bool = False) -> Dict[str, Any]:
        """
        列出目录内容 (GetSubFiles, 服务器流式)。
        返回条目: name / path / is_dir / size / write_time / is_forbidden
        """
        conn = self.connection
        entries: List[Dict[str, Any]] = []
        try:
            req = conn.pb2.ListSubFileRequest(path=path or "/", forceRefresh=force_refresh)
            call = conn.stub.GetSubFiles(req, metadata=conn.get_metadata(), timeout=60)
            for reply in call:
                if not reply.subFiles:
                    continue
                for f in reply.subFiles:
                    entries.append({
                        "name": f.name,
                        "path": f.fullPathName or f.path or f"/{f.name}",
                        "is_dir": bool(f.isDirectory) or int(f.fileType) == 0,
                        "size": int(f.size),
                        "write_time": int(f.writeTime.seconds) if f.HasField("writeTime") else 0,
                        "is_forbidden": bool(f.isForbidden),
                        "can_offline_download": bool(getattr(f, "canOfflineDownload", False)),
                        "cloud_name": f.CloudAPI.name,
                        "cloud_user": f.CloudAPI.userName,
                    })

            # 目录在前，同名按名称排序
            entries.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
            # 当前目录是否支持离线下载（子项具备该能力即视为支持）
            can_offline = any(e["can_offline_download"] for e in entries)
            return {"success": True, "path": path or "/", "entries": entries, "total": len(entries), "can_offline": can_offline}
        except Exception as e:
            details = getattr(e, "details", None) or str(e)
            logger.error(f"[{conn.name}] CD2 列目录失败 {path}: {details}")
            return {"success": False, "message": details, "entries": [], "total": 0}

    def create_folder(self, parent_path: str, name: str) -> tuple:
        """新建文件夹 (CreateFolder，结果嵌套在 result 中)"""
        conn = self.connection
        try:
            req = conn.pb2.CreateFolderRequest(parentPath=parent_path, folderName=name)
            resp = conn.stub.CreateFolder(req, metadata=conn.get_metadata(), timeout=60)
            if resp.result.success:
                log_audit("CD2文件", "新建文件夹", f"{parent_path}/{name}")
                return True, "Success"
            return False, resp.result.errorMessage or "创建失败"
        except Exception as e:
            details = getattr(e, "details", None) or str(e)
            logger.error(f"[{conn.name}] CD2 新建文件夹异常: {details}")
            return False, details

    def rename(self, path: str, new_name: str) -> tuple:
        """重命名文件/文件夹 (RenameFile)"""
        conn = self.connection
        try:
            req = conn.pb2.RenameFileRequest(theFilePath=path, newName=new_name)
            resp = conn.stub.RenameFile(req, metadata=conn.get_metadata(), timeout=60)
            if resp.success:
                log_audit("CD2文件", "重命名", f"{path} -> {new_name}")
                return True, "Success"
            return False, resp.errorMessage or "重命名失败"
        except Exception as e:
            details = getattr(e, "details", None) or str(e)
            logger.error(f"[{conn.name}] CD2 重命名异常: {details}")
            return False, details

    def delete_files(self, paths: List[str]) -> tuple:
        """批量删除文件/文件夹 (DeleteFiles，删除到回收站)"""
        conn = self.connection
        try:
            req = conn.pb2.MultiFileRequest(path=paths)
            resp = conn.stub.DeleteFiles(req, metadata=conn.get_metadata(), timeout=120)
            if resp.success:
                log_audit("CD2文件", "删除", f"删除 {len(paths)} 个文件/文件夹")
                return True, "Success"
            return False, resp.errorMessage or "删除失败"
        except Exception as e:
            details = getattr(e, "details", None) or str(e)
            logger.error(f"[{conn.name}] CD2 删除文件异常: {details}")
            return False, details

    def upload_file(self, parent_path: str, file_name: str, data: bytes) -> tuple:
        """
        上传文件到指定目录 (CreateFile + WriteToFile 分块写入)。
        参考 CD2 官方示例：CreateFile 取 fileHandle，分块 WriteToFile，
        最后一块 closeFile=True 关闭句柄；异常时 CloseFile 清理。
        """
        conn = self.connection
        chunk_size = 1024 * 1024  # 1MB
        handle = None
        try:
            create_req = conn.pb2.CreateFileRequest(parentPath=parent_path, fileName=file_name)
            create_resp = conn.stub.CreateFile(create_req, metadata=conn.get_metadata(), timeout=60)
            handle = create_resp.fileHandle

            total = len(data)
            pos = 0
            while True:
                chunk = data[pos:pos + chunk_size]
                is_last = (pos + len(chunk)) >= total
                write_req = conn.pb2.WriteFileRequest(
                    fileHandle=handle,
                    startPos=pos,
                    length=len(chunk),
                    buffer=chunk,
                    closeFile=is_last,
                )
                conn.stub.WriteToFile(write_req, metadata=conn.get_metadata(), timeout=120)
                pos += len(chunk)
                if is_last:
                    handle = None  # 已随最后一块关闭
                    break

            log_audit("CD2文件", "上传", f"上传文件: {parent_path}/{file_name} ({total} 字节)")
            return True, "Success"
        except Exception as e:
            details = getattr(e, "details", None) or str(e)
            logger.error(f"[{conn.name}] CD2 上传文件异常: {details}")
            # 异常时尽力关闭句柄，避免句柄泄漏
            if handle:
                try:
                    conn.stub.CloseFile(conn.pb2.CloseFileRequest(fileHandle=handle),
                                        metadata=conn.get_metadata(), timeout=15)
                except Exception:
                    pass
            return False, details

    def walk_files(self, root: str, video_exts: Optional[List[str]] = None, ignore_regex=None) -> List[Dict[str, Any]]:
        """
        递归遍历云目录（BFS），产出文件列表。
        供整理任务扫描云源使用：与本地 _walk_recursive 语义对齐——
        video_exts 白名单过滤扩展名，ignore_regex 对文件名/目录名做 re.search。
        返回 [{path, name, size}]。
        """
        import re as _re

        conn = self.connection
        files: List[Dict[str, Any]] = []
        queue = ["/" + (root or "/").strip("/")]
        visited = set()

        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)

            try:
                result = self.list_dir(current)
                entries = result.get("entries", [])
            except Exception as e:
                logger.warning(f"[{conn.name}] 遍历目录失败 {current}: {e}")
                continue

            for entry in entries:
                name = entry["name"]
                if entry["is_dir"]:
                    if ignore_regex and any(_re.search(p, name, _re.I) for p in ignore_regex):
                        continue
                    queue.append(entry["path"])
                else:
                    if video_exts:
                        ext = os.path.splitext(name)[1].lower()
                        if ext not in video_exts:
                            continue
                    if ignore_regex and any(_re.search(p, name, _re.I) for p in ignore_regex):
                        continue
                    files.append({
                        "path": entry["path"],
                        "name": name,
                        "size": entry.get("size", 0),
                    })
        return files

    def path_exists(self, path: str, force_refresh: bool = False) -> bool:
        """检查云路径是否存在（列出父目录按名称匹配）。
        force_refresh=True 时绕过 CD2 目录缓存，强制拉取云端实时列表。"""
        conn = self.connection
        normalized = "/" + (path or "").strip("/")
        parent = posixpath.dirname(normalized) or "/"
        name = posixpath.basename(normalized)
        try:
            req = conn.pb2.ListSubFileRequest(path=parent, forceRefresh=force_refresh)
            for reply in conn.stub.GetSubFiles(req, metadata=conn.get_metadata(), timeout=30):
                for f in reply.subFiles:
                    if f.name == name:
                        return True
        except Exception as e:
            logger.debug(f"[{conn.name}] path_exists 检查失败 {normalized}: {e}")
        return False

    def ensure_dir(self, path: str) -> tuple:
        """
        逐级确认目录存在（GetSubFiles 检查 + CreateFolder 兜底，容忍"已存在"错误）。
        参考 organizer executor._ensure_cd2_dir 的语义，但纯 gRPC 实现、不需要挂载。
        """
        conn = self.connection
        normalized = "/" + (path or "").strip("/")
        if normalized == "/":
            return True, "Success"

        parts = [p for p in normalized.split("/") if p]
        current = ""
        for part in parts:
            parent = current or "/"
            current = f"{current}/{part}"

            exists = False
            try:
                req = conn.pb2.ListSubFileRequest(path=parent, forceRefresh=False)
                for reply in conn.stub.GetSubFiles(req, metadata=conn.get_metadata(), timeout=30):
                    for f in reply.subFiles:
                        if f.name == part and (bool(f.isDirectory) or int(f.fileType) == 0):
                            exists = True
                            break
                    if exists:
                        break
            except Exception as e:
                logger.debug(f"[{conn.name}] 检查目录 {current} 失败，将尝试直接创建: {e}")

            if exists:
                continue

            try:
                req = conn.pb2.CreateFolderRequest(parentPath=parent, folderName=part)
                resp = conn.stub.CreateFolder(req, metadata=conn.get_metadata(), timeout=60)
                if not resp.result.success:
                    err = resp.result.errorMessage or ""
                    if "already exists" in err.lower() or "conflict" in err.lower():
                        continue
                    return False, f"创建目录 {current} 失败: {err}"
            except Exception as e:
                details = getattr(e, "details", None) or str(e)
                return False, f"创建目录 {current} 失败: {details}"

        return True, "Success"

    def organize_rename(self, path: str, new_relative_path: str, conflict_policy: int = 1) -> tuple:
        """
        识别后的整理式重命名：目标相对路径可含子目录。
        步骤（同 organizer executor 的 cd2_move 顺序）：
        1. ensure_dir 创建目标子目录
        2. 原位重命名为新文件名
        3. 移动到目标子目录（无子目录变化时跳过）
        返回 (success, final_path_or_error)
        """
        conn = self.connection
        try:
            source_dir = posixpath.dirname(path) or "/"
            target_abs = posixpath.normpath(posixpath.join(source_dir, new_relative_path.strip("/")))
            target_dir = posixpath.dirname(target_abs) or "/"
            new_name = posixpath.basename(target_abs)

            # 1. 逐级创建目标目录
            ok, msg = self.ensure_dir(target_dir)
            if not ok:
                return False, msg

            # 2. 原位重命名（名字相同则跳过）
            current_path = path
            if new_name != posixpath.basename(path):
                ok, msg = self.rename(path, new_name)
                if not ok:
                    return False, msg
                current_path = f"{source_dir.rstrip('/')}/{new_name}"

            # 3. 移动到目标目录（目录未变化则跳过）
            final_path = current_path
            if target_dir != source_dir:
                req = conn.pb2.MoveFileRequest(
                    theFilePaths=[current_path],
                    destPath=target_dir,
                    conflictPolicy=_CONFLICT_POLICY.get(conflict_policy, "Rename"),
                )
                resp = conn.stub.MoveFile(req, metadata=conn.get_metadata(), timeout=120)
                if not resp.success:
                    return False, f"移动失败: {resp.errorMessage or '未知错误'}"
                final_path = f"{target_dir.rstrip('/')}/{new_name}"

            log_audit("CD2文件", "识别重命名", f"{path} -> {final_path}")
            return True, final_path
        except Exception as e:
            details = getattr(e, "details", None) or str(e)
            logger.error(f"[{conn.name}] CD2 识别重命名异常: {details}")
            return False, details

    def get_cloud_file_size(self, cloud_path: str) -> int:
        """
        获取云文件大小。
        注意: GetFileDetailProperties.totalSize 对单个文件返回的值不可靠（实测偏差），
        因此优先用父目录列表 (GetSubFiles) 的 size，FileDetailProperties 仅作兜底。
        """
        conn = self.connection
        try:
            parent = posixpath.dirname(cloud_path) or "/"
            name = posixpath.basename(cloud_path)
            normalized = "/" + cloud_path.strip("/")
            result = self.list_dir(parent)
            for entry in result.get("entries", []):
                if entry["path"] == normalized or entry["name"] == name:
                    return int(entry.get("size", 0))
        except Exception as e:
            logger.debug(f"[{conn.name}] 列目录获取大小失败 {cloud_path}: {e}")

        try:
            req = conn.pb2.FileRequest(path=cloud_path)
            props = conn.stub.GetFileDetailProperties(req, metadata=conn.get_metadata(), timeout=30)
            if props and int(props.totalSize) > 0:
                return int(props.totalSize)
        except Exception as e:
            logger.debug(f"[{conn.name}] GetFileDetailProperties 获取大小失败 {cloud_path}: {e}")
        return 0

    def open_download_stream(self, cloud_path: str):
        """
        获取云文件的 HTTP 下载流（GetDownloadUrlPath，优先云存储直链）。
        返回 (stream_response, file_size)。使用后由调用方关闭。
        """
        import requests as _requests

        conn = self.connection
        req = conn.pb2.GetDownloadUrlPathRequest(
            path=cloud_path, preview=False, lazy_read=False, get_direct_url=True
        )
        info = conn.stub.GetDownloadUrlPath(req, metadata=conn.get_metadata(), timeout=60)

        headers = {}
        if info.HasField("userAgent") and info.userAgent:
            headers["User-Agent"] = info.userAgent
        for k, v in info.additionalHeaders.items():
            headers[k] = v

        if info.HasField("directUrl") and info.directUrl:
            url = info.directUrl
        else:
            url_path = (info.downloadUrlPath or "")
            url_path = url_path.replace("{SCHEME}", "http").replace("{HOST}", conn.host).replace("{PREVIEW}", "False")
            url = f"http://{conn.host}{url_path}"

        resp = _requests.get(url, headers=headers, stream=True, timeout=(10, 60))
        resp.raise_for_status()
        file_size = int(resp.headers.get("Content-Length", 0) or 0)
        if file_size <= 0:
            file_size = self.get_cloud_file_size(cloud_path)
        return resp, file_size

    def download_file(self, cloud_path: str, local_path: str) -> tuple:
        """
        从 CD2 下载文件到本地路径（免挂载）。
        通过 GetDownloadUrlPath 获取下载地址（优先云存储直链），HTTP 流式写入本地。
        返回 (success, downloaded_bytes_or_error)。
        """
        conn = self.connection
        import requests as _requests

        tmp_path = local_path + ".cd2downloading"
        try:
            req = conn.pb2.GetDownloadUrlPathRequest(
                path=cloud_path, preview=False, lazy_read=False, get_direct_url=True
            )
            info = conn.stub.GetDownloadUrlPath(req, metadata=conn.get_metadata(), timeout=60)

            headers = {}
            if info.HasField("userAgent") and info.userAgent:
                headers["User-Agent"] = info.userAgent
            for k, v in info.additionalHeaders.items():
                headers[k] = v

            if info.HasField("directUrl") and info.directUrl:
                url = info.directUrl
                logger.debug(f"[{conn.name}] 使用云存储直链下载: {cloud_path}")
            else:
                # downloadUrlPath 含 {SCHEME}/{HOST}/{PREVIEW} 占位符，按 gRPC 主机替换
                url_path = (info.downloadUrlPath or "")
                url_path = url_path.replace("{SCHEME}", "http").replace("{HOST}", conn.host).replace("{PREVIEW}", "False")
                url = f"http://{conn.host}{url_path}"
                logger.debug(f"[{conn.name}] 使用 CD2 内置 HTTP 下载: {cloud_path}")

            downloaded = 0
            with _requests.get(url, headers=headers, stream=True, timeout=(10, 60)) as resp:
                resp.raise_for_status()
                with open(tmp_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)

            if downloaded <= 0:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                return False, "下载内容为空"

            os.replace(tmp_path, local_path)
            log_audit("CD2文件", "下载", f"下载到本地: {cloud_path} ({downloaded} 字节)")
            return True, downloaded
        except Exception as e:
            details = getattr(e, "details", None) or str(e)
            logger.error(f"[{conn.name}] CD2 下载文件失败 {cloud_path}: {details}")
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
            return False, details

    def transfer_files(self, paths: List[str], dest_dir: str, action: str = "move", conflict_policy: int = 1) -> tuple:
        """
        移动/复制文件到目标目录 (MoveFile / CopyFile)。
        :param action: "move" 或 "copy"
        :param conflict_policy: 0=覆盖 1=重命名 2=跳过，默认重命名
        """
        conn = self.connection
        try:
            policy = _CONFLICT_POLICY.get(conflict_policy, "Rename")
            if action == "move":
                req = conn.pb2.MoveFileRequest(theFilePaths=paths, destPath=dest_dir, conflictPolicy=policy)
                resp = conn.stub.MoveFile(req, metadata=conn.get_metadata(), timeout=120)
                verb = "移动"
            else:
                req = conn.pb2.CopyFileRequest(theFilePaths=paths, destPath=dest_dir, conflictPolicy=policy)
                resp = conn.stub.CopyFile(req, metadata=conn.get_metadata(), timeout=120)
                verb = "复制"

            if resp.success:
                log_audit("CD2文件", verb, f"{verb} {len(paths)} 个文件 -> {dest_dir} (冲突策略: {policy})")
                return True, "Success"
            return False, resp.errorMessage or f"{verb}失败"
        except Exception as e:
            details = getattr(e, "details", None) or str(e)
            logger.error(f"[{conn.name}] CD2 文件{action}异常: {details}")
            return False, details
