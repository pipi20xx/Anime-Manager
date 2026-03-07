from typing import Optional, Dict, List, Tuple
import logging
import asyncio
import httpx
from config_manager import ConfigManager
from notification import NotificationManager
from .base_client import BaseClient
from .qbittorrent import QBClient
from .cd2 import CD2Client

logger = logging.getLogger(__name__)

class ClientManager:
    """
    Singleton manager for download clients.
    """
    _instances: Dict[str, BaseClient] = {}

    @staticmethod
    def clear_cache():
        """清除客户端实例缓存，配置更新时调用"""
        ClientManager._instances.clear()
        logger.info("客户端实例缓存已清除")

    @staticmethod
    async def add_task(client_id: str, url: str, **kwargs) -> Tuple[bool, str]:
        """
        Unified entry point to add a download task.
        Handles:
        1. Client retrieval.
        2. Default save_path injection.
        3. HTTP .torrent downloading (Smart Mode).
        """
        from logger import log_audit
        client = ClientManager.get_client(client_id)
        if not client:
            return False, f"客户端 {client_id} 未找到"

        # 1. Apply Default Save Path if not present
        if not kwargs.get('save_path'):
            default_path = client.config.get('default_save_path')
            if default_path:
                kwargs['save_path'] = default_path

        # 2. Handle Content
        success = False
        msg = ""
        
        if url.startswith("magnet:"):
            # Magnet: direct add
            success, msg = await asyncio.to_thread(client.add_torrent, url, is_file=False, **kwargs)
        else:
            # HTTP(s): Try to download as file first
            content = None
            try:
                async with httpx.AsyncClient(timeout=25, follow_redirects=True, verify=False) as http_cli:
                    async with http_cli.stream('GET', url) as resp:
                        if resp.status_code == 200:
                            cl = resp.headers.get('content-length')
                            if cl and int(cl) > 10 * 1024 * 1024: # > 10MB
                                pass # Too big
                            else:
                                chunks = []
                                size = 0
                                async for chunk in resp.aiter_bytes():
                                    size += len(chunk)
                                    if size > 10 * 1024 * 1024:
                                        chunks = None
                                        break
                                    chunks.append(chunk)
                                if chunks:
                                    content = b"".join(chunks)
            except Exception as e:
                logger.warning(f"Smart download failed for {url}: {e}")
            
            if content:
                success, msg = await asyncio.to_thread(client.add_torrent, content, is_file=True, **kwargs)
            else:
                # Fallback to URL
                success, msg = await asyncio.to_thread(client.add_torrent, url, is_file=False, **kwargs)

        if success:
            log_audit("下载", "推送成功", f"任务已发送至客户端 {client.name}: {url}", details=url)
        else:
            log_audit("下载", "推送失败", f"客户端 {client.name} 返回错误: {msg} (URL: {url})", level="ERROR", details=url)
            await NotificationManager.push_client_error_notification(url, client.name, msg)
            
        return success, msg

    @staticmethod
    def get_client(client_id: str = None) -> Optional[BaseClient]:
        """
        Get an initialized client instance.
        If client_id is None, returns the first client marked as default, or the first one available.
        """
        config = ConfigManager.get_config()
        clients_conf = config.get("download_clients", [])
        
        target_conf = None
        
        if not client_id:
            # Find default
            for c in clients_conf:
                if c.get('is_default'):
                    target_conf = c
                    break
            # Fallback to first
            if not target_conf and clients_conf:
                target_conf = clients_conf[0]
        else:
            # Find by ID
            for c in clients_conf:
                if c.get('id') == client_id:
                    target_conf = c
                    break
        
        if not target_conf:
            return None

        cid = target_conf.get('id')
        if cid in ClientManager._instances:
            return ClientManager._instances[cid]
        
        # Create new instance
        client = ClientManager._create_client(target_conf)
        if client:
            ClientManager._instances[cid] = client
        return client

    @staticmethod
    def _create_client(conf: Dict) -> Optional[BaseClient]:
        ctype = conf.get('type', 'qbittorrent').lower()
        try:
            if ctype == 'qbittorrent':
                return QBClient(conf)
            elif ctype == 'cd2':
                return CD2Client(conf)
            else:
                logger.warning(f"Unknown client type: {ctype}")
                return None
        except Exception as e:
            logger.error(f"Failed to create client {conf.get('name')}: {e}")
            return None

    @staticmethod
    def get_all_clients() -> List[Dict]:
        """Return list of client configs (for UI)."""
        return ConfigManager.get_config().get("download_clients", [])
