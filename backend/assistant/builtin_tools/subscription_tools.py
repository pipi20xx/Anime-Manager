from ..tools import tool, ToolResult
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)


@tool(
    name="list_subscriptions",
    description="获取当前所有的订阅任务列表。",
    category="订阅管理",
    parameters=[
        {"name": "enabled_only", "type": "boolean", "description": "是否只返回已启用的订阅", "required": False}
    ]
)
async def list_subscriptions(enabled_only: bool = False) -> ToolResult:
    try:
        from rss_core.subscription_manager import SubscriptionManager
        
        subs = await SubscriptionManager.get_subscriptions(enabled_only)
        
        simplified = []
        for sub in subs:
            simplified.append({
                "id": sub.id,
                "title": sub.title,
                "tmdb_id": sub.tmdb_id,
                "media_type": sub.media_type,
                "season": sub.season,
                "start_episode": sub.start_episode,
                "end_episode": sub.end_episode,
                "enabled": sub.enabled,
                "save_path": sub.save_path,
                "created_at": str(sub.created_at) if hasattr(sub, "created_at") else None
            })
        
        return ToolResult(
            success=True,
            data=simplified,
            message=f"当前共有 {len(simplified)} 个订阅"
        )
    except Exception as e:
        logger.error(f"[Tool] list_subscriptions 失败: {e}")
        return ToolResult(success=False, error=str(e))


@tool(
    name="add_subscription",
    description="添加一个新的订阅任务。",
    category="订阅管理",
    parameters=[
        {"name": "title", "type": "string", "description": "作品标题", "required": True},
        {"name": "tmdb_id", "type": "string", "description": "TMDB ID", "required": True},
        {"name": "media_type", "type": "string", "description": "媒体类型：tv 或 movie", "required": True, "enum": ["tv", "movie"]},
        {"name": "season", "type": "integer", "description": "季度号（剧集用）", "required": False},
        {"name": "start_episode", "type": "integer", "description": "起始集数", "required": False},
        {"name": "end_episode", "type": "integer", "description": "结束集数", "required": False},
        {"name": "save_path", "type": "string", "description": "保存路径", "required": False},
        {"name": "enabled", "type": "boolean", "description": "是否启用", "required": False}
    ]
)
async def add_subscription(
    title: str,
    tmdb_id: str,
    media_type: str,
    season: int = 1,
    start_episode: int = 0,
    end_episode: int = 0,
    save_path: str = "",
    enabled: bool = True
) -> ToolResult:
    try:
        from models import Subscription
        from rss_core.subscription_manager import SubscriptionManager
        from database import db
        
        async with db.session_scope():
            existing = await SubscriptionManager.get_by_tmdb_id(tmdb_id, media_type)
            if existing:
                return ToolResult(
                    success=False,
                    error=f"已存在相同的订阅: {existing.title}",
                    data={"existing_id": existing.id}
                )
        
        sub = Subscription(
            title=title,
            tmdb_id=tmdb_id,
            media_type=media_type,
            season=season if media_type == "tv" else 0,
            start_episode=start_episode,
            end_episode=end_episode,
            save_path=save_path,
            enabled=enabled
        )
        
        result = await SubscriptionManager.save_subscription(sub)
        
        return ToolResult(
            success=True,
            data={"id": result.id, "title": result.title},
            message=f"成功添加订阅: {title}"
        )
    except Exception as e:
        logger.error(f"[Tool] add_subscription 失败: {e}")
        return ToolResult(success=False, error=str(e))


@tool(
    name="delete_subscription",
    description="删除指定的订阅任务。",
    category="订阅管理",
    parameters=[
        {"name": "subscription_id", "type": "integer", "description": "订阅 ID", "required": True}
    ]
)
async def delete_subscription(subscription_id: int) -> ToolResult:
    try:
        from rss_core.subscription_manager import SubscriptionManager
        from database import db
        from models import Subscription
        
        async with db.session_scope():
            sub = await db.get(Subscription, subscription_id)
            if not sub:
                return ToolResult(success=False, error=f"订阅 ID {subscription_id} 不存在")
            
            title = sub.title
            await SubscriptionManager.delete_subscription(subscription_id)
        
        return ToolResult(success=True, message=f"已删除订阅: {title}")
    except Exception as e:
        logger.error(f"[Tool] delete_subscription 失败: {e}")
        return ToolResult(success=False, error=str(e))


@tool(
    name="toggle_subscription",
    description="启用或禁用订阅任务。",
    category="订阅管理",
    parameters=[
        {"name": "subscription_id", "type": "integer", "description": "订阅 ID", "required": True},
        {"name": "enabled", "type": "boolean", "description": "是否启用", "required": True}
    ]
)
async def toggle_subscription(subscription_id: int, enabled: bool) -> ToolResult:
    try:
        from rss_core.subscription_manager import SubscriptionManager
        from database import db
        from models import Subscription
        
        async with db.session_scope():
            sub = await db.get(Subscription, subscription_id)
            if not sub:
                return ToolResult(success=False, error=f"订阅 ID {subscription_id} 不存在")
            
            sub.enabled = enabled
            await db.save(sub)
        
        status = "启用" if enabled else "禁用"
        return ToolResult(success=True, message=f"已{status}订阅: {sub.title}")
    except Exception as e:
        logger.error(f"[Tool] toggle_subscription 失败: {e}")
        return ToolResult(success=False, error=str(e))


@tool(
    name="get_subscription_episodes",
    description="获取订阅任务已下载的集数列表。",
    category="订阅管理",
    parameters=[
        {"name": "subscription_id", "type": "integer", "description": "订阅 ID", "required": True}
    ]
)
async def get_subscription_episodes(subscription_id: int) -> ToolResult:
    try:
        from rss_core.subscription_manager import SubscriptionManager
        from database import db
        from models import Subscription
        
        async with db.session_scope():
            sub = await db.get(Subscription, subscription_id)
            if not sub:
                return ToolResult(success=False, error=f"订阅 ID {subscription_id} 不存在")
            
            episodes = await SubscriptionManager.get_downloaded_episodes(
                sub.tmdb_id, sub.media_type
            )
        
        episode_list = []
        for ep in episodes:
            episode_list.append({
                "season": ep.season,
                "episode": ep.episode,
                "title": ep.title,
                "downloaded_at": str(ep.downloaded_at) if hasattr(ep, "downloaded_at") else None
            })
        
        return ToolResult(
            success=True,
            data=episode_list,
            message=f"已下载 {len(episode_list)} 集"
        )
    except Exception as e:
        logger.error(f"[Tool] get_subscription_episodes 失败: {e}")
        return ToolResult(success=False, error=str(e))


@tool(
    name="check_subscription_exists",
    description="检查指定作品是否已订阅。",
    category="订阅管理",
    parameters=[
        {"name": "tmdb_id", "type": "string", "description": "TMDB ID", "required": True},
        {"name": "media_type", "type": "string", "description": "媒体类型：tv 或 movie", "required": True, "enum": ["tv", "movie"]}
    ]
)
async def check_subscription_exists(tmdb_id: str, media_type: str) -> ToolResult:
    try:
        from rss_core.subscription_manager import SubscriptionManager
        
        existing = await SubscriptionManager.get_by_tmdb_id(tmdb_id, media_type)
        
        if existing:
            return ToolResult(
                success=True,
                data={
                    "exists": True,
                    "subscription": {
                        "id": existing.id,
                        "title": existing.title,
                        "enabled": existing.enabled
                    }
                },
                message=f"已订阅: {existing.title}"
            )
        
        return ToolResult(
            success=True,
            data={"exists": False},
            message="未订阅此作品"
        )
    except Exception as e:
        logger.error(f"[Tool] check_subscription_exists 失败: {e}")
        return ToolResult(success=False, error=str(e))
