import os
import logging
from typing import List, Dict, Any, Union, Tuple

from clients.base_client import BaseClient
from .connection import CD2Connection
from .file_ops import CD2FileOps
from .offline import CD2OfflineTasks
from .task_manager import CD2TaskManager
from .file_browser import CD2FileBrowser
from .server_info import CD2ServerInfo
from .remote_upload import RemoteUploadManager

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
        self._task_manager = CD2TaskManager(self._conn)
        self._file_browser = CD2FileBrowser(self._conn)
        self._server_info = CD2ServerInfo(self._conn)

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

    # ---- 种子（离线）任务管理，委托 CD2TaskManager（按 CD2 路径操作） ----
    def list_offline_tasks(self, path: str) -> Dict[str, Any]:
        if not self.logged_in and not self.login():
            return {"success": False, "message": "Login failed", "tasks": [], "quota": {}, "total": 0}
        result = self._task_manager.list_tasks(path)
        if result.get("success"):
            result["quota"] = self._task_manager.get_quota(path)
        return result

    def remove_offline_tasks(self, info_hashes: List[str], path: str, delete_files: bool = False) -> Tuple[bool, str]:
        if not self.logged_in and not self.login():
            return False, "Login failed"
        return self._task_manager.remove_tasks(info_hashes, path, delete_files)

    def restart_offline_task(self, info_hash: str, url: str, parent_id: str, path: str) -> Tuple[bool, str]:
        if not self.logged_in and not self.login():
            return False, "Login failed"
        return self._task_manager.restart_task(info_hash, url, parent_id, path)

    def clear_offline_tasks(self, filter_code: int, path: str, delete_files: bool = False) -> Tuple[bool, str]:
        if not self.logged_in and not self.login():
            return False, "Login failed"
        return self._task_manager.clear_tasks(filter_code, path, delete_files)

    def add_offline_urls(self, urls: str, to_folder: str) -> Tuple[bool, str]:
        if not self.logged_in and not self.login():
            return False, "Login failed"
        return self._offline.add_urls(urls, to_folder)

    # ---- 文件浏览与文件操作（CD2 内部路径），委托 CD2FileBrowser ----
    def browse_files(self, path: str = "/", force_refresh: bool = False) -> Dict[str, Any]:
        if not self.logged_in and not self.login():
            return {"success": False, "message": "Login failed", "entries": [], "total": 0}
        return self._file_browser.list_dir(path, force_refresh)

    def create_folder(self, parent_path: str, name: str) -> Tuple[bool, str]:
        if not self.logged_in and not self.login():
            return False, "Login failed"
        return self._file_browser.create_folder(parent_path, name)

    def rename_path(self, path: str, new_name: str) -> Tuple[bool, str]:
        if not self.logged_in and not self.login():
            return False, "Login failed"
        return self._file_browser.rename(path, new_name)

    def organize_rename(self, path: str, new_relative_path: str) -> Tuple[bool, str]:
        """识别后的整理式重命名：可含子目录，自动建目录+移动"""
        if not self.logged_in and not self.login():
            return False, "Login failed"
        return self._file_browser.organize_rename(path, new_relative_path)

    def walk_files(self, root: str, video_exts: List[str] = None, ignore_regex: List[str] = None) -> List[Dict[str, Any]]:
        """递归遍历云目录（供整理任务扫描云源）"""
        if not self.logged_in and not self.login():
            return []
        return self._file_browser.walk_files(root, video_exts=video_exts, ignore_regex=ignore_regex)

    def delete_paths(self, paths: List[str], permanently: bool = False) -> Tuple[bool, str]:
        if not self.logged_in and not self.login():
            return False, "Login failed"
        return self._file_browser.delete_files(paths, permanently=permanently)

    def transfer_paths(self, paths: List[str], dest_dir: str, action: str = "move", conflict_policy: int = 1) -> Tuple[bool, str]:
        if not self.logged_in and not self.login():
            return False, "Login failed"
        return self._file_browser.transfer_files(paths, dest_dir, action, conflict_policy)

    def upload_file(self, parent_path: str, file_name: str, data: bytes) -> Tuple[bool, str]:
        if not self.logged_in and not self.login():
            return False, "Login failed"
        return self._file_browser.upload_file(parent_path, file_name, data)

    def get_server_info(self) -> Dict[str, Any]:
        if not self.logged_in and not self.login():
            return {"running": {}, "tasks": {}, "system": {}}
        return self._server_info.snapshot()

    # ---- 远程上传（Remote Upload 协议），委托 RemoteUploadManager ----
    def start_remote_upload(self, path: str, file_name: str, size: int) -> Dict[str, Any]:
        if not self.logged_in and not self.login():
            return {"success": False, "message": "Login failed"}
        return RemoteUploadManager.get_instance().start(self._conn, path, file_name, size)

    def remote_upload_next(self, upload_id: str) -> Dict[str, Any]:
        return RemoteUploadManager.get_instance().next_request(upload_id)

    def remote_upload_data(self, upload_id: str, request_id: str, data: bytes) -> Dict[str, Any]:
        return RemoteUploadManager.get_instance().submit_data(upload_id, request_id, data)

    def remote_upload_cancel(self, upload_id: str) -> Dict[str, Any]:
        return RemoteUploadManager.get_instance().cancel(upload_id)

    async def close_async(self):
        """关闭异步连接"""
        await self._conn.close_async()
