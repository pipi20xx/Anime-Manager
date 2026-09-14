from fastapi import APIRouter, HTTPException, UploadFile, File, Request
from pydantic import BaseModel
from typing import List, Optional
import asyncio
import logging

from config_manager import ConfigManager
from clients.manager import ClientManager
from clients.cd2.proto_loader import get_proto_info, force_update_proto
from logger import log_audit

router = APIRouter(tags=["CD2管理"])
logger = logging.getLogger("CD2Manage")


def _get_cd2_client(client_id: Optional[str] = None):
    """
    定位 CD2 客户端实例（复用 ClientManager 缓存的已登录实例）。
    client_id 为空时取配置中第一个 cd2 类型客户端。
    """
    config = ConfigManager.get_config()
    clients_conf = config.get("download_clients", [])

    if client_id:
        target = next((c for c in clients_conf if c.get("id") == client_id and c.get("type") == "cd2"), None)
    else:
        target = next((c for c in clients_conf if c.get("type") == "cd2"), None)

    if not target:
        raise HTTPException(status_code=400, detail="未找到已配置的 CloudDrive2 客户端，请先在系统设置中添加")

    client = ClientManager.get_client(target.get("id"))
    if not client:
        raise HTTPException(status_code=400, detail="CD2 客户端初始化失败，请检查配置")
    return client


@router.get("/cd2/offline-tasks", summary="获取 CD2 离线（种子）任务列表（按路径）")
async def get_offline_tasks(path: str, client_id: Optional[str] = None):
    if not path or not path.startswith("/"):
        raise HTTPException(status_code=400, detail="需要有效的 CD2 路径（如 /115open）")
    client = _get_cd2_client(client_id)
    result = await asyncio.to_thread(client.list_offline_tasks, path)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "获取离线任务失败"))
    return result


class AddOfflineUrlsRequest(BaseModel):
    urls: str
    to_folder: str
    client_id: Optional[str] = None


@router.post("/cd2/offline-tasks/add", summary="提交离线下载链接")
async def add_offline_urls(req: AddOfflineUrlsRequest):
    if not req.urls.strip():
        raise HTTPException(status_code=400, detail="未提供离线下载链接")
    if not req.to_folder.startswith("/"):
        raise HTTPException(status_code=400, detail="目标目录无效")

    client = _get_cd2_client(req.client_id)
    success, msg = await asyncio.to_thread(client.add_offline_urls, req.urls.strip(), req.to_folder)
    if not success:
        log_audit("CD2任务", "添加失败", f"添加离线任务失败: {msg}", level="ERROR", details=f"目标: {req.to_folder}")
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": "任务已提交"}


class DeleteOfflineTasksRequest(BaseModel):
    info_hashes: List[str]
    path: str
    delete_files: bool = False
    client_id: Optional[str] = None


@router.post("/cd2/offline-tasks/delete", summary="删除 CD2 离线任务")
async def delete_offline_tasks(req: DeleteOfflineTasksRequest):
    if not req.info_hashes:
        raise HTTPException(status_code=400, detail="未指定要删除的任务")
    if not req.path.startswith("/"):
        raise HTTPException(status_code=400, detail="路径无效")

    client = _get_cd2_client(req.client_id)
    success, msg = await asyncio.to_thread(client.remove_offline_tasks, req.info_hashes, req.path, req.delete_files)
    if not success:
        log_audit("CD2任务", "删除失败", f"删除离线任务失败: {msg}", level="ERROR")
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": f"已删除 {len(req.info_hashes)} 个任务"}


class RestartOfflineTaskRequest(BaseModel):
    info_hash: str
    url: str = ""
    parent_id: str = ""
    path: str
    client_id: Optional[str] = None


@router.post("/cd2/offline-tasks/restart", summary="重启 CD2 离线任务")
async def restart_offline_task(req: RestartOfflineTaskRequest):
    client = _get_cd2_client(req.client_id)
    success, msg = await asyncio.to_thread(
        client.restart_offline_task, req.info_hash, req.url, req.parent_id, req.path
    )
    if not success:
        log_audit("CD2任务", "重启失败", f"重启离线任务失败: {msg}", level="ERROR")
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": "任务已重启"}


class ClearOfflineTasksRequest(BaseModel):
    filter: int  # 0=全部 1=已完成 2=错误 3=下载中
    path: str
    delete_files: bool = False
    client_id: Optional[str] = None


@router.post("/cd2/offline-tasks/clear", summary="按类型清空 CD2 离线任务")
async def clear_offline_tasks(req: ClearOfflineTasksRequest):
    if req.filter not in (0, 1, 2, 3):
        raise HTTPException(status_code=400, detail="无效的清空类型")

    client = _get_cd2_client(req.client_id)
    success, msg = await asyncio.to_thread(client.clear_offline_tasks, req.filter, req.path, req.delete_files)
    if not success:
        log_audit("CD2任务", "清空失败", f"清空离线任务失败: {msg}", level="ERROR")
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": "清空完成"}


@router.get("/cd2/monitor", summary="获取 CD2 传输监控状态")
async def get_monitor_status():
    from clients.cd2 import CD2TransferMonitor

    config = ConfigManager.get_config()
    cd2_conf = next((c for c in config.get("download_clients", []) if c.get("type") == "cd2"), None)

    monitor_enabled = cd2_conf.get("monitor_enabled", None) if cd2_conf else None
    if monitor_enabled is None:
        monitor_enabled = config.get("enable_cd2_monitor", True)

    instance = CD2TransferMonitor._instance
    thread = CD2TransferMonitor._thread
    running = instance is not None and thread is not None and thread.is_alive()

    cache = dict(instance.last_scan_cache) if instance else {}
    watching = [
        {
            "path": path,
            "name": info.get("name", ""),
            "status": info.get("status", ""),
            "type": info.get("type", 0),
        }
        for path, info in cache.items()
    ]

    # 实时传输任务（上传/下载完整信息；失败或未配置时不影响联动监控状态展示）
    transfers = {"uploads": [], "downloads": [], "upload_speed": 0.0, "download_speed": 0.0}
    try:
        client = _get_cd2_client()
        transfers = await asyncio.to_thread(client._server_info.transfers)
    except HTTPException:
        pass
    except Exception as e:
        logger.warning(f"获取实时传输任务失败: {e}")

    return {
        "configured": cd2_conf is not None,
        "enabled": bool(monitor_enabled) and cd2_conf is not None,
        "running": running,
        "interval": cd2_conf.get("monitor_interval", 5) if cd2_conf else 5,
        "watching_count": len(watching),
        "watching": watching,
        "transfers": transfers,
    }


@router.get("/cd2/files", summary="浏览 CD2 文件目录")
async def browse_files(path: str = "/", refresh: bool = False, client_id: Optional[str] = None):
    client = _get_cd2_client(client_id)
    result = await asyncio.to_thread(client.browse_files, path or "/", refresh)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "列目录失败"))
    return result


class CreateFolderRequest(BaseModel):
    parent_path: str
    name: str
    client_id: Optional[str] = None


@router.post("/cd2/files/create-folder", summary="新建文件夹")
async def create_folder(req: CreateFolderRequest):
    client = _get_cd2_client(req.client_id)
    success, msg = await asyncio.to_thread(client.create_folder, req.parent_path, req.name)
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": "创建成功"}


class RenamePathRequest(BaseModel):
    path: str
    new_name: str
    client_id: Optional[str] = None


@router.post("/cd2/files/rename", summary="重命名文件/文件夹")
async def rename_path(req: RenamePathRequest):
    client = _get_cd2_client(req.client_id)
    success, msg = await asyncio.to_thread(client.rename_path, req.path, req.new_name)
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": "重命名成功"}


class OrganizeRenameRequest(BaseModel):
    path: str
    new_relative_path: str
    client_id: Optional[str] = None


@router.post("/cd2/files/organize-rename", summary="识别后的整理式重命名（可含子目录）")
async def organize_rename(req: OrganizeRenameRequest):
    if not req.new_relative_path.strip():
        raise HTTPException(status_code=400, detail="目标路径为空")

    client = _get_cd2_client(req.client_id)
    success, msg = await asyncio.to_thread(client.organize_rename, req.path, req.new_relative_path.strip("/"))
    if not success:
        log_audit("CD2文件", "识别重命名失败", f"{req.path}: {msg}", level="ERROR")
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "final_path": msg}


class DeletePathsRequest(BaseModel):
    paths: List[str]
    client_id: Optional[str] = None


@router.post("/cd2/files/delete", summary="删除文件/文件夹")
async def delete_paths(req: DeletePathsRequest):
    if not req.paths:
        raise HTTPException(status_code=400, detail="未指定要删除的文件")

    client = _get_cd2_client(req.client_id)
    success, msg = await asyncio.to_thread(client.delete_paths, req.paths)
    if not success:
        log_audit("CD2文件", "删除失败", f"删除文件失败: {msg}", level="ERROR")
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": f"已删除 {len(req.paths)} 项"}


class TransferPathsRequest(BaseModel):
    paths: List[str]
    dest_dir: str
    action: str = "move"  # move | copy
    conflict_policy: int = 1  # 0=覆盖 1=重命名 2=跳过
    client_id: Optional[str] = None


@router.post("/cd2/files/transfer", summary="移动/复制文件")
async def transfer_paths(req: TransferPathsRequest):
    if not req.paths:
        raise HTTPException(status_code=400, detail="未指定要操作的文件")
    if req.action not in ("move", "copy"):
        raise HTTPException(status_code=400, detail=f"不支持的操作类型: {req.action}")

    client = _get_cd2_client(req.client_id)
    success, msg = await asyncio.to_thread(
        client.transfer_paths, req.paths, req.dest_dir, req.action, req.conflict_policy
    )
    if not success:
        verb = "移动" if req.action == "move" else "复制"
        log_audit("CD2文件", f"{verb}失败", f"{verb}文件失败: {msg}", level="ERROR")
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": f"{'移动' if req.action == 'move' else '复制'}成功"}


@router.get("/cd2/server-info", summary="获取 CD2 服务器运行状态")
async def get_server_info(client_id: Optional[str] = None):
    client = _get_cd2_client(client_id)
    return await asyncio.to_thread(client.get_server_info)


_MAX_UPLOAD_SIZE = 500 * 1024 * 1024  # 500MB


@router.post("/cd2/files/upload", summary="上传文件到 CD2 目录")
async def upload_file(path: str, file: UploadFile = File(...), client_id: Optional[str] = None):
    if not path or not path.startswith("/"):
        raise HTTPException(status_code=400, detail="目标目录无效")
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名无效")

    data = await file.read()
    if len(data) > _MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail="文件超过 500MB 上传限制，请使用 CD2 官方客户端上传大文件")

    client = _get_cd2_client(client_id)
    success, msg = await asyncio.to_thread(client.upload_file, path, file.filename, data)
    if not success:
        log_audit("CD2文件", "上传失败", f"上传 {file.filename} 失败: {msg}", level="ERROR")
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": f"已上传 {file.filename}"}


class RemoteUploadStartRequest(BaseModel):
    path: str
    file_name: str
    size: int
    client_id: Optional[str] = None


@router.post("/cd2/upload/remote", summary="启动远程上传会话 (Remote Upload 协议)")
async def remote_upload_start(req: RemoteUploadStartRequest):
    if not req.path.startswith("/"):
        raise HTTPException(status_code=400, detail="目标目录无效")
    if req.size < 0:
        raise HTTPException(status_code=400, detail="文件大小无效")

    client = _get_cd2_client(req.client_id)
    result = await asyncio.to_thread(client.start_remote_upload, req.path, req.file_name, req.size)
    if not result.get("upload_id"):
        raise HTTPException(status_code=400, detail=result.get("message", "启动远程上传失败"))
    return result


@router.get("/cd2/upload/remote/{upload_id}/next", summary="长轮询获取下一个上传任务")
async def remote_upload_next(upload_id: str):
    client = _get_cd2_client()
    return await asyncio.to_thread(client.remote_upload_next, upload_id)


@router.post("/cd2/upload/remote/{upload_id}/data", summary="回传远程上传分块数据")
async def remote_upload_data(upload_id: str, request: Request, request_id: str):
    data = await request.body()
    if not data:
        raise HTTPException(status_code=400, detail="数据为空")
    client = _get_cd2_client()
    result = await asyncio.to_thread(client.remote_upload_data, upload_id, request_id, data)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "回传失败"))
    return result


@router.post("/cd2/upload/remote/{upload_id}/cancel", summary="取消远程上传")
async def remote_upload_cancel(upload_id: str):
    client = _get_cd2_client()
    return await asyncio.to_thread(client.remote_upload_cancel, upload_id)


@router.get("/cd2/proto", summary="获取 CD2 协议文件信息")
async def get_proto():
    return get_proto_info()


@router.post("/cd2/proto/force-update", summary="强制更新 CD2 协议")
async def force_update():
    log_audit("CD2协议", "强制更新", "手动触发 clouddrive.proto 下载与重新编译...")
    result = await asyncio.to_thread(force_update_proto)
    if result.get("success"):
        log_audit("CD2协议", "更新完成", result.get("message", ""), details=f"新 Hash: {result.get('hash')}")
    else:
        log_audit("CD2协议", "更新失败", result.get("message", ""), level="ERROR")
    return result


# ---------------------------------------------------------------------------
# 神医深度删除联动配置 (deep.delete → CD2)
# ---------------------------------------------------------------------------

class DeepDeleteConfig(BaseModel):
    enabled: bool = False
    delete_preference: str = "files"  # files | folder | auto
    permanent_delete: bool = False     # True=永久删除, False=删除到回收站
    notify_on_delete: bool = True       # 联动删除后是否发送 TG 通知
    cleanup_empty_folder: bool = False  # 删除文件后检查并清理空的父文件夹
    path_mappings: List[dict] = []  # [{"from": "...", "to": "..."}]


@router.get("/cd2/deep-delete", summary="获取深度删除联动配置")
async def get_deep_delete_config():
    config = ConfigManager.get_config()
    dd = config.get("deep_delete", {})
    return {
        "enabled": dd.get("enabled", False),
        "delete_preference": dd.get("delete_preference", "files"),
        "permanent_delete": dd.get("permanent_delete", False),
        "notify_on_delete": dd.get("notify_on_delete", True),
        "cleanup_empty_folder": dd.get("cleanup_empty_folder", False),
        "path_mappings": dd.get("path_mappings", []),
    }


@router.post("/cd2/deep-delete", summary="保存深度删除联动配置")
async def save_deep_delete_config(req: DeepDeleteConfig):
    ConfigManager.update_config({"deep_delete": req.model_dump()})
    action = "永久删除" if req.permanent_delete else "删除到回收站"
    log_audit("神医深度删除联动", "配置更新",
              f"联动删除已{'启用' if req.enabled else '禁用'}，删除偏好: {req.delete_preference}，{action}，TG通知: {'开' if req.notify_on_delete else '关'}，清理空文件夹: {'开' if req.cleanup_empty_folder else '关'}，映射规则: {len(req.path_mappings)} 条")
    return {"success": True, "message": "配置已保存"}
