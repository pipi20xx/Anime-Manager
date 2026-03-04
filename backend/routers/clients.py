from fastapi import APIRouter, HTTPException, Body
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from config_manager import ConfigManager
from clients.manager import ClientManager
from clients.base_client import BaseClient
from clients.qbittorrent import QBClient
from clients.cd2 import CD2Client
from clients.jackett import JackettClient
from logger import log_audit
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
    # 限制只能有一个 CD2 客户端
    cd2_clients = [c for c in clients if c.get('type') == 'cd2']
    if len(cd2_clients) > 1:
        raise HTTPException(status_code=400, detail="系统中仅允许配置一个 CloudDrive2 客户端实例。")

    # Add IDs if missing (simple generation)
    import uuid
    for c in clients:
        if not c.get('id'):
            c['id'] = str(uuid.uuid4())[:8]
    
    ConfigManager.update_config({"download_clients": clients})
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
            client = QBClient(client_config)
        elif ctype == 'cd2':
            client = CD2Client(client_config)
        else:
            return {"success": False, "message": f"Unknown client type: {ctype}"}
        
        return client.test_connection()
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
