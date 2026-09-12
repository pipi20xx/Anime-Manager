import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class CD2ServerInfo:
    """
    CD2 服务器运行信息（参考官方示例的 FileManager 用法）：
    - GetRunningInfo: CPU/内存/实时上下行速度/运行时长
    - GetAllTasksCount: 下载/上传/复制任务数汇总
    - GetSystemInfo: 登录状态/就绪状态
    """
    def __init__(self, connection):
        self.connection = connection

    def running_info(self) -> Dict[str, Any]:
        conn = self.connection
        try:
            resp = conn.stub.GetRunningInfo(conn.pb2.google_dot_protobuf_dot_empty__pb2.Empty(),
                                            metadata=conn.get_metadata(), timeout=15)
            return {
                "cpu_usage": round(float(resp.cpuUsage), 1),
                "mem_used_mb": round(int(resp.memUsageKB) / 1024, 1),
                "mem_total_mb": round(int(resp.totalMemoryKB) / 1024, 1),
                "download_speed": float(resp.downloadBytesPerSecond),
                "upload_speed": float(resp.uploadBytesPerSecond),
                "uptime_sec": int(resp.uptime),
            }
        except Exception as e:
            details = getattr(e, "details", None) or str(e)
            logger.error(f"[{conn.name}] CD2 获取运行信息异常: {details}")
            return {}

    def tasks_count(self) -> Dict[str, Any]:
        conn = self.connection
        try:
            resp = conn.stub.GetAllTasksCount(conn.pb2.google_dot_protobuf_dot_empty__pb2.Empty(),
                                              metadata=conn.get_metadata(), timeout=15)
            return {
                "download_count": int(resp.downloadCount),
                "upload_count": int(resp.uploadCount),
                "copy_task_count": int(resp.copyTaskCount),
            }
        except Exception as e:
            details = getattr(e, "details", None) or str(e)
            logger.error(f"[{conn.name}] CD2 获取任务数异常: {details}")
            return {}

    def system_info(self) -> Dict[str, Any]:
        conn = self.connection
        try:
            resp = conn.stub.GetSystemInfo(conn.pb2.google_dot_protobuf_dot_empty__pb2.Empty(),
                                           metadata=conn.get_metadata(), timeout=15)
            return {
                "is_login": bool(resp.IsLogin),
                "user_name": resp.UserName,
                "system_ready": bool(resp.SystemReady),
                "system_message": resp.SystemMessage or "",
            }
        except Exception as e:
            details = getattr(e, "details", None) or str(e)
            logger.error(f"[{conn.name}] CD2 获取系统信息异常: {details}")
            return {}

    def snapshot(self) -> Dict[str, Any]:
        """一次拉取全部服务器状态（任一失败不影响其他）"""
        return {
            "running": self.running_info(),
            "tasks": self.tasks_count(),
            "system": self.system_info(),
        }
