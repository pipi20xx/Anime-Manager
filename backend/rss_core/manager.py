import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from sqlmodel import select, delete, or_, and_
from models import Feed, Rule, DownloadHistory, FeedItem, Blacklist
from database import db

from logger import log_audit

logger = logging.getLogger("RssManager")

def normalize_guid(guid: str) -> str:
    """如果 GUID 过长（超过 500 字符），则使用 MD5 摘要以避免数据库索引溢出"""
    if not guid:
        return ""
    if len(guid) > 500:
        import hashlib
        return hashlib.md5(guid.encode()).hexdigest()
    return guid

class RssManager:
    """
    RSS 订阅与规则管理器，使用 db (DBService) 统一管理。
    """

    @staticmethod
    async def get_feeds() -> List[Feed]:
        async with db.session_scope():
            return await db.all(Feed)

    @staticmethod
    async def save_feed(feed_data: Feed) -> Feed:
        async with db.session_scope():
            if feed_data.id:
                db_feed = await db.get(Feed, feed_data.id)
                if db_feed:
                    logger.info(f"更新 RSS 订阅源: {feed_data.url}")
                    for key, value in feed_data.model_dump(exclude_unset=True).items():
                        setattr(db_feed, key, value)
                    saved = await db.save(db_feed)
                    log_audit("RSS", "更新源", f"成功更新 RSS 源: {saved.title or saved.url}")
                    return saved
            
            logger.info(f"添加新 RSS 订阅源: {feed_data.url}")
            saved = await db.save(feed_data)
            log_audit("RSS", "添加源", f"成功添加 RSS 源: {saved.title or saved.url}")
            return saved

    @staticmethod
    async def delete_feed(feed_id: int):
        async with db.session_scope() as session:
            await session.execute(delete(FeedItem).where(FeedItem.feed_id == feed_id))
            feed = await db.get(Feed, feed_id)
            if feed:
                title = feed.title or feed.url
                await db.delete(feed)
                logger.info(f"删除 RSS 订阅源: {title} (ID: {feed_id})")
                log_audit("RSS", "删除源", f"已删除 RSS 源: {title}")
            await session.commit()

    @staticmethod
    async def get_rules() -> List[Rule]:
        async with db.session_scope():
            return await db.all(Rule)

    @staticmethod
    async def save_rule(rule_data: Rule) -> Rule:
        async with db.session_scope():
            if rule_data.id:
                db_rule = await db.get(Rule, rule_data.id)
                if db_rule:
                    logger.info(f"更新匹配规则: {rule_data.name}")
                    for key, value in rule_data.model_dump(exclude_unset=True).items():
                        setattr(db_rule, key, value)
                    saved = await db.save(db_rule)
                    log_audit("规则", "更新规则", f"已更新匹配规则: {saved.name}")
                    return saved
            
            logger.info(f"添加新匹配规则: {rule_data.name}")
            saved = await db.save(rule_data)
            log_audit("规则", "添加规则", f"已添加匹配规则: {saved.name}")
            return saved

    @staticmethod
    async def delete_rule(rule_id: int):
        async with db.session_scope():
            rule = await db.get(Rule, rule_id)
            if rule:
                name = rule.name
                await db.delete(rule)
                logger.info(f"删除匹配规则: {name} (ID: {rule_id})")
                log_audit("规则", "删除规则", f"已删除匹配规则: {name}")

    @staticmethod
    async def get_history(limit: int = 50) -> List[DownloadHistory]:
        async with db.session_scope():
            stmt = select(DownloadHistory).order_by(DownloadHistory.created_at.desc()).limit(limit)
            return await db.all(DownloadHistory, stmt)

    @staticmethod
    async def is_downloaded(guid: str, title: Optional[str] = None, rule_id: Optional[int] = None) -> bool:
        guid = normalize_guid(guid)
        async with db.session_scope():
            # 1. 检查正常下载历史
            # 逻辑优化：
            # - 如果存在与当前 rule_id 完全匹配的记录 -> True
            # - 如果存在 rule_id 为空的记录 (手动标记/全局记录) -> True (代表手动屏蔽了该资源，所有规则都应跳过)
            stmt = select(DownloadHistory).where(DownloadHistory.guid == guid)
            
            if rule_id is not None:
                # 只有当记录的 rule_id 匹配，或者记录的 rule_id 为空(手动)时，才算已下载
                stmt = stmt.where(or_(
                    DownloadHistory.rule_id == rule_id,
                    DownloadHistory.rule_id == None
                ))
            
            if await db.first(DownloadHistory, stmt) is not None:
                return True
            
            # 2. 检查黑名单 (确定失效的种子)
            # 如果 GUID 匹配，或者标题完全匹配（且不为空），则拦截
            filters = [Blacklist.guid == guid]
            if title:
                filters.append(Blacklist.title == title)
            
            stmt_bl = select(Blacklist).where(or_(*filters))
            if await db.first(Blacklist, stmt_bl) is not None:
                logger.info(f"拦截命中黑名单资源: {title or guid}")
                return True
                
            return False

    @staticmethod
    async def is_blacklisted(guid: str, title: Optional[str] = None) -> bool:
        """独立检查是否在黑名单中 (不检查 DownloadHistory)"""
        guid = normalize_guid(guid)
        async with db.session_scope():
            filters = [Blacklist.guid == guid]
            if title:
                filters.append(Blacklist.title == title)
            
            stmt_bl = select(Blacklist).where(or_(*filters))
            if await db.first(Blacklist, stmt_bl) is not None:
                logger.info(f"拦截命中黑名单资源: {title or guid}")
                return True
            return False

    @staticmethod
    async def add_history(history: DownloadHistory):
        history.guid = normalize_guid(history.guid)
        async with db.session_scope():
            return await db.save(history)

    @staticmethod
    async def remove_history(guid: str):
        guid = normalize_guid(guid)
        async with db.session_scope():
            stmt = select(DownloadHistory).where(DownloadHistory.guid == guid)
            item = await db.first(DownloadHistory, stmt)
            if item: 
                await db.delete(item)
                logger.info(f"Deleted history for GUID: {guid[:30]}...")
            else:
                logger.warning(f"History not found for deletion: {guid[:30]}...")

    @staticmethod
    async def get_feed_items(feed_id: int, limit: int = 50, offset: int = 0) -> List[FeedItem]:
        async with db.session_scope():
            stmt = select(FeedItem).where(FeedItem.feed_id == feed_id).order_by(FeedItem.created_at.desc()).offset(offset).limit(limit)
            return await db.all(FeedItem, stmt)

    @staticmethod
    async def reset_feed_history(feed_id: int):
        async with db.session_scope() as session:
            # User expectation: "Reset History" means clearing the "Pushed/Downloaded" status
            # so that items can be pushed again. It should NOT clear the RSS feed cache (FeedItems).
            await session.execute(delete(DownloadHistory).where(DownloadHistory.feed_id == feed_id))
            await session.commit()

    @staticmethod
    async def save_feed_items(feed_id: int, entries: List[Dict]):
        """镜像同步 Feed 条目：保存新条目，并自动删除该源中已不在 RSS 列表里的旧条目"""
        async with db.session_scope() as session:
            if not entries:
                # 如果当前源为空，则清空该源所有缓存条目
                await session.execute(delete(FeedItem).where(FeedItem.feed_id == feed_id))
                await session.commit()
                return
            
            # 1. 提取当前所有新鲜条目的 GUID (并进行规范化)
            current_guids = [normalize_guid(entry['guid']) for entry in entries]
            
            # 2. 删除数据库中属于该源但不在当前新鲜列表里的条目
            await session.execute(
                delete(FeedItem).where(
                    and_(
                        FeedItem.feed_id == feed_id,
                        FeedItem.guid.not_in(current_guids)
                    )
                )
            )
            
            # 3. 准备数据进行 Upsert (保存/更新)
            values = []
            for entry in entries:
                values.append({
                    "feed_id": feed_id,
                    "guid": normalize_guid(entry['guid']),
                    "title": entry['title'],
                    "link": entry['link'],
                    "description": entry.get('description'),
                    "pub_date": entry.get('pub_date'),
                    "created_at": datetime.now()
                })
                
            await db.upsert_all(FeedItem, values, index_elements=['guid'])
            await session.commit()

    @staticmethod
    async def update_item_recognition(item_id: int, recognition_data: Dict[str, Any]):
        """更新条目的识别信息"""
        async with db.session_scope():
            item = await db.get(FeedItem, item_id)
            if item:
                t_id = recognition_data.get("tmdb_id")
                # Fix: Ensure empty string or None is stored as None/empty, not "None" string
                item.tmdb_id = str(t_id) if t_id else None
                item.tmdb_title = recognition_data.get("title")
                item.media_type = "movie" if recognition_data.get("category") == "电影" else "tv"
                item.season = recognition_data.get("season")
                item.episode = str(recognition_data.get("episode")) if recognition_data.get("episode") is not None else None
                
                # 更新详细规格字段
                for field in ["resolution", "team", "source", "video_encode", "audio_encode", 
                             "video_effect", "subtitle", "platform"]:
                    if field in recognition_data:
                        setattr(item, field, recognition_data[field])
                
                item.recognition_done = True
                await db.save(item, audit=False)
