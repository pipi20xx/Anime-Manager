import logging
import posixpath
import time
from typing import Dict, Any, List

from logger import log_audit

logger = logging.getLogger(__name__)

# OfflineFileStatus 枚举: OFFLINE_INIT=0; OFFLINE_DOWNLOADING=1; OFFLINE_FINISHED=2; OFFLINE_ERROR=3; OFFLINE_UNKNOWN=4
_STATUS_TEXT = {
    0: "排队中",
    1: "下载中",
    2: "已完成",
    3: "失败",
    4: "未知",
}

_MAX_PAGES = 10


class CD2TaskManager:
    """
    CD2 种子（离线下载）任务管理，严格按官方 gRPC API 定义实现。

    - 账号维度: cloudName + cloudAccountId（取自目录条目的 CloudAPI.name / CloudAPI.userName，
      与 CloudApiChange 事件标识账号的方式一致）
    - path 仅作可选过滤
    - ListAllOfflineFiles 分页列出所有离线文件
    - GetOfflineQuotaInfo 返回 total/used/left
    """
    def __init__(self, connection):
        self.connection = connection
        # 账号解析缓存: path -> (cloudName, cloudAccountId, 解析时间)
        # _resolve_account 需完整列举父目录，云盘上很慢；目录归属极少变化，缓存复用
        self._account_cache: Dict[str, tuple] = {}
        self._account_cache_ttl = 600

    # ---- 账号解析 ----
    def _resolve_account(self, path: str) -> Dict[str, str]:
        """
        解析 path 所属云端账号: 列出父目录，取该条目的 CloudAPI.name / CloudAPI.userName。
        返回 {"cloudName": ..., "cloudAccountId": ...}
        """
        conn = self.connection
        normalized = "/" + (path or "/").strip("/")

        cached = self._account_cache.get(normalized)
        if cached and time.time() - cached[2] < self._account_cache_ttl:
            return {"cloudName": cached[0], "cloudAccountId": cached[1]}

        parent = posixpath.dirname(normalized) or "/"
        name = posixpath.basename(normalized)

        req = conn.pb2.ListSubFileRequest(path=parent, forceRefresh=False)
        for reply in conn.stub.GetSubFiles(req, metadata=conn.get_metadata(), timeout=30):
            if not reply.subFiles:
                continue
            for f in reply.subFiles:
                entry_path = f.fullPathName or f.path or f"/{f.name}"
                if entry_path == normalized or f.name == name:
                    self._account_cache[normalized] = (f.CloudAPI.name, f.CloudAPI.userName, time.time())
                    return {"cloudName": f.CloudAPI.name, "cloudAccountId": f.CloudAPI.userName}

        raise RuntimeError(f"未找到 {normalized} 所属的云端账号")

    # ---- 任务查询 ----
    def _normalize_task(self, f) -> Dict[str, Any]:
        status = int(getattr(f, "status", 4))
        return {
            "info_hash": f.infoHash,
            "name": f.name,
            "url": f.url,
            "parent_id": f.parentId,
            "size": int(f.size),
            "status_code": status,
            "status": _STATUS_TEXT.get(status, "未知"),
            "progress": round(float(f.percendDone), 1),
            "peers": int(f.peers),
            "add_time": int(f.add_time),
        }

    def list_tasks(self, path: str) -> Dict[str, Any]:
        """分页列出当前账号/path 的离线任务 (ListAllOfflineFiles)"""
        conn = self.connection
        try:
            account = self._resolve_account(path)

            tasks: List[Dict[str, Any]] = []
            page = 1
            page_count = 1
            while page <= min(page_count, _MAX_PAGES):
                req = conn.pb2.OfflineFileListAllRequest(
                    cloudName=account["cloudName"],
                    cloudAccountId=account["cloudAccountId"],
                    page=page,
                    path=path,
                )
                resp = conn.stub.ListAllOfflineFiles(req, metadata=conn.get_metadata(), timeout=30)
                tasks.extend(self._normalize_task(f) for f in resp.offlineFiles)
                page_count = int(resp.pageCount) or 1
                page += 1

            return {"success": True, "path": path, "tasks": tasks, "total": len(tasks)}
        except Exception as e:
            details = getattr(e, "details", None) or str(e)
            logger.error(f"[{conn.name}] CD2 获取离线任务列表异常 {path}: {details}")
            return {"success": False, "message": details, "path": path, "tasks": [], "total": 0}

    def get_quota(self, path: str) -> Dict[str, Any]:
        """查询当前账号/path 的离线下载配额 (GetOfflineQuotaInfo: total/used/left)"""
        conn = self.connection
        try:
            account = self._resolve_account(path)
            req = conn.pb2.OfflineQuotaRequest(
                cloudName=account["cloudName"],
                cloudAccountId=account["cloudAccountId"],
                path=path,
            )
            resp = conn.stub.GetOfflineQuotaInfo(req, metadata=conn.get_metadata(), timeout=15)
            return {"total": int(resp.total), "used": int(resp.used), "left": int(resp.left)}
        except Exception as e:
            details = getattr(e, "details", None) or str(e)
            logger.error(f"[{conn.name}] CD2 获取离线配额异常 {path}: {details}")
            return {}

    # ---- 任务操作 ----
    def remove_tasks(self, info_hashes: List[str], path: str, delete_files: bool = False) -> tuple:
        """删除离线任务 (RemoveOfflineFiles)"""
        conn = self.connection
        try:
            account = self._resolve_account(path)

            # 先定位任务，日志里记录任务名便于追溯
            task_names = {}
            try:
                listing = self.list_tasks(path)
                task_names = {t["info_hash"]: t["name"] for t in listing.get("tasks", []) if t.get("info_hash")}
            except Exception:
                pass
            names = [task_names.get(h, h[:12]) for h in info_hashes]

            req = conn.pb2.RemoveOfflineFilesRequest(
                cloudName=account["cloudName"],
                cloudAccountId=account["cloudAccountId"],
                deleteFiles=delete_files,
                infoHashes=info_hashes,
                path=path,
            )
            resp = conn.stub.RemoveOfflineFiles(req, metadata=conn.get_metadata(), timeout=60)
            if resp.success:
                log_audit(
                    "CD2任务", "删除",
                    f"删除 {len(info_hashes)} 个离线任务{' (含文件)' if delete_files else ''}: {'、'.join(names)}",
                    details=f"路径: {path} | infoHashes: {', '.join(info_hashes)}",
                )
                return True, "Success"
            return False, resp.errorMessage or "删除失败"
        except Exception as e:
            details = getattr(e, "details", None) or str(e)
            logger.error(f"[{conn.name}] CD2 删除离线任务异常: {details}")
            return False, details

    def clear_tasks(self, filter_code: int, path: str, delete_files: bool = False) -> tuple:
        """
        按筛选类型清空离线任务 (ClearOfflineFiles)。
        Filter 枚举: All=0; Finished=1; Error=2; Downloading=3
        官方响应为 google.protobuf.Empty，无异常即成功。
        """
        conn = self.connection
        filter_text = {0: "全部", 1: "已完成", 2: "错误", 3: "下载中"}.get(filter_code, str(filter_code))
        try:
            account = self._resolve_account(path)
            req = conn.pb2.ClearOfflineFileRequest(
                cloudName=account["cloudName"],
                cloudAccountId=account["cloudAccountId"],
                filter=filter_code,
                deleteFiles=delete_files,
                path=path,
            )
            conn.stub.ClearOfflineFiles(req, metadata=conn.get_metadata(), timeout=120)
            log_audit(
                "CD2任务", "清空",
                f"清空「{filter_text}」离线任务{' (含文件)' if delete_files else ''}",
                details=f"路径: {path}",
            )
            return True, "Success"
        except Exception as e:
            details = getattr(e, "details", None) or str(e)
            logger.error(f"[{conn.name}] CD2 清空离线任务异常: {details}")
            return False, details

    def restart_task(self, info_hash: str, url: str, parent_id: str, path: str) -> tuple:
        """重启失败的离线任务 (RestartOfflineTask)"""
        conn = self.connection
        try:
            account = self._resolve_account(path)
            req = conn.pb2.RestartOfflineFileRequest(
                cloudName=account["cloudName"],
                cloudAccountId=account["cloudAccountId"],
                infoHash=info_hash,
                url=url,
                parentId=parent_id,
                path=path,
            )
            conn.stub.RestartOfflineTask(req, metadata=conn.get_metadata(), timeout=60)
            log_audit("CD2任务", "重启", f"重启离线任务: {info_hash}", details=f"路径: {path}")
            return True, "Success"
        except Exception as e:
            details = getattr(e, "details", None) or str(e)
            logger.error(f"[{conn.name}] CD2 重启离线任务异常: {details}")
            return False, details
