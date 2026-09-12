import logging
from typing import Dict, Any, List

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
