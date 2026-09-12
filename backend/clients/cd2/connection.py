import grpc
import logging
from typing import Dict, Any, Optional, Tuple

from .proto_loader import ensure_cd2_module

logger = logging.getLogger(__name__)


class CD2Connection:
    """
    CD2 gRPC 连接层：负责 channel/stub 的创建、登录鉴权与 token 管理。
    CD2Client 与 CD2TransferMonitor 共用此连接逻辑。
    """
    def __init__(self, client_config: Dict[str, Any]):
        self.name = client_config.get('name', 'CD2')
        self.host = client_config.get('url', '').replace("http://", "").replace("https://", "").rstrip("/")
        self.username = client_config.get('username', '')
        self.password = client_config.get('password', '')
        self.api_token = client_config.get('api_token', '')

        self.pb2, self.pb2_grpc = ensure_cd2_module()
        self.channel = None
        self.stub = None
        self.token = None
        self.logged_in = False
        self._async_channel = None
        self._async_stub = None

    def _connect(self) -> bool:
        if not self.pb2 or not self.pb2_grpc:
            logger.error(f"[{self.name}] CD2 modules not available.")
            return False

        if self.channel is None:
            self.channel = grpc.insecure_channel(self.host)
            self.stub = self.pb2_grpc.CloudDriveFileSrvStub(self.channel)
        return True

    async def _get_async_stub(self):
        """获取异步 gRPC Stub"""
        if self._async_channel is None:
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

    async def close_async(self):
        """关闭异步连接"""
        if self._async_channel:
            await self._async_channel.close()
            self._async_channel = None
