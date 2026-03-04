import logging
from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime
from sqlmodel import select, delete, and_, or_
from models import Subscription, SubscribedEpisode, DownloadHistory
from database import db

logger = logging.getLogger("SubscriptionManager")

class SubscriptionManager:
    @staticmethod
    async def get_subscriptions(enabled_only: bool = False) -> List[Subscription]:
        async with db.session_scope():
            stmt = select(Subscription)
            if enabled_only:
                stmt = stmt.where(Subscription.enabled == True)
            return await db.all(Subscription, stmt)

    @staticmethod
    async def save_subscription(sub_data: Subscription) -> Subscription:
        async with db.session_scope():
            if sub_data.id:
                db_sub = await db.get(Subscription, sub_data.id)
                if db_sub:
                    update_data = sub_data.model_dump(exclude={"id", "last_check", "created_at"}, exclude_unset=True)
                    for key, value in update_data.items():
                        setattr(db_sub, key, value)
                    saved = await db.save(db_sub)
                    await SubscriptionManager._sync_to_calendar(saved)
                    return saved
            
            sub_data.id = None
            sub_data.last_check = datetime.now()
            sub_data.created_at = datetime.now()
            saved = await db.save(sub_data)
            await SubscriptionManager._sync_to_calendar(saved)
            return saved

    @staticmethod
    async def delete_subscription(sub_id: int):
        async with db.session_scope():
            sub = await db.get(Subscription, sub_id)
            if sub:
                # 同步从日历移除
                from models import CalendarSubject
                stmt = delete(CalendarSubject).where(
                    CalendarSubject.tmdb_id == sub.tmdb_id,
                    CalendarSubject.season == sub.season
                )
                await db.execute(stmt)
                await db.delete(sub)

    @staticmethod
    async def _sync_to_calendar(sub: Subscription):
        """内部方法：将订阅同步到日历追踪"""
        try:
            from models import CalendarSubject
            from recognition.data_provider.tmdb.client import TMDBProvider
            
            async with db.session_scope():
                # 检查是否已在追踪
                stmt = select(CalendarSubject).where(
                    CalendarSubject.tmdb_id == sub.tmdb_id,
                    CalendarSubject.season == sub.season
                )
                exists = await db.first(CalendarSubject, stmt)
                if exists:
                    # 如果已存在，仅同步可能的标题更改
                    if exists.title != sub.title:
                        exists.title = sub.title
                        await db.save(exists)
                    return

                # 不存在则抓取并新建
                tmdb = TMDBProvider()
                eps = await tmdb.get_season_episodes(sub.tmdb_id, sub.season)
                
                new_cal = CalendarSubject(
                    tmdb_id=sub.tmdb_id,
                    media_type=sub.media_type,
                    title=sub.title,
                    season=sub.season,
                    poster_path=sub.poster_path,
                    episodes_cache=eps,
                    first_air_date=eps[0]["air_date"] if eps else None
                )
                await db.save(new_cal)
                logger.info(f"已自动同步订阅《{sub.title}》至追剧日历")
        except Exception as e:
            logger.error(f"同步订阅至日历失败: {e}")

    @staticmethod
    async def is_episode_downloaded(tmdb_id: str, media_type: str, season: int, episode: int) -> bool:
        async with db.session_scope():
            stmt = select(SubscribedEpisode).where(
                and_(
                    SubscribedEpisode.tmdb_id == str(tmdb_id),
                    SubscribedEpisode.media_type == media_type,
                    SubscribedEpisode.season == season,
                    SubscribedEpisode.episode == episode
                )
            )
            return await db.first(SubscribedEpisode, stmt) is not None

    @staticmethod
    async def get_episode_record(tmdb_id: str, media_type: str, season: int, episode: int) -> Optional[SubscribedEpisode]:
        """获取具体的集数下载记录 (包含分数等信息)"""
        async with db.session_scope():
            stmt = select(SubscribedEpisode).where(
                and_(
                    SubscribedEpisode.tmdb_id == str(tmdb_id),
                    SubscribedEpisode.media_type == media_type,
                    SubscribedEpisode.season == season,
                    SubscribedEpisode.episode == episode
                )
            )
            return await db.first(SubscribedEpisode, stmt)

    @staticmethod
    async def add_subscribed_episode(tmdb_id: str, media_type: str, season: int, episode: int, 
                                     title: Optional[str] = None, info_hash: Optional[str] = None,
                                     quality_score: int = 0, profile_id: Optional[int] = None):
        async with db.session_scope():
            # 查找现有记录
            stmt = select(SubscribedEpisode).where(
                and_(
                    SubscribedEpisode.tmdb_id == str(tmdb_id),
                    SubscribedEpisode.media_type == media_type,
                    SubscribedEpisode.season == season,
                    SubscribedEpisode.episode == episode
                )
            )
            existing_ep = await db.first(SubscribedEpisode, stmt)
            
            if existing_ep:
                # 更新模式 (洗版)
                existing_ep.title = title
                existing_ep.info_hash = info_hash
                existing_ep.download_at = datetime.now()
                existing_ep.quality_score = quality_score
                existing_ep.profile_id = profile_id
                await db.save(existing_ep, audit=False)
            else:
                # 插入模式
                ep = SubscribedEpisode(
                    tmdb_id=str(tmdb_id),
                    media_type=media_type,
                    season=season,
                    episode=episode,
                    title=title,
                    info_hash=info_hash, 
                    download_at=datetime.now(),
                    quality_score=quality_score,
                    profile_id=profile_id
                )
                await db.save(ep, audit=False)

    @staticmethod
    async def delete_subscribed_episode(tmdb_id: str, media_type: str, season: int, episode: int):
        async with db.session_scope():
            stmt = select(SubscribedEpisode).where(
                and_(
                    SubscribedEpisode.tmdb_id == str(tmdb_id),
                    SubscribedEpisode.media_type == media_type,
                    SubscribedEpisode.season == season,
                    SubscribedEpisode.episode == episode
                )
            )
            ep = await db.first(SubscribedEpisode, stmt)
            if ep:
                await db.delete(ep)

    @staticmethod
    async def get_downloaded_episodes(tmdb_id: str, media_type: str) -> List[SubscribedEpisode]:
        async with db.session_scope():
            stmt = select(SubscribedEpisode).where(
                and_(
                    SubscribedEpisode.tmdb_id == str(tmdb_id),
                    SubscribedEpisode.media_type == media_type
                )
            )
            return await db.all(SubscribedEpisode, stmt)

    @staticmethod
    async def clear_downloaded_episodes(tmdb_id: str, media_type: str, title: Optional[str] = None):
        """
        彻底清空特定作品的所有历史记录。
        仅清理 SubscribedEpisode (订阅逻辑)，不再触碰 DownloadHistory (全局/规则历史)。
        """
        async with db.session_scope() as session:
            # 1. 清理集数追踪
            await session.execute(delete(SubscribedEpisode).where(
                and_(
                    SubscribedEpisode.tmdb_id == str(tmdb_id),
                    SubscribedEpisode.media_type == media_type
                )
            ))
            
            # 2. [已解耦] 不再清理 DownloadHistory
            # if title:
            #    await session.execute(delete(DownloadHistory).where(
            #        DownloadHistory.title.like(f"%{title}%")
            #    ))
            await session.commit()

    @staticmethod
    async def check_and_complete_subscription(sub_id: int):
        """
        检查订阅是否已达到结束集数，如果是则自动将其设为禁用状态。
        """
        async with db.session_scope():
            sub = await db.get(Subscription, sub_id)
            if not sub or not sub.enabled or sub.media_type != "tv" or sub.end_episode <= 0:
                return False

            # 查询已下载的所有集数
            stmt = select(SubscribedEpisode).where(
                and_(
                    SubscribedEpisode.tmdb_id == str(sub.tmdb_id),
                    SubscribedEpisode.media_type == sub.media_type,
                    SubscribedEpisode.season == sub.season
                )
            )
            downloaded = await db.all(SubscribedEpisode, stmt)
            downloaded_eps = {ep.episode for ep in downloaded}

            # 判定标准：检查从 start_episode 到 end_episode 的每一集是否都已经在已下载列表中
            # 只有全量覆盖了订阅范围，才自动结束
            required_eps = set(range(sub.start_episode, sub.end_episode + 1))
            
            if required_eps.issubset(downloaded_eps):
                sub.enabled = False
                await db.save(sub)
                logger.info(f"✅ 订阅《{sub.title}》已完成全部集数 (E{sub.start_episode}-E{sub.end_episode})，自动设为已完成状态。")
                log_audit("订阅", "自动完成", f"订阅 '{sub.title}' 已下载完整范围 {sub.start_episode}-{sub.end_episode}，自动关闭")
                return True
        return False

    @staticmethod
    def check_subscription_filter(sub: Subscription, final: Dict[str, Any], title: str) -> Tuple[bool, str]:
        """
        检查条目是否符合订阅的过滤规则。
        支持：空格=且(AND)，|=或(OR)
        """
        title_lower = title.lower()

        if sub.include_keywords:
            or_groups = [g.strip() for g in sub.include_keywords.split('|') if g.strip()]
            matched_any_group = False
            for group in or_groups:
                keywords = [k.strip().lower() for k in group.split() if k.strip()]
                if keywords and all(k in title_lower for k in keywords):
                    matched_any_group = True
                    break
            if not matched_any_group:
                return False, f"未包含指定关键字组: {sub.include_keywords}"
        
        if sub.exclude_keywords:
            exclude_terms = []
            for group in sub.exclude_keywords.split('|'):
                exclude_terms.extend([k.strip().lower() for k in group.split() if k.strip()])
            for term in exclude_terms:
                if term in title_lower:
                    return False, f"包含排除关键字: {term}"
        
        field_map = {
            "filter_res": "resolution", "filter_team": "team", "filter_source": "source",
            "filter_codec": "video_encode", "filter_audio": "audio_encode", "filter_sub": "subtitle",
            "filter_effect": "video_effect", "filter_platform": "platform"
        }
        
        for sub_field, rec_field in field_map.items():
            required_val = getattr(sub, sub_field, None)
            if required_val and required_val.strip():
                actual_val = final.get(rec_field)
                allowed_vals = [v.strip().lower() for v in required_val.split(',') if v.strip()]
                if not actual_val or str(actual_val).lower() not in allowed_vals:
                    return False, f"字段 {rec_field} 不匹配 (期待: {required_val}, 实际: {actual_val})"
        
        return True, ""
