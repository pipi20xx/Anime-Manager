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
        from sqlmodel import select
        
        async with db.session_scope():
            existing_stmt = select(Subscription).where(
                Subscription.tmdb_id == tmdb_id,
                Subscription.media_type == media_type
            )
            existing = await db.first(Subscription, existing_stmt)
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


@tool(
    name="subscribe_by_bangumi_id",
    description="通过 Bangumi ID 一键订阅番剧。系统会自动匹配 TMDB 并创建订阅。这是最简单的订阅方式。",
    category="订阅管理",
    parameters=[
        {"name": "bangumi_id", "type": "integer", "description": "Bangumi 条目 ID", "required": True}
    ]
)
async def subscribe_by_bangumi_id(bangumi_id: int) -> ToolResult:
    try:
        from recognition.data_provider.bangumi.client import BangumiProvider
        from recognition_engine.bgm_matcher.utils import extract_season_from_name
        from rss_core.subscription_manager import SubscriptionManager
        from clients.manager import ClientManager
        from models import Subscription, SubscriptionTemplate
        from notification import NotificationManager
        from database import db
        from config_manager import ConfigManager
        from sqlmodel import select
        
        bgm_item = await BangumiProvider.get_subject_details(bangumi_id)
        if not bgm_item:
            return ToolResult(success=False, error=f"Bangumi 条目 {bangumi_id} 未找到")
        
        bgm_title = bgm_item.get('title') or bgm_item.get('original_title')
        
        async with db.session_scope():
            existing_stmt = select(Subscription).where(Subscription.bangumi_id == str(bangumi_id))
            existing = await db.first(Subscription, existing_stmt)
            if existing:
                return ToolResult(
                    success=False,
                    error=f"已存在相同的订阅: {existing.title}",
                    data={"existing_id": existing.id}
                )
        
        tmdb_item = None
        config = ConfigManager.get_config()
        tmdb_key = config.get("tmdb_api_key")
        
        if tmdb_key:
            tmdb_item = await BangumiProvider.map_to_tmdb(bgm_item, tmdb_key, logs=None)
        
        season = extract_season_from_name(bgm_title)
        total_episodes = bgm_item.get('total_episodes') or 0
        
        final_poster = bgm_item.get('poster_path')
        tmdb_id = None
        media_type = "tv"
        year = None
        
        if tmdb_item:
            tmdb_id = str(tmdb_item['id'])
            media_type = tmdb_item.get('type', 'tv')
            year = tmdb_item.get('year')
            if tmdb_item.get('poster_path'):
                final_poster = tmdb_item['poster_path']
        
        target_tmpl = None
        async with db.session_scope():
            stmt = select(SubscriptionTemplate).where(SubscriptionTemplate.is_default == True)
            target_tmpl = await db.first(SubscriptionTemplate, stmt)
        
        default_client = ClientManager.get_client()
        default_client_id = default_client.config.get('id') if default_client else None
        
        sub = Subscription(
            tmdb_id=tmdb_id,
            media_type=media_type,
            title=bgm_title,
            year=year,
            poster_path=final_poster,
            season=season,
            start_episode=1,
            end_episode=total_episodes,
            bangumi_id=str(bangumi_id),
            enabled=True,
            target_client_id=target_tmpl.target_client_id if target_tmpl else default_client_id,
            save_path=target_tmpl.save_path if target_tmpl else None,
            category=target_tmpl.category if target_tmpl else "Anime",
            auto_fill=target_tmpl.auto_fill if target_tmpl else True,
            filter_res=target_tmpl.filter_res if target_tmpl else None,
            filter_team=target_tmpl.filter_team if target_tmpl else None,
            filter_source=target_tmpl.filter_source if target_tmpl else None,
            filter_codec=target_tmpl.filter_codec if target_tmpl else None,
            filter_audio=target_tmpl.filter_audio if target_tmpl else None,
            filter_sub=target_tmpl.filter_sub if target_tmpl else None,
            filter_effect=target_tmpl.filter_effect if target_tmpl else None,
            filter_platform=target_tmpl.filter_platform if target_tmpl else None,
            include_keywords=target_tmpl.include_keywords if target_tmpl else None,
            exclude_keywords=target_tmpl.exclude_keywords if target_tmpl else None
        )
        
        result = await SubscriptionManager.save_subscription(sub)
        
        try:
            await NotificationManager.push_sub_add_notification(result)
        except:
            pass
        
        logger.info(f"[Tool] 一键订阅成功: {result.title}")
        
        return ToolResult(
            success=True,
            data={
                "id": result.id,
                "title": result.title,
                "tmdb_id": result.tmdb_id,
                "bangumi_id": result.bangumi_id,
                "season": result.season,
                "total_episodes": result.end_episode
            },
            message=f"✅ 成功订阅: {result.title} (第{result.season}季，共{result.end_episode}集)"
        )
    except Exception as e:
        logger.error(f"[Tool] subscribe_by_bangumi_id 失败: {e}", exc_info=True)
        return ToolResult(success=False, error=str(e))
