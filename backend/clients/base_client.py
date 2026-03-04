from abc import ABC, abstractmethod
from typing import List, Dict, Any, Union, Tuple

class BaseClient(ABC):
    """
    Abstract base class for download clients.
    All download clients (QB, CD2, Aria2, etc.) must implement this interface.
    """
    def __init__(self, client_config: Dict[str, Any]):
        self.config = client_config
        self.client_id = client_config.get('id', 'unknown')
        self.name = client_config.get('name', 'Unknown Client')
        self.url = client_config.get('url', '').rstrip('/')
        self.username = client_config.get('username', '')
        self.password = client_config.get('password', '')
        self.logged_in = False

    @abstractmethod
    def login(self) -> bool:
        """Authenticate with the client."""
        pass

    @abstractmethod
    def test_connection(self) -> Dict[str, Any]:
        """
        Test connectivity.
        Returns: {'success': bool, 'message': str, 'version': str (optional)}
        """
        pass

    @abstractmethod
    def add_torrent(self, content: Union[str, bytes], is_file: bool = False, **kwargs) -> Tuple[bool, str]:
        """
        Add a torrent task.
        :param content: Magnet link string or torrent file bytes.
        :param is_file: True if content is bytes.
        :param kwargs: save_path, category, tags, paused, etc.
        """
        pass

    @abstractmethod
    def get_torrent_files(self, torrent_hash: str) -> List[Dict[str, Any]]:
        """Get file list for a specific torrent task."""
        pass

    @abstractmethod
    def rename_file(self, torrent_hash: str, old_path: str, new_path: str) -> bool:
        """Rename a file inside a torrent task."""
        pass

    @abstractmethod
    def get_torrents(self, filter: str = 'all') -> List[Dict[str, Any]]:
        """获取任务列表"""
        pass

    @abstractmethod
    def delete_torrent(self, torrent_hash: str, delete_files: bool = False) -> bool:
        """删除任务"""
        pass
