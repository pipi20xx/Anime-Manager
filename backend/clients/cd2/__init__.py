# CloudDrive2 客户端包
# 对外导出与旧单文件版本 (clients/cd2.py, clients/cd2_helper.py, clients/cd2_monitor.py) 保持兼容
from .client import CD2Client
from .monitor import CD2TransferMonitor
from .proto_loader import ensure_cd2_module
from .offline import torrent_to_magnet

__all__ = ["CD2Client", "CD2TransferMonitor", "ensure_cd2_module", "torrent_to_magnet"]
