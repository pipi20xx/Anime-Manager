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

    # ---- 实时传输任务（只读展示，与后台联动监控互不影响） ----
    # UploadFileInfo.Status 枚举
    _UPLOAD_STATUS_TEXT = {
        0: "等待预处理", 1: "预处理中", 2: "已取消", 3: "传输中", 4: "暂停",
        5: "完成", 6: "已跳过", 7: "排队中", 8: "已忽略", 9: "错误", 10: "致命错误",
    }
    # UploadFileInfo.OperatorType 枚举
    _OPERATOR_TEXT = {0: "挂载", 1: "复制", 2: "备份", 3: "远程上传"}

    def upload_transfers(self) -> Dict[str, Any]:
        """上传类任务（含复制/远程上传/挂载），GetUploadFileList getAll"""
        conn = self.connection
        result: Dict[str, Any] = {"uploads": [], "speed": 0.0}
        try:
            req = conn.pb2.GetUploadFileListRequest(getAll=True, itemsPerPage=100, pageNumber=0, filter="")
            resp = conn.stub.GetUploadFileList(req, metadata=conn.get_metadata(), timeout=30)
            result["speed"] = float(resp.globalBytesPerSecond)
            for f in resp.uploadFiles:
                size = int(f.size)
                transfered = int(f.transferedBytes)
                status_enum = int(getattr(f, "statusEnum", -1))
                result["uploads"].append({
                    "key": f.key,
                    "path": f.destPath,
                    "name": f.destPath.rsplit("/", 1)[-1] if f.destPath else "",
                    "size": size,
                    "transfered": transfered,
                    "progress": round(transfered / size * 100, 1) if size > 0 else 0.0,
                    "status_enum": status_enum,
                    "status": self._UPLOAD_STATUS_TEXT.get(status_enum, f.status or "未知"),
                    "operator_type": int(f.operatorType),
                    "operator": self._OPERATOR_TEXT.get(int(f.operatorType), "未知"),
                    "error": f.errorMessage,
                })
        except Exception as e:
            details = getattr(e, "details", None) or str(e)
            logger.error(f"[{conn.name}] CD2 获取上传任务列表异常: {details}")
            result["error"] = details
        return result

    def download_transfers(self) -> Dict[str, Any]:
        """下载类任务，GetDownloadFileList"""
        conn = self.connection
        result: Dict[str, Any] = {"downloads": [], "speed": 0.0}
        try:
            resp = conn.stub.GetDownloadFileList(
                conn.pb2.google_dot_protobuf_dot_empty__pb2.Empty(),
                metadata=conn.get_metadata(), timeout=30,
            )
            result["speed"] = float(resp.globalBytesPerSecond)
            for f in resp.downloadFiles:
                length = int(f.fileLength)
                buffered = int(f.totalBufferUsed)
                result["downloads"].append({
                    "path": f.filePath,
                    "name": f.filePath.rsplit("/", 1)[-1] if f.filePath else "",
                    "length": length,
                    "buffered": buffered,
                    "progress": round(buffered / length * 100, 1) if length > 0 else 0.0,
                    "threads": int(f.downloadThreadCount),
                    "speed": float(f.bytesPerSecond),
                    "last_error": f.lastDownloadError or "",
                })
        except Exception as e:
            details = getattr(e, "details", None) or str(e)
            logger.error(f"[{conn.name}] CD2 获取下载任务列表异常: {details}")
            result["error"] = details
        return result

    def transfers(self) -> Dict[str, Any]:
        """上传+下载实时任务（任一失败不影响另一个）"""
        up = self.upload_transfers()
        down = self.download_transfers()
        return {
            "uploads": up.get("uploads", []),
            "downloads": down.get("downloads", []),
            "upload_speed": up.get("speed", 0.0),
            "download_speed": down.get("speed", 0.0),
            "upload_error": up.get("error"),
            "download_error": down.get("error"),
        }
