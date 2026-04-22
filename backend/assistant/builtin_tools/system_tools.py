from ..tools import tool, ToolResult
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@tool(
    name="get_system_status",
    description="获取系统运行状态信息。",
    category="系统管理",
    parameters=[]
)
async def get_system_status() -> ToolResult:
    try:
        import psutil
        import platform
        from datetime import datetime
        
        boot_time = datetime.fromtimestamp(psutil.boot_time())
        
        status = {
            "os": platform.system(),
            "python_version": platform.python_version(),
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory": {
                "total": round(psutil.virtual_memory().total / (1024**3), 2),
                "used": round(psutil.virtual_memory().used / (1024**3), 2),
                "percent": psutil.virtual_memory().percent
            },
            "disk": {
                "total": round(psutil.disk_usage('/').total / (1024**3), 2),
                "used": round(psutil.disk_usage('/').used / (1024**3), 2),
                "percent": psutil.disk_usage('/').percent
            },
            "boot_time": str(boot_time)
        }
        
        return ToolResult(success=True, data=status)
    except ImportError:
        return ToolResult(
            success=True,
            data={"message": "psutil 未安装，无法获取详细系统信息"},
            message="基础模式"
        )
    except Exception as e:
        logger.error(f"[Tool] get_system_status 失败: {e}")
        return ToolResult(success=False, error=str(e))


@tool(
    name="get_config",
    description="获取系统配置信息（敏感信息已脱敏）。",
    category="系统管理",
    parameters=[
        {"name": "key", "type": "string", "description": "配置项名称，不填则返回全部", "required": False}
    ]
)
async def get_config(key: Optional[str] = None) -> ToolResult:
    try:
        from config_manager import ConfigManager
        
        config = ConfigManager.get_config()
        
        sensitive_keys = ["tmdb_api_key", "api_key", "password", "secret", "token"]
        
        def mask_sensitive(d: dict) -> dict:
            result = {}
            for k, v in d.items():
                if any(s in k.lower() for s in sensitive_keys):
                    result[k] = "******"
                elif isinstance(v, dict):
                    result[k] = mask_sensitive(v)
                else:
                    result[k] = v
            return result
        
        if key:
            value = config.get(key)
            if any(s in key.lower() for s in sensitive_keys):
                value = "******"
            return ToolResult(success=True, data={key: value})
        
        masked = mask_sensitive(config)
        return ToolResult(success=True, data=masked)
    except Exception as e:
        logger.error(f"[Tool] get_config 失败: {e}")
        return ToolResult(success=False, error=str(e))


@tool(
    name="list_download_clients",
    description="获取已配置的下载器列表。",
    category="系统管理",
    parameters=[]
)
async def list_download_clients() -> ToolResult:
    try:
        from config_manager import ConfigManager
        
        config = ConfigManager.get_config()
        clients = config.get("download_clients", [])
        
        simplified = []
        for client in clients:
            simplified.append({
                "id": client.get("id"),
                "name": client.get("name"),
                "type": client.get("type"),
                "enabled": client.get("enabled", True),
                "host": client.get("host")
            })
        
        return ToolResult(
            success=True,
            data=simplified,
            message=f"共有 {len(simplified)} 个下载器"
        )
    except Exception as e:
        logger.error(f"[Tool] list_download_clients 失败: {e}")
        return ToolResult(success=False, error=str(e))


@tool(
    name="get_rss_feeds",
    description="获取 RSS 源列表。",
    category="系统管理",
    parameters=[]
)
async def get_rss_feeds() -> ToolResult:
    try:
        from config_manager import ConfigManager
        
        config = ConfigManager.get_config()
        feeds = config.get("rss_feeds", [])
        
        simplified = []
        for feed in feeds:
            simplified.append({
                "id": feed.get("id"),
                "name": feed.get("name"),
                "url": feed.get("url"),
                "enabled": feed.get("enabled", True),
                "interval": feed.get("interval", 30)
            })
        
        return ToolResult(
            success=True,
            data=simplified,
            message=f"共有 {len(simplified)} 个 RSS 源"
        )
    except Exception as e:
        logger.error(f"[Tool] get_rss_feeds 失败: {e}")
        return ToolResult(success=False, error=str(e))


@tool(
    name="get_recent_logs",
    description="获取最近的系统日志。",
    category="系统管理",
    parameters=[
        {"name": "count", "type": "integer", "description": "日志条数，默认 20", "required": False},
        {"name": "level", "type": "string", "description": "日志级别：INFO, WARN, ERROR", "required": False, "enum": ["INFO", "WARN", "ERROR", "DEBUG"]}
    ]
)
async def get_recent_logs(count: int = 20, level: str = "INFO") -> ToolResult:
    try:
        from logger import get_recent_audit_logs
        
        logs = get_recent_audit_logs(count=count, level=level)
        
        return ToolResult(
            success=True,
            data=logs,
            message=f"获取到 {len(logs)} 条日志"
        )
    except Exception as e:
        logger.error(f"[Tool] get_recent_logs 失败: {e}")
        return ToolResult(success=False, error=str(e))


@tool(
    name="search_torrents",
    description="在索引器中搜索种子资源。",
    category="资源搜索",
    parameters=[
        {"name": "query", "type": "string", "description": "搜索关键词", "required": True},
        {"name": "indexer", "type": "string", "description": "索引器名称，默认 all", "required": False}
    ]
)
async def search_torrents(query: str, indexer: str = "all") -> ToolResult:
    try:
        from clients.jackett import JackettClient
        
        results = await JackettClient.search(query, indexer=indexer)
        
        if not results:
            return ToolResult(success=True, data=[], message="未找到结果")
        
        simplified = []
        for item in results[:20]:
            simplified.append({
                "title": item.get("title"),
                "size": item.get("size"),
                "seeders": item.get("seeders"),
                "leechers": item.get("leechers"),
                "link": item.get("link"),
                "indexer": item.get("indexer")
            })
        
        return ToolResult(
            success=True,
            data=simplified,
            message=f"找到 {len(simplified)} 个结果"
        )
    except Exception as e:
        logger.error(f"[Tool] search_torrents 失败: {e}")
        return ToolResult(success=False, error=str(e))


@tool(
    name="add_download_task",
    description="添加下载任务到下载器。",
    category="资源搜索",
    parameters=[
        {"name": "client_id", "type": "string", "description": "下载器 ID", "required": True},
        {"name": "url", "type": "string", "description": "下载链接或磁力链接", "required": True},
        {"name": "save_path", "type": "string", "description": "保存路径", "required": False},
        {"name": "category", "type": "string", "description": "分类标签", "required": False}
    ]
)
async def add_download_task(
    client_id: str,
    url: str,
    save_path: str = "",
    category: str = ""
) -> ToolResult:
    try:
        from clients.manager import ClientManager
        
        success, message = await ClientManager.add_task(
            client_id,
            url,
            save_path=save_path,
            category=category
        )
        
        if success:
            return ToolResult(success=True, message=f"下载任务已添加: {message}")
        else:
            return ToolResult(success=False, error=message)
    except Exception as e:
        logger.error(f"[Tool] add_download_task 失败: {e}")
        return ToolResult(success=False, error=str(e))


@tool(
    name="get_download_tasks",
    description="获取下载器中的任务列表。",
    category="资源搜索",
    parameters=[
        {"name": "client_id", "type": "string", "description": "下载器 ID", "required": True}
    ]
)
async def get_download_tasks(client_id: str) -> ToolResult:
    try:
        from clients.manager import ClientManager
        
        tasks = await ClientManager.get_tasks(client_id)
        
        simplified = []
        for task in tasks[:50]:
            simplified.append({
                "name": task.get("name"),
                "size": task.get("size"),
                "progress": task.get("progress"),
                "state": task.get("state"),
                "download_speed": task.get("download_speed"),
                "save_path": task.get("save_path")
            })
        
        return ToolResult(
            success=True,
            data=simplified,
            message=f"获取到 {len(simplified)} 个任务"
        )
    except Exception as e:
        logger.error(f"[Tool] get_download_tasks 失败: {e}")
        return ToolResult(success=False, error=str(e))
