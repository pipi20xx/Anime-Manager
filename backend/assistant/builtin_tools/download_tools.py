from ..tools import tool, ToolResult
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@tool(
    name="run_rss_refresh",
    description="手动执行 RSS 订阅源刷新，检查并下载新资源。",
    category="下载管理",
    parameters=[]
)
async def run_rss_refresh() -> ToolResult:
    try:
        from rss_core.rss_manager import RSSManager
        
        result = await RSSManager.refresh_all_feeds()
        
        return ToolResult(
            success=True,
            data={
                "checked": result.get("checked", 0),
                "downloaded": result.get("downloaded", 0),
                "skipped": result.get("skipped", 0),
                "errors": result.get("errors", 0)
            },
            message=f"RSS 刷新完成: 检查 {result.get('checked', 0)} 项, 下载 {result.get('downloaded', 0)} 项"
        )
    except Exception as e:
        logger.error(f"[Tool] run_rss_refresh 失败: {e}")
        return ToolResult(success=False, error=str(e))


@tool(
    name="get_download_history",
    description="获取最近的下载历史记录。",
    category="下载管理",
    parameters=[
        {"name": "limit", "type": "integer", "description": "返回记录数量，默认 20", "required": False}
    ]
)
async def get_download_history(limit: int = 20) -> ToolResult:
    try:
        from database import db
        from models import DownloadHistory
        from sqlmodel import select, desc
        
        async with db.session_scope():
            stmt = select(DownloadHistory).order_by(desc(DownloadHistory.id)).limit(limit)
            history = await db.all(DownloadHistory, stmt)
        
        result = []
        for item in history:
            result.append({
                "id": item.id,
                "title": item.title,
                "guid": item.guid,
                "downloaded_at": str(item.downloaded_at) if hasattr(item, "downloaded_at") else None,
                "rule_id": item.rule_id,
                "feed_id": item.feed_id
            })
        
        if not result:
            formatted = "📭 暂无下载记录"
        else:
            lines = ["📥 **下载历史**\n"]
            lines.append("| ID | 标题 | 下载时间 |")
            lines.append("|:--:|:-----|:---------|")
            for item in result[:15]:
                time_str = item.get("downloaded_at", "-")[:19] if item.get("downloaded_at") else "-"
                lines.append(f"| {item['id']} | {item['title'][:30]} | {time_str} |")
            formatted = "\n".join(lines)
        
        return ToolResult(
            success=True,
            data=result,
            message=f"最近 {len(result)} 条下载记录",
            formatted_message=formatted
        )
    except Exception as e:
        logger.error(f"[Tool] get_download_history 失败: {e}")
        return ToolResult(success=False, error=str(e))


@tool(
    name="get_download_status",
    description="获取下载客户端的状态和当前下载任务。",
    category="下载管理",
    parameters=[]
)
async def get_download_status() -> ToolResult:
    try:
        from clients.manager import ClientManager
        from config_manager import ConfigManager
        
        client = ClientManager.get_client()
        
        if not client:
            return ToolResult(success=False, error="未配置下载客户端")
        
        status = await client.get_status()
        downloads = await client.get_downloads()
        
        return ToolResult(
            success=True,
            data={
                "client_type": client.__class__.__name__,
                "status": status,
                "downloads": downloads[:10] if downloads else []
            },
            message=f"客户端状态: {status.get('status', 'unknown')}"
        )
    except Exception as e:
        logger.error(f"[Tool] get_download_status 失败: {e}")
        return ToolResult(success=False, error=str(e))


@tool(
    name="get_rss_feeds",
    description="获取所有 RSS 订阅源列表。",
    category="下载管理",
    parameters=[]
)
async def get_rss_feeds() -> ToolResult:
    try:
        from database import db
        from models import Feed
        from sqlmodel import select
        
        async with db.session_scope():
            stmt = select(Feed)
            feeds = await db.all(Feed, stmt)
        
        result = []
        for feed in feeds:
            result.append({
                "id": feed.id,
                "name": feed.name,
                "url": feed.url,
                "enabled": feed.enabled,
                "rule_id": feed.rule_id,
                "last_refresh": str(feed.last_refresh) if hasattr(feed, "last_refresh") else None
            })
        
        return ToolResult(
            success=True,
            data=result,
            message=f"共有 {len(result)} 个订阅源"
        )
    except Exception as e:
        logger.error(f"[Tool] get_rss_feeds 失败: {e}")
        return ToolResult(success=False, error=str(e))


@tool(
    name="get_rss_rules",
    description="获取所有 RSS 下载规则列表。",
    category="下载管理",
    parameters=[]
)
async def get_rss_rules() -> ToolResult:
    try:
        from database import db
        from models import Rule
        from sqlmodel import select
        
        async with db.session_scope():
            stmt = select(Rule)
            rules = await db.all(Rule, stmt)
        
        result = []
        for rule in rules:
            result.append({
                "id": rule.id,
                "name": rule.name,
                "enabled": rule.enabled,
                "priority": rule.priority,
                "include_keywords": rule.include_keywords,
                "exclude_keywords": rule.exclude_keywords
            })
        
        return ToolResult(
            success=True,
            data=result,
            message=f"共有 {len(result)} 个下载规则"
        )
    except Exception as e:
        logger.error(f"[Tool] get_rss_rules 失败: {e}")
        return ToolResult(success=False, error=str(e))


@tool(
    name="start_download",
    description="手动添加下载任务到下载客户端。",
    category="下载管理",
    parameters=[
        {"name": "url", "type": "string", "description": "下载链接（种子链接或磁力链接）", "required": True},
        {"name": "save_path", "type": "string", "description": "保存路径（可选）", "required": False}
    ]
)
async def start_download(url: str, save_path: str = "") -> ToolResult:
    try:
        from clients.manager import ClientManager
        
        client = ClientManager.get_client()
        
        if not client:
            return ToolResult(success=False, error="未配置下载客户端")
        
        result = await client.add_download(url, save_path)
        
        if result.get("success"):
            return ToolResult(
                success=True,
                data={"download_id": result.get("id")},
                message="下载任务已添加"
            )
        else:
            return ToolResult(
                success=False,
                error=result.get("error", "添加下载失败")
            )
    except Exception as e:
        logger.error(f"[Tool] start_download 失败: {e}")
        return ToolResult(success=False, error=str(e))
