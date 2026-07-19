from ..tools import tool, ToolResult
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@tool(
    name="get_system_status",
    description="获取系统运行状态信息，包括 CPU、内存、磁盘使用率等。",
    category="系统管理",
    parameters=[]
)
async def get_system_status() -> ToolResult:
    try:
        import psutil
        import platform
        import asyncio
        from datetime import datetime

        def _collect():
            # cpu_percent(interval=None) 非阻塞，返回上次调用以来的 CPU 平均使用率
            # 首次调用返回 0.0，属正常现象
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            return {
                "os": platform.system(),
                "python_version": platform.python_version(),
                "cpu_percent": psutil.cpu_percent(interval=None),
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

        # psutil 调用可能涉及系统调用，整体扔进线程池避免阻塞事件循环
        status = await asyncio.to_thread(_collect)

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
    description="获取系统配置信息（敏感信息已脱敏）。可指定 key 获取单项配置。",
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
    name="get_recent_logs",
    description="获取最近的系统审计日志。",
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
    name="get_cache_stats",
    description="获取工具查询缓存的统计信息，包括命中率和缓存条目数。",
    category="系统管理",
    parameters=[]
)
async def get_cache_stats() -> ToolResult:
    try:
        from ..cache import query_cache

        stats = query_cache.get_stats()
        return ToolResult(success=True, data=stats, message=f"缓存命中率: {stats.get('hit_rate', '0%')}")
    except Exception as e:
        logger.error(f"[Tool] get_cache_stats 失败: {e}")
        return ToolResult(success=False, error=str(e))
