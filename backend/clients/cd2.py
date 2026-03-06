import grpc
import logging
import os
from typing import List, Dict, Any, Union, Tuple
from logger import log_audit
from .base_client import BaseClient
from .cd2_helper import ensure_cd2_module, torrent_to_magnet

logger = logging.getLogger(__name__)

class CD2Client(BaseClient):
    """
    Client for CloudDrive2 (CD2) via gRPC.
    """
    def __init__(self, client_config: Dict[str, Any]):
        super().__init__(client_config)
        self.host = self.url.replace("http://", "").replace("https://", "").rstrip("/")
        self.pb2, self.pb2_grpc = ensure_cd2_module()
        self.channel = None
        self.stub = None
        self.token = None

    def _connect(self):
        if not self.pb2 or not self.pb2_grpc:
            logger.error(f"[{self.name}] CD2 modules not available.")
            return False
        
        if self.channel is None:
            self.channel = grpc.insecure_channel(self.host)
            self.stub = self.pb2_grpc.CloudDriveFileSrvStub(self.channel)
        return True

    async def _get_async_stub(self):
        """获取异步 gRPC Stub"""
        if not hasattr(self, '_async_channel') or self._async_channel is None:
            self._async_channel = grpc.aio.insecure_channel(self.host)
            self._async_stub = self.pb2_grpc.CloudDriveFileSrvStub(self._async_channel)
        return self._async_stub

    def get_metadata(self):
        """获取带 Token 的元数据"""
        return [('authorization', f'Bearer {self.token}')] if self.token else []

    async def login_async(self) -> bool:
        """异步登录逻辑"""
        stub = await self._get_async_stub()
        
        if self.api_token:
            self.token = self.api_token
            self.logged_in = True
            logger.info(f"[{self.name}] CD2 使用 API Token 登录成功")
            return True
        
        try:
            req = self.pb2.GetTokenRequest(userName=self.username, password=self.password)
            resp = await stub.GetToken(req, timeout=10)
            if resp.success:
                self.token = resp.token
                self.logged_in = True
                return True
            else:
                logger.error(f"[{self.name}] CD2 Async Login Failed: {resp.errorMessage}")
        except Exception as e:
            logger.error(f"[{self.name}] CD2 Async Login Exception: {e}")
        return False

    def login(self) -> bool:
        if not self._connect():
            return False

        if self.api_token:
            self.token = self.api_token
            self.logged_in = True
            logger.info(f"[{self.name}] CD2 使用 API Token 登录成功")
            return True

        try:
            req = self.pb2.GetTokenRequest(userName=self.username, password=self.password)
            resp = self.stub.GetToken(req, timeout=10)
            
            if resp.success:
                self.token = resp.token
                self.logged_in = True
                return True
            else:
                logger.error(f"[{self.name}] CD2 Login Failed: {resp.errorMessage}")
                return False
        except grpc.RpcError as e:
            logger.error(f"[{self.name}] CD2 RPC Error: {e.details()}")
            return False
        except Exception as e:
            logger.error(f"[{self.name}] CD2 Exception: {e}")
            return False

    def test_connection(self) -> Dict[str, Any]:
        if self.login():
            return {"success": True, "message": "Connected (Logged into CD2).", "version": "CD2 gRPC"}
        return {"success": False, "message": "Failed to connect or login to CD2."}

    def add_torrent(self, content: Union[str, bytes], is_file: bool = False, **kwargs) -> Tuple[bool, str]:
        if not self.logged_in:
            if not self.login():
                return False, "Login failed"

        magnet_link = ""
        if is_file:
            # content is bytes, convert to magnet
            magnet_link = torrent_to_magnet(content)
            if not magnet_link:
                return False, "Failed to convert torrent file to magnet."
            logger.info(f"[{self.name}] 种子文件已成功转换为磁力链: {magnet_link[:60]}...")
        else:
            # content is magnet link string
            magnet_link = content

        # Priority: kwargs['save_path'] > config['default_save_path'] > "/"
        save_path = kwargs.get('save_path')
        if not save_path:
             save_path = self.config.get('default_save_path')
        
        if not save_path:
             save_path = "/" 

        try:
            req = self.pb2.AddOfflineFileRequest(
                urls=magnet_link,
                toFolder=save_path,
                checkFolderAfterSecs=1
            )
            metadata = [('authorization', f'Bearer {self.token}')]
            resp = self.stub.AddOfflineFiles(req, metadata=metadata, timeout=60)

            if resp.success:
                log_audit("CD2", "添加任务", f"成功添加离线任务到: {save_path}", details={"client": self.name})
                return True, "Task added successfully."
            else:
                log_audit("CD2", "任务失败", f"添加离线任务失败: {resp.errorMessage}", level="ERROR")
                return False, f"CD2 Error: {resp.errorMessage}"

        except grpc.RpcError as e:
            return False, f"RPC Error: {e.details()}"
        except Exception as e:
            return False, f"Exception: {str(e)}"

    def get_torrent_files(self, torrent_hash: str) -> List[Dict[str, Any]]:
        return []

    def _to_cd2_path(self, local_path: str) -> str:
        """
        Convert local absolute path to CD2 internal path.
        Requires 'mount_path' to be set in client config.
        """
        mount_path = self.config.get('mount_path', '').strip()
        if not mount_path:
            logger.warning(f"[{self.name}] No mount_path configured. Using path as-is: {local_path}")
            return local_path
        
        abs_mount = os.path.abspath(mount_path)
        abs_local = os.path.abspath(local_path)
        
        if abs_local.startswith(abs_mount):
            rel_path = abs_local[len(abs_mount):]
            if not rel_path.startswith('/'):
                rel_path = '/' + rel_path
            logger.debug(f"[{self.name}] Path conversion: {local_path} -> {rel_path} (Mount: {mount_path})")
            return rel_path
        
        logger.warning(f"[{self.name}] Path {local_path} does not start with mount_path {mount_path}. Using as-is.")
        return local_path

    def rename_file(self, path: str, new_name: str) -> Tuple[bool, str]:
        """
        Rename a file/directory using CD2 native API.
        'path' is the full CD2 path, 'new_name' is just the filename.
        """
        if not self.logged_in and not self.login():
            return False, "Login failed"

        try:
            req = self.pb2.RenameFileRequest(
                theFilePath=path,
                newName=new_name
            )
            metadata = [('authorization', f'Bearer {self.token}')]
            resp = self.stub.RenameFile(req, metadata=metadata, timeout=60)

            if resp.success:
                return True, "Success"
            else:
                return False, resp.errorMessage or "Unknown error"
        except Exception as e:
            logger.error(f"[{self.name}] CD2 Rename Exception: {e}")
            return False, str(e)

    def create_directory(self, parent_path: str, name: str) -> Tuple[bool, str]:
        """
        Create a directory using CD2 native API.
        """
        if not self.logged_in and not self.login():
            return False, "Login failed"
        
        try:
            req = self.pb2.CreateFolderRequest(
                parentPath=parent_path,
                folderName=name
            )
            metadata = [('authorization', f'Bearer {self.token}')]
            resp = self.stub.CreateFolder(req, metadata=metadata, timeout=60)
            
            # The result is nested inside CreateFolderResult
            if resp.result.success:
                return True, "Success"
            else:
                return False, resp.result.errorMessage or "Unknown error"
        except Exception as e:
            logger.error(f"[{self.name}] CD2 CreateFolder Exception: {e}")
            return False, str(e)

    def move_files(self, src_paths: List[str], dest_dir: str) -> Tuple[bool, str]:
        """
        Batch move files to a destination directory.
        'src_paths' are local absolute paths.
        'dest_dir' is the local absolute target directory.
        """
        if not self.logged_in and not self.login():
            return False, "Login failed"

        cd2_srcs = [self._to_cd2_path(p) for p in src_paths]
        cd2_dest_dir = self._to_cd2_path(dest_dir)
        
        logger.info(f"[{self.name}] Native Batch Move: {len(cd2_srcs)} items -> {cd2_dest_dir}")

        try:
            req = self.pb2.MoveFileRequest(
                theFilePaths=cd2_srcs,
                destPath=cd2_dest_dir
            )
            metadata = [('authorization', f'Bearer {self.token}')]
            resp = self.stub.MoveFile(req, metadata=metadata, timeout=60)

            if resp.success:
                log_audit("CD2", "移动", f"云端移动成功: {len(cd2_srcs)} 个文件 -> {dest_dir}")
                return True, "Success"
            else:
                log_audit("CD2", "移动失败", f"云端移动失败: {resp.errorMessage}", level="ERROR")
                return False, resp.errorMessage or "Batch Move failed"
        except Exception as e:
            logger.error(f"[{self.name}] CD2 Batch Move Exception: {e}")
            return False, str(e)

    def move_file(self, src_path: str, dest_path: str) -> Tuple[bool, str]:
        # Keep for backward compatibility or simple moves
        return self.move_files([src_path], os.path.dirname(dest_path))

    def copy_files(self, src_paths: List[str], dest_dir: str) -> Tuple[bool, str]:
        """
        Batch copy files to a destination directory.
        """
        if not self.logged_in and not self.login():
            return False, "Login failed"

        cd2_srcs = [self._to_cd2_path(p) for p in src_paths]
        cd2_dest_dir = self._to_cd2_path(dest_dir)

        logger.info(f"[{self.name}] Native Batch Copy: {len(cd2_srcs)} items -> {cd2_dest_dir}")

        try:
            req = self.pb2.CopyFileRequest(
                theFilePaths=cd2_srcs,
                destPath=cd2_dest_dir
            )
            metadata = [('authorization', f'Bearer {self.token}')]
            resp = self.stub.CopyFile(req, metadata=metadata, timeout=60)

            if resp.success:
                return True, "Success"
            else:
                return False, resp.errorMessage or "Batch Copy failed"
        except Exception as e:
            logger.error(f"[{self.name}] CD2 Batch Copy Exception: {e}")
            return False, str(e)

    def copy_file(self, src_path: str, dest_path: str) -> Tuple[bool, str]:
        return self.copy_files([src_path], os.path.dirname(dest_path))

    def get_torrents(self, filter: str = 'all') -> List[Dict[str, Any]]:
        return []

    def delete_torrent(self, torrent_hash: str, delete_files: bool = False) -> bool:
        return False

    async def close_async(self):
        """关闭异步连接"""
        if hasattr(self, '_async_channel') and self._async_channel:
            await self._async_channel.close()
            self._async_channel = None

