from fastapi import APIRouter, HTTPException, Body
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from config_manager import ConfigManager
from clients.manager import ClientManager
from clients.base_client import BaseClient
from clients.qbittorrent import QBClient
from clients.cd2 import CD2Client
from clients.jackett import JackettClient
from clients.space_cleanup import group_torrents_by_path, select_torrents_for_deletion, format_size, GB
from clients.space_cleanup_task import run_space_cleanup
from logger import log_audit
from monitor import MonitorManager
import asyncio
import requests

router = APIRouter(tags=["下载与外部客户端"])

@router.get("/jackett/search", summary="Jackett 资源搜索")
async def search_jackett(keyword: str, indexer: Optional[str] = "all"):
    """
    通过 Jackett 聚合搜索资源。可选指定特定的 Indexer ID。
    """
    results = await JackettClient.search(keyword, indexer=indexer)
    return results

@router.get("/jackett/indexers", summary="获取 Jackett 站点列表")
async def get_jackett_indexers():
    """
    获取 Jackett 中已配置的可用站点列表。
    """
    return await JackettClient.get_indexers()

class ManualDownloadRequest(BaseModel):
    client_id: str
    url: str
    save_path: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[str] = None

@router.get("/clients", response_model=List[Dict[str, Any]], summary="获取客户端列表")
async def get_clients():
    """
    返回系统当前配置的所有下载客户端 (qBit, CD2等)。
    """
    return ClientManager.get_all_clients()

@router.post("/clients", summary="保存客户端配置")
async def save_clients(clients: List[Dict[str, Any]] = Body(...)):
    """
    批量更新下载客户端配置。
    """
    cd2_clients = [c for c in clients if c.get('type') == 'cd2']
    if len(cd2_clients) > 1:
        raise HTTPException(status_code=400, detail="系统中仅允许配置一个 CloudDrive2 客户端实例。")

    import uuid
    for c in clients:
        if not c.get('id'):
            c['id'] = str(uuid.uuid4())[:8]
    
    ConfigManager.update_config({"download_clients": clients})
    await MonitorManager.reload()
    log_audit("系统", "客户端更新", f"更新了下载客户端配置 (共 {len(clients)} 个)")
    return {"message": "Clients configuration saved."}

@router.post("/clients/test", summary="测试客户端连接")
async def test_client(client_config: Dict[str, Any] = Body(...)):
    """
    针对给定的配置参数进行即时的连接性测试。
    """
    # Temporarily instantiate the client to test connection
    client: BaseClient = None
    ctype = client_config.get('type', 'qbittorrent').lower()
    
    try:
        if ctype == 'qbittorrent':
            client = await asyncio.to_thread(QBClient, client_config)
        elif ctype == 'cd2':
            client = await asyncio.to_thread(CD2Client, client_config)
        else:
            return {"success": False, "message": f"Unknown client type: {ctype}"}
        
        return await asyncio.to_thread(client.test_connection)
    except Exception as e:
        return {"success": False, "message": f"Test failed: {str(e)}"}

@router.post("/clients/download", summary="执行手动下载任务")
async def manual_download(req: ManualDownloadRequest):
    """
    手动推送一个下载链接（磁力、种子链接）到指定的下载客户端。
    """
    try:
        # Construct kwargs from request
        kwargs = {}
        if req.save_path: kwargs['save_path'] = req.save_path
        if req.category: kwargs['category'] = req.category
        if req.tags: kwargs['tags'] = req.tags

        # Use the unified manager to handle the task
        success, msg = await ClientManager.add_task(req.client_id, req.url, **kwargs)

        # Retrieve client name for logging (optional, requires fetching client again or changing return signature)
        # ClientManager.add_task checks for client existence.
        # Let's get client name for audit log
        client = ClientManager.get_client(req.client_id)
        client_name = client.name if client else req.client_id

        if success:
            log_audit("手动下载", "添加成功", f"任务已推送到 {client_name}: {req.url}", details=req.url)
            return {"success": True, "message": f"已推送到 {client_name}"}
        else:
            log_audit("手动下载", "添加失败", f"客户端 {client_name} 返回错误", level="ERROR", details=msg)
            return {"success": False, "message": f"推送失败: {msg}"}
            
    except Exception as e:
        log_audit("手动下载", "异常", str(e), level="ERROR")
        return {"success": False, "message": f"系统异常: {str(e)}"}


# ════════════════════════════════════════════════════════
# 磁盘空间回收 API
# ════════════════════════════════════════════════════════

@router.get("/clients/torrents", summary="获取客户端种子列表")
async def get_torrents(client_id: str):
    """
    获取指定 QB 客户端中的种子列表，包含名称、状态、进度、体积、路径等信息。
    """
    client = ClientManager.get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="客户端未找到")

    if not isinstance(client, QBClient):
        raise HTTPException(status_code=400, detail="该客户端类型不支持种子列表查询")

    torrents = await asyncio.to_thread(client.get_torrents, "all")
    return {
        "client_name": client.name,
        "total": len(torrents),
        "torrents": [
            {
                "hash": t.get("hash", ""),
                "name": t.get("name", ""),
                "state": t.get("state", ""),
                "progress": round(float(t.get("progress", 0) or 0) * 100, 1),
                "size": int(t.get("size", 0) or 0),
                "size_display": format_size(int(t.get("size", 0) or 0)),
                "save_path": t.get("save_path", ""),
                "content_path": t.get("content_path", ""),
                "added_on": t.get("added_on", 0),
                "category": t.get("category", ""),
                "tags": t.get("tags", ""),
                "num_seeds": t.get("num_seeds", 0),
                "dlspeed": t.get("dlspeed", 0),
                "upspeed": t.get("upspeed", 0),
            }
            for t in torrents
        ],
    }


@router.get("/clients/space-cleanup/preview", summary="预览空间回收结果")
async def preview_space_cleanup(rule_index: Optional[int] = None):
    """
    预览空间回收：不执行删除，仅返回当前规则下各路径的占用情况及计划删除的种子。
    :param rule_index: 指定规则索引（从 0 开始），不传则预览所有规则
    """
    config = ConfigManager.get_config()
    all_rules = config.get("space_cleanup_rules", [])
    if not all_rules:
        return {"rules": [], "message": "未配置空间回收规则"}

    # ── 如果指定了 rule_index，只预览单条规则 ──
    if rule_index is not None:
        if rule_index < 0 or rule_index >= len(all_rules):
            return {"rules": [], "message": f"无效的规则索引: {rule_index}"}
        rules = [all_rules[rule_index]]
    else:
        rules = all_rules

    client_configs = ClientManager.get_all_clients()
    all_groups: List[Dict[str, Any]] = []

    for conf in client_configs:
        client = ClientManager.get_client(conf.get("id"))
        if not client or not isinstance(client, QBClient):
            continue

        torrents = await asyncio.to_thread(client.get_torrents, "all")
        if not torrents:
            continue

        groups = group_torrents_by_path(torrents, rules, client_id=conf.get("id"))
        for group in groups:
            group["client_name"] = client.name
            group["client_id"] = conf.get("id")
            to_delete = select_torrents_for_deletion(group)
            group["torrents_to_delete"] = [
                {
                    "hash": t.get("hash", ""),
                    "name": t.get("name", ""),
                    "size": int(t.get("size", 0) or 0),
                    "size_display": format_size(int(t.get("size", 0) or 0)),
                    "added_on": t.get("added_on", 0),
                    "state": t.get("state", ""),
                    "category": t.get("category", ""),
                    "tags": t.get("tags", ""),
                }
                for t in to_delete
            ]
            # 不需要把完整 torrents 列表返回给前端（太大）
            group.pop("torrents", None)
            all_groups.append(group)

    return {
        "rules": rules,
        "groups": all_groups,
        "total_to_delete": sum(len(g.get("torrents_to_delete", [])) for g in all_groups),
    }


@router.post("/clients/space-cleanup/run", summary="手动触发空间回收")
async def trigger_space_cleanup(rule_index: Optional[int] = None):
    """
    手动触发一次磁盘空间回收任务（忽略 enabled 开关）。
    :param rule_index: 指定规则索引（从 0 开始），不传则执行所有规则
    """
    label = f"规则 #{rule_index + 1}" if rule_index is not None else "全部规则"
    log_audit("空间回收", "手动触发", f"用户手动触发磁盘空间回收 ({label})")
    stats = await run_space_cleanup(manual=True, rule_index=rule_index)
    return {"success": True, "stats": stats}
