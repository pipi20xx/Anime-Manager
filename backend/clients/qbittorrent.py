import requests
import logging
from typing import List, Dict, Any, Union, Tuple
from .base_client import BaseClient

logger = logging.getLogger(__name__)

class QBClient(BaseClient):
    """
    Wrapper for qBittorrent API v2.
    """
    def __init__(self, client_config: Dict[str, Any]):
        super().__init__(client_config)
        self.session = requests.Session()
        self.session.headers.update({'Referer': self.url})

    def login(self) -> bool:
        try:
            self.session.cookies.clear()
            
            self.session.headers.update({
                'Referer': f"{self.url}/",
                'Origin': self.url
            })

            resp = self.session.post(f"{self.url}/api/v2/auth/login", data={
                'username': self.username,
                'password': self.password
            }, timeout=10)
            
            if resp.status_code == 403:
                logger.error(f"[{self.name}] QB Login Failed: IP is banned (too many failed attempts)")
                return False
            
            if resp.status_code == 200:
                if resp.text == "Fails.":
                    logger.error(f"[{self.name}] QB Login Failed: Invalid username or password")
                    return False
                self.logged_in = True
                logger.info(f"[{self.name}] QB Login successful (HTTP 200)")
                return True
            
            if resp.status_code == 204:
                if self.session.cookies:
                    self.logged_in = True
                    logger.info(f"[{self.name}] QB Login successful (HTTP 204, QB >= 5.2.0)")
                    return True
                else:
                    logger.error(f"[{self.name}] QB Login Failed: HTTP 204 but no cookie received")
                    return False
            
            logger.error(f"[{self.name}] QB Login Failed: Unexpected status code {resp.status_code}, response: {resp.text}")
            return False
        except Exception as e:
            logger.error(f"[{self.name}] QB Login Exception: {e}")
            return False

    def test_connection(self) -> Dict[str, Any]:
        if not self.login():
             return {"success": False, "message": "Login failed"}
        try:
            version_response = self.session.get(f"{self.url}/api/v2/app/version", timeout=5)
            if version_response.status_code == 200:
                return {"success": True, "message": f"Connected. QB Version: {version_response.text}", "version": version_response.text}
            
            if version_response.status_code == 403:
                return {"success": False, "message": "Login succeeded but API access forbidden. Check WebUI permissions."}
            
            return {"success": False, "message": f"Login OK but failed to get version. Code: {version_response.status_code}"}
        except Exception as e:
            return {"success": False, "message": f"Connection Exception: {e}"}

    def add_torrent(self, content: Union[str, bytes], is_file: bool = False, **kwargs) -> Tuple[bool, str]:
        # Ensure we are logged in before adding torrent
        if not self.logged_in:
            if not self.login():
                return False, "QB login failed"

        data = {}
        # Priority: kwargs['save_path'] > config['default_save_path'] > QB default
        save_path = kwargs.get('save_path')
        if not save_path:
             save_path = self.config.get('default_save_path')
        
        if save_path: data['savepath'] = save_path
        if kwargs.get('category'): data['category'] = kwargs['category']
        if kwargs.get('tags'): data['tags'] = kwargs['tags']
        
        # Explicitly set paused state (must be 'true' or 'false' string for QB API)
        data['paused'] = 'true' if kwargs.get('paused') else 'false'
        
        if kwargs.get('root_folder') is not None: 
            data['root_folder'] = 'true' if kwargs.get('root_folder') else 'false'

        try:
            if is_file:
                files = {'torrents': ('torrent_file.torrent', content, 'application/x-bittorrent')}
                resp = self.session.post(f"{self.url}/api/v2/torrents/add", data=data, files=files, timeout=30)
            else:
                data['urls'] = content
                resp = self.session.post(f"{self.url}/api/v2/torrents/add", data=data, timeout=30)
            
            # If still forbidden, try to re-login once
            if resp.status_code == 403:
                import time
                time.sleep(0.5)
                logger.warning(f"[{self.name}] QB returned 403, attempting re-login...")
                if self.login():
                    return self.add_torrent(content, is_file, **kwargs)

            if resp.status_code == 200:
                if resp.text == "Ok.":
                    logger.info(f"[{self.name}] Torrent added successfully (QB < 5.2.0)")
                    return True, "Ok."
                
                try:
                    result = resp.json()
                    if isinstance(result, dict) and result.get('success_count', 0) > 0:
                        torrent_ids = result.get('added_torrent_ids', [])
                        logger.info(f"[{self.name}] Torrent added successfully (QB >= 5.2.0), IDs: {torrent_ids}")
                        return True, f"Ok. Added {len(torrent_ids)} torrent(s)"
                except:
                    pass
                
                logger.warning(f"[{self.name}] Unexpected response format: {resp.text}")
                return False, f"Unexpected response: {resp.text}"
            
            logger.error(f"[{self.name}] Add torrent failed: HTTP {resp.status_code}, {resp.text}")
            return False, f"Failed. Code: {resp.status_code}, Resp: {resp.text}"
        except Exception as e:
            logger.error(f"[{self.name}] add_torrent exception: {e}")
            return False, str(e)

    def get_torrent_files(self, torrent_hash: str) -> List[Dict[str, Any]]:
        try:
            resp = self.session.get(f"{self.url}/api/v2/torrents/files", params={'hash': torrent_hash}, timeout=10)
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            logger.error(f"[{self.name}] get_torrent_files exception: {e}")
            return []

    def rename_file(self, torrent_hash: str, old_path: str, new_path: str) -> bool:
        try:
            resp = self.session.post(f"{self.url}/api/v2/torrents/renameFile", data={
                'hash': torrent_hash,
                'oldPath': old_path,
                'newPath': new_path
            }, timeout=10)
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"[{self.name}] rename_file exception: {e}")
            return False

    def get_torrents(self, filter: str = 'all') -> List[Dict[str, Any]]:
        """获取种子列表"""
        if not self.logged_in and not self.login():
            return []
        try:
            resp = self.session.get(f"{self.url}/api/v2/torrents/info", params={'filter': filter}, timeout=15)
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            logger.error(f"[{self.name}] get_torrents exception: {e}")
            return []

    def delete_torrent(self, torrent_hash: str, delete_files: bool = False) -> bool:
        """删除种子"""
        if not self.logged_in and not self.login():
            return False
        try:
            resp = self.session.post(f"{self.url}/api/v2/torrents/delete", data={
                'hashes': torrent_hash,
                'deleteFiles': 'true' if delete_files else 'false'
            }, timeout=15)
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"[{self.name}] delete_torrent exception: {e}")
            return False
