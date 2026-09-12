import grpc
import logging
import hashlib
from typing import Tuple, Union

import bencodepy
from logger import log_audit

logger = logging.getLogger(__name__)


def torrent_to_magnet(torrent_content: bytes) -> str:
    try:
        metadata = bencodepy.decode(torrent_content)
        info = metadata[b'info']
        info_encoded = bencodepy.encode(info)
        digest = hashlib.sha1(info_encoded).hexdigest()
        return f"magnet:?xt=urn:btih:{digest}"
    except Exception as e:
        logger.error(f"种子转磁力链接失败: {e}")
        return ""


class CD2OfflineTasks:
    """
    CD2 离线下载任务：通过 AddOfflineFiles 提交磁力链任务。
    """
    def __init__(self, connection):
        self.connection = connection
        self.config = {}

    def set_config(self, config: dict):
        """挂载客户端配置（用于 default_save_path）"""
        self.config = config or {}

    def add_torrent(self, content: Union[str, bytes], is_file: bool = False, **kwargs) -> Tuple[bool, str]:
        conn = self.connection

        magnet_link = ""
        if is_file:
            # content is bytes, convert to magnet
            magnet_link = torrent_to_magnet(content)
            if not magnet_link:
                return False, "Failed to convert torrent file to magnet."
            logger.info(f"[{conn.name}] 种子文件已成功转换为磁力链: {magnet_link[:60]}...")
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
            req = conn.pb2.AddOfflineFileRequest(
                urls=magnet_link,
                toFolder=save_path,
                checkFolderAfterSecs=1
            )
            resp = conn.stub.AddOfflineFiles(req, metadata=conn.get_metadata(), timeout=60)

            if resp.success:
                log_audit("CD2", "添加任务", f"成功添加离线任务到: {save_path}", details={"client": conn.name})
                return True, "Task added successfully."
            else:
                log_audit("CD2", "任务失败", f"添加离线任务失败: {resp.errorMessage}", level="ERROR")
                return False, f"CD2 Error: {resp.errorMessage}"

        except grpc.RpcError as e:
            return False, f"RPC Error: {e.details()}"
        except Exception as e:
            return False, f"Exception: {str(e)}"

    def add_urls(self, urls: str, to_folder: str) -> Tuple[bool, str]:
        """
        提交离线下载链接 (AddOfflineFiles)。
        :param urls: 磁力链/ed2k 等，多个链接由 CD2 解析
        :param to_folder: 目标目录 (CD2 内部路径)
        """
        conn = self.connection
        try:
            req = conn.pb2.AddOfflineFileRequest(
                urls=urls,
                toFolder=to_folder,
                checkFolderAfterSecs=1
            )
            resp = conn.stub.AddOfflineFiles(req, metadata=conn.get_metadata(), timeout=60)

            if resp.success:
                log_audit("CD2", "添加任务", f"成功添加离线任务到: {to_folder}", details={"client": conn.name})
                return True, "Task added successfully."
            return False, f"CD2 Error: {resp.errorMessage}"
        except grpc.RpcError as e:
            return False, f"RPC Error: {e.details()}"
        except Exception as e:
            return False, f"Exception: {str(e)}"
