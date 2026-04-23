import logging
import asyncio
from datetime import datetime, date
from typing import List, Dict, Any, Optional
from sqlmodel import select
from database import db
from models import Subscription, CalendarSubject, SubscribedEpisode
from notification import NotificationManager
from recognition.data_provider.tmdb.client import TMDBProvider
from logger import log_audit

logger = logging.getLogger("SubscriptionNotifier")


class SubscriptionNotifier:
    _instance = None
    _last_check_time: Dict[str, datetime] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @staticmethod
    async def check_new_episodes() -> Dict[str, Any]:
        """
        检查所有订阅番剧是否有新集播出
        返回: {"new_episodes": [...], "notifications_sent": int}
        """
        from config_manager import ConfigManager
        config = ConfigManager.get_config()
        
        if not config.get("subscription_notify_enabled", True):
            logger.info("[订阅提醒] 功能已禁用")
            return {"new_episodes": [], "notifications_sent": 0}
        
        logger.info("[订阅提醒] 开始检查订阅更新...")
        
        new_episodes = []
        notifications_sent = 0
        
        try:
            subscriptions = await SubscriptionNotifier._get_active_subscriptions()
            
            for sub in subscriptions:
                try:
                    new_eps = await SubscriptionNotifier._check_subscription(sub)
                    if new_eps:
                        new_episodes.extend(new_eps)
                        
                        if config.get("subscription_notify_on_new_episode", True):
                            for ep_info in new_eps:
                                sent = await SubscriptionNotifier._send_new_episode_notification(sub, ep_info)
                                if sent:
                                    notifications_sent += 1
                                    
                except Exception as e:
                    logger.error(f"[订阅提醒] 检查订阅 {sub.title} 失败: {e}")
                    continue
            
            logger.info(f"[订阅提醒] 检查完成，发现 {len(new_episodes)} 个新集，发送 {notifications_sent} 条通知")
            
            return {
                "new_episodes": new_episodes,
                "notifications_sent": notifications_sent,
                "checked_count": len(subscriptions)
            }
            
        except Exception as e:
            logger.error(f"[订阅提醒] 检查失败: {e}")
            return {"new_episodes": [], "notifications_sent": 0, "error": str(e)}
    
    @staticmethod
    async def _get_active_subscriptions() -> List[Subscription]:
        """获取所有启用的订阅"""
        async with db.session_scope():
            stmt = select(Subscription).where(Subscription.enabled == True)
            return await db.all(Subscription, stmt)
    
    @staticmethod
    async def _check_subscription(sub: Subscription) -> List[Dict]:
        """
        检查单个订阅是否有新集
        返回新集列表: [{"episode": 1, "air_date": "2024-01-01", "title": "..."}]
        """
        new_episodes = []
        
        try:
            tmdb = TMDBProvider()
            episodes = await tmdb.get_season_episodes(sub.tmdb_id, sub.season)
            
            if not episodes:
                return []
            
            async with db.session_scope():
                for ep in episodes:
                    ep_num = ep.get("episode_number")
                    air_date_str = ep.get("air_date")
                    
                    if not ep_num or not air_date_str:
                        continue
                    
                    try:
                        air_date = datetime.strptime(air_date_str, "%Y-%m-%d").date()
                    except:
                        continue
                    
                    today = date.today()
                    if air_date > today:
                        continue
                    
                    stmt = select(SubscribedEpisode).where(
                        SubscribedEpisode.tmdb_id == str(sub.tmdb_id),
                        SubscribedEpisode.season == sub.season,
                        SubscribedEpisode.episode == ep_num
                    )
                    exists = await db.first(SubscribedEpisode, stmt)
                    
                    if not exists:
                        new_episodes.append({
                            "episode": ep_num,
                            "air_date": air_date_str,
                            "title": ep.get("name", f"第{ep_num}集"),
                            "overview": ep.get("overview", ""),
                            "still_path": ep.get("still_path")
                        })
                        
                        await SubscriptionNotifier._mark_episode_notified(
                            sub.tmdb_id, sub.media_type, sub.season, ep_num
                        )
            
            if new_episodes:
                await SubscriptionNotifier._update_calendar_cache(sub, episodes)
                
        except Exception as e:
            logger.error(f"[订阅提醒] 检查 {sub.title} 失败: {e}")
        
        return new_episodes
    
    @staticmethod
    async def _mark_episode_notified(tmdb_id: str, media_type: str, season: int, episode: int):
        """标记剧集已通知"""
        async with db.session_scope():
            ep_record = SubscribedEpisode(
                tmdb_id=str(tmdb_id),
                media_type=media_type,
                season=season,
                episode=episode
            )
            await db.save(ep_record)
    
    @staticmethod
    async def _update_calendar_cache(sub: Subscription, episodes: List[Dict]):
        """更新日历缓存"""
        try:
            async with db.session_scope():
                stmt = select(CalendarSubject).where(
                    CalendarSubject.tmdb_id == sub.tmdb_id,
                    CalendarSubject.season == sub.season
                )
                cal = await db.first(CalendarSubject, stmt)
                
                if cal:
                    cal.episodes_cache = episodes
                    await db.save(cal)
        except Exception as e:
            logger.warning(f"[订阅提醒] 更新日历缓存失败: {e}")
    
    @staticmethod
    async def _send_new_episode_notification(sub: Subscription, ep_info: Dict) -> bool:
        """发送新集通知"""
        try:
            ep_num = ep_info.get("episode")
            ep_title = ep_info.get("title", f"第{ep_num}集")
            air_date = ep_info.get("air_date", "")
            
            season_str = f"S{sub.season:02d}" if sub.season else ""
            ep_str = f"E{ep_num:02d}"
            
            msg = (
                f"🎬 <b>新集播出提醒</b>\n\n"
                f"📺 <b>番剧：</b>{sub.title}\n"
                f"🔢 <b>集数：</b>{season_str}{ep_str}\n"
                f"📝 <b>标题：</b>{ep_title}\n"
                f"📅 <b>日期：</b>{air_date}\n"
            )
            
            if sub.poster_path:
                poster_url = f"https://image.tmdb.org/t/p/w500{sub.poster_path}"
                success, _, _ = await NotificationManager.send_telegram_message(msg, photo_url=poster_url)
            else:
                success, _, _ = await NotificationManager.send_telegram_message(msg)
            
            if success:
                log_audit("订阅提醒", "通知发送", f"{sub.title} {season_str}{ep_str}")
            
            return success
            
        except Exception as e:
            logger.error(f"[订阅提醒] 发送通知失败: {e}")
            return False
    
    @staticmethod
    async def check_today_airing() -> List[Dict]:
        """
        检查今天播出的订阅番剧
        返回: [{"title": "...", "episode": 1, "air_time": "..."}]
        """
        today_airing = []
        weekday = date.today().weekday() + 1
        
        try:
            subscriptions = await SubscriptionNotifier._get_active_subscriptions()
            
            for sub in subscriptions:
                try:
                    tmdb = TMDBProvider()
                    episodes = await tmdb.get_season_episodes(sub.tmdb_id, sub.season)
                    
                    today_str = date.today().isoformat()
                    
                    for ep in episodes:
                        air_date = ep.get("air_date")
                        if air_date == today_str:
                            today_airing.append({
                                "title": sub.title,
                                "season": sub.season,
                                "episode": ep.get("episode_number"),
                                "ep_title": ep.get("name", f"第{ep.get('episode_number')}集"),
                                "poster_path": sub.poster_path
                            })
                            
                except Exception as e:
                    logger.warning(f"[订阅提醒] 检查 {sub.title} 今日播出失败: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"[订阅提醒] 检查今日播出失败: {e}")
        
        return today_airing
    
    @staticmethod
    async def send_daily_summary():
        """发送每日番剧播出摘要"""
        from config_manager import ConfigManager
        config = ConfigManager.get_config()
        
        if not config.get("subscription_daily_summary", False):
            return
        
        today_airing = await SubscriptionNotifier.check_today_airing()
        
        if not today_airing:
            logger.info("[订阅提醒] 今日无订阅番剧播出")
            return
        
        lines = ["📅 <b>今日番剧播出</b>\n"]
        
        for item in today_airing:
            season_str = f"S{item['season']:02d}" if item.get('season') else ""
            ep_str = f"E{item['episode']:02d}"
            lines.append(f"🎬 {item['title']} {season_str}{ep_str}")
            lines.append(f"   └ {item['ep_title']}\n")
        
        msg = "\n".join(lines)
        await NotificationManager.send_telegram_message(msg)
        log_audit("订阅提醒", "每日摘要", f"共 {len(today_airing)} 部番剧今日播出")


async def check_subscription_updates():
    """调度入口：检查订阅更新"""
    return await SubscriptionNotifier.check_new_episodes()


async def send_daily_anime_summary():
    """调度入口：发送每日摘要"""
    return await SubscriptionNotifier.send_daily_summary()
