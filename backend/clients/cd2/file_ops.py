import os
import logging
from typing import List, Tuple

from logger import log_audit

logger = logging.getLogger(__name__)


class CD2FileOps:
    """
    CD2 文件操作：重命名、创建目录、批量移动/复制，以及本地路径到 CD2 内部路径的转换。
    """
    def __init__(self, connection):
        self.connection = connection
        self.config = {}

    def set_config(self, config: dict):
        """挂载客户端配置（用于 mount_path 路径映射）"""
        self.config = config or {}

    def _to_cd2_path(self, local_path: str) -> str:
        """
        Convert local absolute path to CD2 internal path.
        Requires 'mount_path' to be set in client config.
        """
        mount_path = self.config.get('mount_path', '').strip()
        if not mount_path:
            logger.warning(f"[{self.connection.name}] No mount_path configured. Using path as-is: {local_path}")
            return local_path

        abs_mount = os.path.abspath(mount_path)
        abs_local = os.path.abspath(local_path)

        if abs_local.startswith(abs_mount):
            rel_path = abs_local[len(abs_mount):]
            if not rel_path.startswith('/'):
                rel_path = '/' + rel_path
            logger.debug(f"[{self.connection.name}] Path conversion: {local_path} -> {rel_path} (Mount: {mount_path})")
            return rel_path

        logger.warning(f"[{self.connection.name}] Path {local_path} does not start with mount_path {mount_path}. Using as-is.")
        return local_path

    def rename_file(self, path: str, new_name: str) -> Tuple[bool, str]:
        """
        Rename a file/directory using CD2 native API.
        'path' is the full CD2 path, 'new_name' is just the filename.
        """
        conn = self.connection
        try:
            req = conn.pb2.RenameFileRequest(
                theFilePath=path,
                newName=new_name
            )
            resp = conn.stub.RenameFile(req, metadata=conn.get_metadata(), timeout=60)

            if resp.success:
                return True, "Success"
            else:
                return False, resp.errorMessage or "Unknown error"
        except Exception as e:
            logger.error(f"[{conn.name}] CD2 Rename Exception: {e}")
            return False, str(e)

    def create_directory(self, parent_path: str, name: str) -> Tuple[bool, str]:
        """
        Create a directory using CD2 native API.
        """
        conn = self.connection
        try:
            req = conn.pb2.CreateFolderRequest(
                parentPath=parent_path,
                folderName=name
            )
            resp = conn.stub.CreateFolder(req, metadata=conn.get_metadata(), timeout=60)

            # The result is nested inside CreateFolderResult
            if resp.result.success:
                return True, "Success"
            else:
                return False, resp.result.errorMessage or "Unknown error"
        except Exception as e:
            logger.error(f"[{conn.name}] CD2 CreateFolder Exception: {e}")
            return False, str(e)

    def move_files(self, src_paths: List[str], dest_dir: str) -> Tuple[bool, str]:
        """
        Batch move files to a destination directory.
        'src_paths' are local absolute paths.
        'dest_dir' is the local absolute target directory.
        """
        conn = self.connection
        cd2_srcs = [self._to_cd2_path(p) for p in src_paths]
        cd2_dest_dir = self._to_cd2_path(dest_dir)

        logger.info(f"[{conn.name}] 原生批量移动: {len(cd2_srcs)} 个文件 -> {cd2_dest_dir}")

        try:
            req = conn.pb2.MoveFileRequest(
                theFilePaths=cd2_srcs,
                destPath=cd2_dest_dir
            )
            resp = conn.stub.MoveFile(req, metadata=conn.get_metadata(), timeout=60)

            if resp.success:
                log_audit("CD2", "移动", f"云端移动成功: {len(cd2_srcs)} 个文件 -> {dest_dir}")
                return True, "Success"
            else:
                log_audit("CD2", "移动失败", f"云端移动失败: {resp.errorMessage}", level="ERROR")
                return False, resp.errorMessage or "Batch Move failed"
        except Exception as e:
            logger.error(f"[{conn.name}] CD2 Batch Move Exception: {e}")
            return False, str(e)

    def copy_files(self, src_paths: List[str], dest_dir: str) -> Tuple[bool, str]:
        """
        Batch copy files to a destination directory.
        """
        conn = self.connection
        cd2_srcs = [self._to_cd2_path(p) for p in src_paths]
        cd2_dest_dir = self._to_cd2_path(dest_dir)

        logger.info(f"[{conn.name}] 原生批量复制: {len(cd2_srcs)} 个文件 -> {cd2_dest_dir}")

        try:
            req = conn.pb2.CopyFileRequest(
                theFilePaths=cd2_srcs,
                destPath=cd2_dest_dir
            )
            resp = conn.stub.CopyFile(req, metadata=conn.get_metadata(), timeout=60)

            if resp.success:
                return True, "Success"
            else:
                return False, resp.errorMessage or "Batch Copy failed"
        except Exception as e:
            logger.error(f"[{conn.name}] CD2 Batch Copy Exception: {e}")
            return False, str(e)
