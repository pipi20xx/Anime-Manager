import os
import logging
from typing import List, Dict, Any, Union, Tuple

from clients.base_client import BaseClient
from .connection import CD2Connection
from .file_ops import CD2FileOps
from .offline import CD2OfflineTasks

logger = logging.getLogger(__name__)


class CD2Client(BaseClient):
    """
    Client for CloudDrive2 (CD2) via gRPC.

    薄外观层：连接/鉴权委托给 CD2Connection，文件操作委托给 CD2FileOps，
    离线任务委托给 CD2OfflineTasks。对外接口与 BaseClient 保持一致。
    """
    def __init__(self, client_config: Dict[str, Any]):
        # BaseClient.__init__ 会设置 self.logged_in（经 property 转发），
        # 因此必须先创建连接对象
        self._conn = CD2Connection(client_config)
        super().__init__(client_config)
        self._file_ops = CD2FileOps(self._conn)
        self._file_ops.set_config(client_config)
        self._offline = CD2OfflineTasks(self._conn)
        self._offline.set_config(client_config)

    # ---- 对外保持兼容的属性（原实现直接挂在实例上） ----
    @property
    def pb2(self):
        return self._conn.pb2

    @property
    def pb2_grpc(self):
        return self._conn.pb2_grpc

    @property
    def channel(self):
        return self._conn.channel

    @property
    def stub(self):
        return self._conn.stub

    @property
    def token(self):
        return self._conn.token

    @token.setter
    def token(self, value):
        self._conn.token = value

    @property
    def logged_in(self):
        return self._conn.logged_in

    @logged_in.setter
    def logged_in(self, value):
        self._conn.logged_in = value

    @property
    def host(self):
        return self._conn.host

    def _to_cd2_path(self, local_path: str) -> str:
        """本地路径转 CD2 内部路径（organizer_core 等外部模块直接调用）"""
        return self._file_ops._to_cd2_path(local_path)

    # ---- 连接/鉴权 ----
    async def _get_async_stub(self):
        """获取异步 gRPC Stub"""
        return await self._conn._get_async_stub()

    def get_metadata(self):
        """获取带 Token 的元数据"""
        return self._conn.get_metadata()

    async def login_async(self) -> bool:
        """异步登录逻辑"""
        return await self._conn.login_async()

    def login(self) -> bool:
        return self._conn.login()

    def test_connection(self) -> Dict[str, Any]:
        if self.login():
            return {"success": True, "message": "Connected (Logged into CD2).", "version": "CD2 gRPC"}
        return {"success": False, "message": "Failed to connect or login to CD2."}

    # ---- 离线任务 ----
    def add_torrent(self, content: Union[str, bytes], is_file: bool = False, **kwargs) -> Tuple[bool, str]:
        if not self.logged_in:
            if not self.login():
                return False, "Login failed"
        return self._offline.add_torrent(content, is_file=is_file, **kwargs)

    # ---- 文件操作 ----
    def rename_file(self, path: str, new_name: str) -> Tuple[bool, str]:
        """
        Rename a file/directory using CD2 native API.
        'path' is the full CD2 path, 'new_name' is just the filename.
        """
        if not self.logged_in and not self.login():
            return False, "Login failed"
        return self._file_ops.rename_file(path, new_name)

    def create_directory(self, parent_path: str, name: str) -> Tuple[bool, str]:
        """
        Create a directory using CD2 native API.
        """
        if not self.logged_in and not self.login():
            return False, "Login failed"
        return self._file_ops.create_directory(parent_path, name)

    def move_files(self, src_paths: List[str], dest_dir: str) -> Tuple[bool, str]:
        """
        Batch move files to a destination directory.
        'src_paths' are local absolute paths.
        'dest_dir' is the local absolute target directory.
        """
        if not self.logged_in and not self.login():
            return False, "Login failed"
        return self._file_ops.move_files(src_paths, dest_dir)

    def move_file(self, src_path: str, dest_path: str) -> Tuple[bool, str]:
        # Keep for backward compatibility or simple moves
        return self.move_files([src_path], os.path.dirname(dest_path))

    def copy_files(self, src_paths: List[str], dest_dir: str) -> Tuple[bool, str]:
        """
        Batch copy files to a destination directory.
        """
        if not self.logged_in and not self.login():
            return False, "Login failed"
        return self._file_ops.copy_files(src_paths, dest_dir)

    def copy_file(self, src_path: str, dest_path: str) -> Tuple[bool, str]:
        return self.copy_files([src_path], os.path.dirname(dest_path))

    # ---- 未实现的接口（保持原行为） ----
    def get_torrent_files(self, torrent_hash: str) -> List[Dict[str, Any]]:
        return []

    def get_torrents(self, filter: str = 'all') -> List[Dict[str, Any]]:
        return []

    def delete_torrent(self, torrent_hash: str, delete_files: bool = False) -> bool:
        return False

    async def close_async(self):
        """关闭异步连接"""
        await self._conn.close_async()
