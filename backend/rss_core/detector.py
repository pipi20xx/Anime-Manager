import asyncio
import re
import feedparser
import logging
import httpx
from typing import List, Dict, Any, Optional, Set, Tuple
from datetime import datetime
from sqlmodel import select

from models import (
    RssDetectTask, Subscription, SubscriptionTemplate,
    FeedItem, DownloadHistory, SubscribedEpisode
)
from database import db
from rss_core.manager import RssManager, normalize_guid
from rss_core.subscription_matcher import SubscriptionMatcher
from recognition.recognizer import MovieRecognizer
from clients.manager import ClientManager
from logger import log_audit
from task_history import start_task, log_task, finish_task

logger = logging.getLogger("RssDetector")


class RssDetector:
    """RSS 探测与自动订阅核心逻辑"""

    @staticmethod
    async def parse_rss(rss_url: str) -> Tuple[List[Dict], Optional[str]]:
        """解析 RSS 链接，返回条目列表和错误信息"""
        from config_manager import ConfigManager
        
        proxy = ConfigManager.get_proxy("rss")
        try:
            async with httpx.AsyncClient(proxy=proxy, timeout=30.0, follow_redirects=True) as client:
                resp = await client.get(rss_url)
                resp.raise_for_status()
                content = resp.content
            
            parsed = feedparser.parse(content)
            entries = []
            
            for entry in parsed.entries:
                title = entry.get('title', 'No Title')
                link = entry.get('link', '')
                
                for enc in entry.get('enclosures', []):
                    if enc.get('href'):
                        link = enc.get('href')
                        break
                
                raw_guid = entry.get('id', link)
                entries.append({
                    'title': title,
                    'link': link,
                    'description': entry.get('summary', entry.get('description', '')),
                    'guid': normalize_guid(raw_guid),
                    'pub_date': entry.get('published', entry.get('updated', ''))
                })
            
            return entries, None
            
        except Exception as e:
            return [], f"RSS 解析失败: {str(e)}"

    @staticmethod
    async def detect_and_preview(
        rss_url: str,
        template_id: Optional[int] = None,
        filter_res: Optional[str] = None,
        filter_team: Optional[str] = None,
        **filter_kwargs
    ) -> Dict[str, Any]:
        """
        探测 RSS 并返回预览结果（不创建订阅）
        
        返回:
        {
            "total_entries": N,
            "detected_shows": [
                {
                    "tmdb_id": "12345",
                    "title": "番剧名",
                    "media_type": "tv",
                    "season": 1,
                    "year": "2024",
                    "poster_path": "...",
                    "entry_count": 5,
                    "is_subscribed": false
                },
                ...
            ],
            "failed_entries": [...]
        }
        """
        entries, error = await RssDetector.parse_rss(rss_url)
        if error:
            return {"error": error, "total_entries": 0, "detected_shows": []}
        
        if not entries:
            return {"total_entries": 0, "detected_shows": [], "message": "RSS 源为空"}
        
        task_id = f"detect_{datetime.now().strftime('%H%M%S')}"
        
        recognized = await SubscriptionMatcher.recognize_items(entries, task_id=None)
        
        show_map: Dict[str, Dict] = {}
        failed_titles = []
        
        for i, entry in enumerate(entries):
            title = entry['title']
            
            async with db.session_scope():
                item_stmt = select(FeedItem).where(FeedItem.guid == entry['guid'])
                item = await db.first(FeedItem, item_stmt)
                
                tmdb_id = None
                if item and item.tmdb_id and item.tmdb_id != "None" and item.tmdb_id != "":
                    tmdb_id = item.tmdb_id
                
                if not tmdb_id:
                    failed_titles.append(title)
                    continue
                
                if tmdb_id not in show_map:
                    sub_stmt = select(Subscription).where(Subscription.tmdb_id == tmdb_id)
                    existing_sub = await db.first(Subscription, sub_stmt)
                    
                    show_map[tmdb_id] = {
                        "tmdb_id": tmdb_id,
                        "title": item.tmdb_title or re.split(r'[/\[]', title)[0].strip(),
                        "media_type": item.media_type or "tv",
                        "season": item.season or 1,
                        "year": None,
                        "poster_path": None,
                        "entry_count": 0,
                        "is_subscribed": existing_sub is not None
                    }
                
                show_map[tmdb_id]["entry_count"] += 1
        
        detected_shows = list(show_map.values())
        
        for show in detected_shows:
            show["total_episodes"] = await RssDetector._get_season_episode_count(
                show["tmdb_id"], show.get("season", 1)
            )
        
        return {
            "total_entries": len(entries),
            "detected_shows": detected_shows,
            "failed_count": len(failed_titles),
            "failed_entries": failed_titles[:20]
        }

    @staticmethod
    async def _get_season_episode_count(tmdb_id: str, season: int) -> int:
        try:
            from recognition.data_provider.tmdb.client import TMDBProvider
            provider = TMDBProvider()
            details = await provider.get_subject_details(tmdb_id, "tv")
            if not details:
                return 0
            for s in details.get("seasons", []):
                if s.get("season_number") == season:
                    count = s.get("episode_count", 0)
                    logger.debug(f"TMDB 季集查询: {tmdb_id} S{season} = {count} 集")
                    return count
            return 0
        except Exception as e:
            logger.warning(f"TMDB 季集查询失败: {tmdb_id} S{season} - {e}")
            return 0

    @staticmethod
    async def detect_and_subscribe(
        rss_url: str,
        task_config: Optional[RssDetectTask] = None,
        template_id: Optional[int] = None,
        filter_res: Optional[str] = None,
        filter_team: Optional[str] = None,
        target_client_id: Optional[str] = None,
        save_path: Optional[str] = None,
        category: str = "Anime",
        auto_fill: bool = True,
        **filter_kwargs
    ) -> Dict[str, Any]:
        """
        探测 RSS 并自动创建订阅
        
        返回统计结果
        """
        task_id = f"rss_detect_{datetime.now().strftime('%H%M%S')}"
        await start_task(task_id, "RSS探测", f"探测: {rss_url[:50]}...")
        await log_task(task_id, f"🔗 开始探测 RSS: {rss_url[:60]}")
        
        preview = await RssDetector.detect_and_preview(
            rss_url, template_id, filter_res, filter_team, **filter_kwargs
        )
        
        if "error" in preview:
            await log_task(task_id, f"❌ {preview['error']}", "ERROR")
            await finish_task(task_id, "failed", 0)
            return {"success": False, "error": preview["error"]}
        
        shows = preview.get("detected_shows", [])
        if not shows:
            await log_task(task_id, "⚠️ 未识别到任何番剧")
            await finish_task(task_id, "completed", 0)
            return {"success": True, "created": 0, "skipped": 0, "shows": []}
        
        await log_task(task_id, f"📺 识别到 {len(shows)} 个番剧")
        
        tmpl = None
        if template_id:
            async with db.session_scope():
                tmpl = await db.get(SubscriptionTemplate, template_id)
        if not tmpl:
            async with db.session_scope():
                stmt = select(SubscriptionTemplate).where(SubscriptionTemplate.is_default == True)
                tmpl = await db.first(SubscriptionTemplate, stmt)
        
        default_client = ClientManager.get_client()
        default_client_id = default_client.config.get('id') if default_client else None
        
        created = 0
        skipped = 0
        details = []
        
        for show in shows:
            if show.get("is_subscribed"):
                skipped += 1
                details.append({"tmdb_id": show["tmdb_id"], "title": show["title"], "status": "skipped"})
                continue
            
            try:
                season = show.get("season", 1)
                end_episode = await RssDetector._get_season_episode_count(show["tmdb_id"], season)
                
                sub = Subscription(
                    tmdb_id=show["tmdb_id"],
                    media_type=show.get("media_type", "tv"),
                    title=show["title"],
                    year=show.get("year"),
                    poster_path=show.get("poster_path"),
                    season=season,
                    start_episode=1,
                    end_episode=end_episode,
                    enabled=True,
                    auto_fill=auto_fill,
                    target_client_id=target_client_id or (tmpl.target_client_id if tmpl else default_client_id),
                    save_path=save_path or (tmpl.save_path if tmpl else None),
                    category=category or (tmpl.category if tmpl else "Anime"),
                    filter_res=filter_res or (tmpl.filter_res if tmpl else None),
                    filter_team=filter_team or (tmpl.filter_team if tmpl else None),
                    filter_source=filter_kwargs.get('filter_source') or (tmpl.filter_source if tmpl else None),
                    filter_codec=filter_kwargs.get('filter_codec') or (tmpl.filter_codec if tmpl else None),
                    filter_audio=filter_kwargs.get('filter_audio') or (tmpl.filter_audio if tmpl else None),
                    filter_sub=filter_kwargs.get('filter_sub') or (tmpl.filter_sub if tmpl else None),
                    filter_effect=filter_kwargs.get('filter_effect') or (tmpl.filter_effect if tmpl else None),
                    filter_platform=filter_kwargs.get('filter_platform') or (tmpl.filter_platform if tmpl else None),
                    include_keywords=filter_kwargs.get('include_keywords') or (tmpl.include_keywords if tmpl else None),
                    exclude_keywords=filter_kwargs.get('exclude_keywords') or (tmpl.exclude_keywords if tmpl else None),
                )
                
                async with db.session_scope():
                    saved = await db.save(sub)
                
                created += 1
                ep_info = f"S{season} E1-{end_episode}" if end_episode > 0 else f"S{season}"
                details.append({"tmdb_id": show["tmdb_id"], "title": show["title"], "status": "created", "episode_info": ep_info})
                await log_task(task_id, f"  ✅ 已订阅: {show['title']} ({ep_info})")
                
            except Exception as e:
                skipped += 1
                details.append({"tmdb_id": show["tmdb_id"], "title": show["title"], "status": "error", "message": str(e)})
                await log_task(task_id, f"  ❌ 订阅失败: {show['title']} - {str(e)}", "ERROR")
        
        result = {
            "success": True,
            "created": created,
            "skipped": skipped,
            "shows": details,
            "total_detected": len(shows)
        }
        
        if task_config:
            async with db.session_scope():
                task_config.last_run_at = datetime.now()
                task_config.last_result = result
                task_config.updated_at = datetime.now()
                await db.save(task_config, audit=False)
        
        await log_task(task_id, f"🏁 完成！新增订阅 {created} 个，跳过 {skipped} 个")
        await finish_task(task_id, "completed", created, result)
        log_audit("RSS探测", "完成", f"URL: {rss_url[:50]}... 新增{created}个，跳过{skipped}个")
        
        return result

    @staticmethod
    async def run_scheduled_tasks():
        """执行所有到期的定时探测任务"""
        from config_manager import ConfigManager
        
        async with db.session_scope():
            stmt = select(RssDetectTask).where(RssDetectTask.enabled == True)
            tasks = await db.all(RssDetectTask, stmt)
        
        now = datetime.now()
        ran_count = 0
        
        for task in tasks:
            should_run = False
            
            if not task.last_run_at:
                should_run = True
            elif task.interval_minutes > 0:
                elapsed = (now - task.last_run_at).total_seconds() / 60
                if elapsed >= task.interval_minutes:
                    should_run = True
            
            if not should_run:
                continue
            
            logger.info(f"[RssDetector] 执行定时任务: {task.name or task.rss_url[:30]}")
            
            try:
                await RssDetector.detect_and_subscribe(
                    rss_url=task.rss_url,
                    task_config=task,
                    template_id=task.template_id,
                    filter_res=task.filter_res,
                    filter_team=task.filter_team,
                    filter_source=task.filter_source,
                    filter_codec=task.filter_codec,
                    filter_audio=task.filter_audio,
                    filter_sub=task.filter_sub,
                    filter_effect=task.filter_effect,
                    filter_platform=task.filter_platform,
                    include_keywords=task.include_keywords,
                    exclude_keywords=task.exclude_keywords,
                    target_client_id=task.target_client_id,
                    save_path=task.save_path,
                    category=task.category or "Anime",
                    auto_fill=task.auto_fill
                )
                ran_count += 1
            except Exception as e:
                logger.error(f"[RssDetector] 任务执行失败 ({task.name}): {e}")
        
        if ran_count > 0:
            logger.info(f"[RssDetector] 共执行 {ran_count} 个定时任务")

    @staticmethod
    async def get_tasks() -> List[RssDetectTask]:
        async with db.session_scope():
            return await db.all(RssDetectTask)

    @staticmethod
    async def save_task(task: RssDetectTask) -> RssDetectTask:
        _exclude = {"last_run_at", "created_at", "updated_at", "last_result"}
        async with db.session_scope():
            if task.id:
                existing = await db.get(RssDetectTask, task.id)
                if existing:
                    for key, value in task.model_dump(exclude_unset=True, exclude=_exclude).items():
                        setattr(existing, key, value)
                    saved = await db.save(existing)
                    log_audit("RSS探测", "更新任务", f"已更新: {saved.name or saved.rss_url[:30]}")
                    return saved
            
            saved = await db.save(task)
            log_audit("RSS探测", "新建任务", f"已创建: {saved.name or saved.rss_url[:30]}")
            return saved

    @staticmethod
    async def delete_task(task_id: int):
        async with db.session_scope():
            task = await db.get(RssDetectTask, task_id)
            if task:
                name = task.name or task.rss_url[:30]
                await db.delete(task)
                log_audit("RSS探测", "删除任务", f"已删除: {name}")

    @staticmethod
    async def run_task_once(task_id: int) -> Dict[str, Any]:
        """手动触发单个任务执行"""
        async with db.session_scope():
            task = await db.get(RssDetectTask, task_id)
            if not task:
                return {"success": False, "error": "任务不存在"}
        
        return await RssDetector.detect_and_subscribe(
            rss_url=task.rss_url,
            task_config=task,
            template_id=task.template_id,
            filter_res=task.filter_res,
            filter_team=task.filter_team,
            filter_source=task.filter_source,
            filter_codec=task.filter_codec,
            filter_audio=task.filter_audio,
            filter_sub=task.filter_sub,
            filter_effect=task.filter_effect,
            filter_platform=task.filter_platform,
            include_keywords=task.include_keywords,
            exclude_keywords=task.exclude_keywords,
            target_client_id=task.target_client_id,
            save_path=task.save_path,
            category=task.category or "Anime",
            auto_fill=task.auto_fill
        )
