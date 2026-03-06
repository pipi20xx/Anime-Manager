from fastapi import APIRouter, HTTPException
import asyncio
from typing import List, Dict, Any
from models import Feed, Rule, DownloadHistory, FeedItem, Subscription, SubscribedEpisode
from rss_core.manager import RssManager
from rss_core.scheduler import refresh_all_feeds
from clients.jackett import JackettClient
from logger import log_audit
from database import db
from sqlmodel import select, delete, text, or_

router = APIRouter(tags=["RSS 下载管理"])

# --- Feeds ---
@router.get("/feeds", response_model=List[Feed], summary="获取订阅源列表")
async def get_feeds():
    """
    返回系统当前配置的所有 RSS 订阅源信息。
    """
    return await RssManager.get_feeds()

@router.post("/feeds", summary="保存/更新订阅源")
async def save_feed(feed: Feed):
    """
    新增或修改 RSS 订阅源地址及其配置。
    """
    return await RssManager.save_feed(feed)

@router.delete("/feeds/{feed_id}", summary="删除订阅源")
async def delete_feed(feed_id: int):
    """
    通过 ID 删除指定的 RSS 订阅源。
    """
    await RssManager.delete_feed(feed_id)
    return {"success": True}

@router.get("/feeds/{feed_id}/items", summary="获取源条目列表")
async def get_feed_items(feed_id: int, limit: int = 50, offset: int = 0):
    """
    获取指定订阅源下已抓取到的条目，并附带识别状态、订阅状态等标记。
    """
    # Get raw items
    items = await RssManager.get_feed_items(feed_id, limit=limit, offset=offset)
    if not items:
        return []

    # Get all distinct TMDB IDs from these items to batch query subscriptions
    tmdb_ids = {item.tmdb_id for item in items if item.tmdb_id}
    # Get all GUIDs to check download history
    guids = [item.guid for item in items]
    
    # Pre-fetch subscriptions and collected episodes
    sub_map = {} # tmdb_id -> Subscription
    collected_map = set() # (tmdb_id, season, episode)
    downloaded_guids = set()

    async with db.session_scope():
        # 0. Check Download History (for is_downloaded flag)
        if guids:
            hist_stmt = select(DownloadHistory).where(DownloadHistory.guid.in_(guids))
            hist_items = await db.all(DownloadHistory, hist_stmt)
            downloaded_guids = {h.guid for h in hist_items}

        if tmdb_ids:
            # 1. Check Subscriptions
            sub_stmt = select(Subscription).where(Subscription.tmdb_id.in_(tmdb_ids))
            subs = await db.all(Subscription, sub_stmt)
            sub_map = {s.tmdb_id: s for s in subs}
            
            # 2. Check Collected Episodes
            # We query all episodes for these shows to keep logic simple (assuming not massive for single feed view)
            ep_stmt = select(SubscribedEpisode).where(SubscribedEpisode.tmdb_id.in_(tmdb_ids))
            eps = await db.all(SubscribedEpisode, ep_stmt)
            for ep in eps:
                collected_map.add((ep.tmdb_id, ep.season, ep.episode))

    # Construct response with flags
    result = []
    for item in items:
        # Use mode='json' to force Pydantic to serialize types (e.g. int -> str) correctly
        data = item.model_dump(mode='json')
        
        # Flag 0: Is this GUID pushed?
        data['is_downloaded'] = item.guid in downloaded_guids

        # Flag 1: Is this show subscribed?
        data['in_subscription'] = item.tmdb_id in sub_map
        
        # Flag 2: Is this specific episode collected?
        is_collected = False
        if item.tmdb_id:
            # Handle multi-episode range string e.g., "1-2" later if needed, currently simplistic
            # For now, try to parse single episode or just check if primary one is there
            try:
                # If episode is a range string "01-02", check if ANY in range is collected? Or ALL?
                # Let's simplify: check the start episode
                ep_val = int(str(item.episode).split('-')[0]) if item.episode else 0
                season_val = item.season if item.season is not None else 1
                
                if item.media_type == 'movie':
                    is_collected = (item.tmdb_id, 0, 0) in collected_map
                else:
                    is_collected = (item.tmdb_id, season_val, ep_val) in collected_map
            except:
                pass
        
        data['episode_collected'] = is_collected
        result.append(data)
        
    return result

@router.post("/feeds/{feed_id}/reset", summary="重置下载历史")
async def reset_feed_history(feed_id: int):
    """
    清空该订阅源在 download_history 表中的所有记录，允许系统重新推送已下载过的资源。
    """
    await RssManager.reset_feed_history(feed_id)
    return {"success": True, "message": "已重置下载历史"}

@router.post("/feeds/{feed_id}/retry", summary="重试源识别失败项")
async def retry_feed_recognition(feed_id: int):
    """
    手动触发：对该源下所有识别失败的条目重新进行识别。
    """
    from rss_core.subscription_matcher import SubscriptionMatcher
    
    async with db.session_scope():
        # 获取该源下识别失败的条目 (done=True 但 id 为空)
        stmt = select(FeedItem).where(
            FeedItem.feed_id == feed_id,
            FeedItem.recognition_done == True,
            or_(FeedItem.tmdb_id == None, FeedItem.tmdb_id == "None", FeedItem.tmdb_id == "")
        )
        items = await db.all(FeedItem, stmt)
        
        if not items:
            return {"success": True, "message": "没有需要重试的失败条目", "count": 0}
            
        # 构造 entries 格式传递给 matcher
        entries = [{"guid": item.guid, "title": item.title} for item in items]
        
    # 异步执行重试识别
    asyncio.create_task(SubscriptionMatcher.recognize_items(entries, retry_failed=True))
    
    log_audit("RSS", "重试识别", f"手动触发了源 (ID: {feed_id}) 的识别失败项重试，共 {len(items)} 条")
    return {"success": True, "message": f"已启动 {len(items)} 个条目的重试任务，请稍后刷新列表", "count": len(items)}

@router.post("/feeds/sync-jackett", summary="同步 Jackett 源")
async def sync_jackett_feeds():
    """
    从 Jackett 获取所有已配置的索引站，并自动添加为 RSS 订阅源。
    """
    from config_manager import ConfigManager
    
    # 获取 Jackett 配置
    config = ConfigManager.get_config()
    jackett_url = config.get("jackett_url", "").rstrip("/")
    api_key = config.get("jackett_api_key", "")
    
    if not jackett_url or not api_key:
        raise HTTPException(status_code=400, detail="Jackett 未配置，请先在设置中配置 Jackett")
    
    # 获取 Jackett 索引站列表
    indexers = await JackettClient.get_indexers()
    if not indexers:
        return {"success": True, "message": "Jackett 中没有已配置的索引站", "added": 0, "skipped": 0}
    
    # 获取现有的 RSS 源
    existing_feeds = await RssManager.get_feeds()
    existing_urls = {feed.url for feed in existing_feeds}
    
    added_count = 0
    skipped_count = 0
    
    # 为每个索引站生成 RSS URL 并添加
    for indexer in indexers:
        indexer_id = indexer.get("id")
        indexer_name = indexer.get("name")
        
        if not indexer_id:
            continue
        
        # 生成 Jackett RSS URL
        rss_url = f"{jackett_url}/api/v2.0/indexers/{indexer_id}/results/torznab/api?apikey={api_key}&t=search&cat=&q="
        
        # 检查是否已存在
        if rss_url in existing_urls:
            skipped_count += 1
            continue
        
        # 创建新的 RSS 源
        new_feed = Feed(
            url=rss_url,
            title=f"Jackett - {indexer_name}",
            enabled=True,
            for_subscription=True,
            for_rules=True,
            anime_priority=True
        )
        
        await RssManager.save_feed(new_feed)
        added_count += 1
    
    log_audit("RSS", "同步 Jackett 源", f"从 Jackett 同步了 {added_count} 个新源，跳过 {skipped_count} 个已存在的源")
    
    return {
        "success": True,
        "message": f"成功添加 {added_count} 个新源，跳过 {skipped_count} 个已存在的源",
        "added": added_count,
        "skipped": skipped_count
    }

# --- Rules ---
@router.get("/rules", response_model=List[Rule], summary="获取下载规则列表")
async def get_rules():
    """
    返回系统当前配置的所有 RSS 关键词过滤/正则下载规则。
    """
    return await RssManager.get_rules()

@router.post("/rules", summary="保存/更新下载规则")
async def save_rule(rule: Rule):
    """
    新增或修改 RSS 下载规则。
    """
    return await RssManager.save_rule(rule)

@router.delete("/rules/{rule_id}", summary="删除下载规则")
async def delete_rule(rule_id: int):
    """
    通过 ID 删除指定的 RSS 下载规则。
    """
    await RssManager.delete_rule(rule_id)
    return {"success": True}

# --- Actions & History ---
@router.post("/rss/run", summary="手动执行 RSS 刷新")
async def run_rss_now():
    """
    立即强制执行一次全量 RSS 抓取与匹配下载。
    """
    log_audit("RSS", "手动刷新", "用户触发了手动 RSS 刷新")
    # 不再 await 整个刷新任务，改为创建后台 Task 立即返回
    asyncio.create_task(refresh_all_feeds())
    return {"message": "RSS task started in background."}

@router.post("/rss/recognition/retry", summary="全局重试识别失败项")
async def retry_all_recognition():
    """
    手动触发：对系统中所有 RSS 源下识别失败的条目重新进行识别。
    """
    from rss_core.subscription_matcher import SubscriptionMatcher
    
    async with db.session_scope():
        # 获取所有识别失败的条目 (done=True 但 id 为空)
        stmt = select(FeedItem).where(
            FeedItem.recognition_done == True,
            or_(FeedItem.tmdb_id == None, FeedItem.tmdb_id == "None", FeedItem.tmdb_id == "")
        )
        items = await db.all(FeedItem, stmt)
        
        if not items:
            return {"success": True, "message": "全局未发现需要重试的失败条目", "count": 0}
            
        entries = [{"guid": item.guid, "title": item.title} for item in items]
        
    asyncio.create_task(SubscriptionMatcher.recognize_items(entries, retry_failed=True))
    
    log_audit("RSS", "全局重试识别", f"手动触发了全局识别失败项重试，共 {len(items)} 条")
    return {"success": True, "message": f"已启动全局 {len(items)} 个条目的重试任务", "count": len(items)}

@router.post("/rss/recognition/clear", summary="清空识别缓存")
async def clear_recognition_cache():
    """
    彻底清空 feed_items 表，重置所有条目的识别状态，下次刷新将重新全量识别。
    """
    async with db.session_scope() as session:
        # PostgreSQL 使用 TRUNCATE 并重置自增 ID，显式指定 public schema 更加稳健
        await session.execute(text('TRUNCATE TABLE "public"."feed_items" RESTART IDENTITY CASCADE'))
        await session.commit()
    log_audit("RSS", "缓存清理", "彻底清空了所有 Feed 条目及识别记录")
    return {"success": True, "message": "所有历史条目已清空，下次刷新将重新抓取并识别"}

@router.get("/rss/history", response_model=List[DownloadHistory], summary="获取下载历史")
async def get_history(limit: int = 50):
    """
    查询最近通过 RSS 规则推送成功的下载记录。
    """
    return await RssManager.get_history(limit)

@router.post("/rss/history", summary="手动标记下载历史")
async def add_history_manual(history: DownloadHistory):
    """
    手动往下载历史中插入一条记录，防止系统重复推送。
    """
    return await RssManager.add_history(history)

@router.delete("/rss/history/{guid:path}", summary="删除下载历史记录")
async def remove_history_manual(guid: str):
    """
    撤回/删除指定的下载历史记录。
    """
    # GUID likely contains slashes, handled by :path and unquoting
    # FastAPI/Starlette typically decodes path parameters.
    # Manual unquote might cause double-decoding if the original GUID contained encoded characters (like %3A).
    log_audit("Debug", "GUID Check", f"Received: {guid[:50]}...")
    
    # Try removing exactly as received
    await RssManager.remove_history(guid)
    
    return {"success": True, "message": "已清除该条目的推送记录"}

@router.get("/rules/{rule_id}/history", response_model=List[Dict[str, Any]], summary="获取特定规则的下载历史")
async def get_rule_history(rule_id: int):
    """
    查询指定规则所产生的历史下载流水。
    """
    async with db.session_scope():
        stmt = select(DownloadHistory).where(DownloadHistory.rule_id == rule_id).order_by(DownloadHistory.created_at.desc())
        history_list = await db.all(DownloadHistory, stmt)
        
        # Filter out None and ensure they are real objects
        history_list = [h for h in history_list if h is not None]
        
        guids = [h.guid for h in history_list]
        item_map = {}
        if guids:
            item_stmt = select(FeedItem).where(FeedItem.guid.in_(guids))
            items = await db.all(FeedItem, item_stmt)
            for item in items:
                item_map[item.guid] = item.link

        result = []
        for h in history_list:
            d = h.model_dump()
            d['link'] = item_map.get(h.guid)
            result.append(d)
            
        return result

@router.post("/rss/preview", summary="测试规则匹配")
async def preview_rule(rule_config: dict):
    """
    根据当前的规则配置，在现有的识别缓存中模拟匹配，返回预测会下载的条目列表。
    """
    from rss_core.matcher import Matcher
    
    must_contain = rule_config.get('must_contain', '')
    must_not_contain = rule_config.get('must_not_contain', '')
    use_regex = rule_config.get('use_regex', False)
    target_feeds = rule_config.get('target_feeds', '')
    
    async with db.session_scope():
        # 1. Map Feed IDs to Titles
        feeds = await db.all(Feed)
        feed_map = {f.id: (f.title or f.url) for f in feeds}

        # 2. Build Query
        statement = select(FeedItem)
        if target_feeds and target_feeds.strip():
            try:
                ids = [int(i) for i in target_feeds.split(',') if i.strip()]
                if ids:
                    statement = statement.where(FeedItem.feed_id.in_(ids))
            except ValueError: pass

        statement = statement.order_by(FeedItem.created_at.desc()).limit(200)
        items = await db.all(FeedItem, statement)
        
        matches = []
        for item in items:
            if Matcher.check_match(item.title, must_contain, must_not_contain, use_regex):
                # Check history for preview
                h_stmt = select(DownloadHistory).where(DownloadHistory.guid == item.guid)
                is_downloaded = await db.first(DownloadHistory, h_stmt) is not None
                matches.append({
                    "title": item.title,
                    "link": item.link,
                    "description": item.description,
                    "guid": item.guid,
                    "feed_id": item.feed_id,
                    "feed_name": feed_map.get(item.feed_id, f"Feed #{item.feed_id}"),
                    "is_downloaded": is_downloaded
                })
        
        return matches
