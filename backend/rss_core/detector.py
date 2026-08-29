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
from rss_core.subscription_manager import SubscriptionManager
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
        include_keywords: Optional[str] = None,
        exclude_keywords: Optional[str] = None,
        **filter_kwargs
    ) -> Dict[str, Any]:
        """
        探测 RSS 并返回预览结果（不创建订阅）

        识别不再依赖 feed_items 表缓存：已落库的条目直接取缓存，
        未落库的条目在内存中即时识别，因此任意 RSS 链接填入即可预览。
        同时真正应用筛选条件（8 个 filter 字段 + 包含/排除关键词，
        未填时回退到所选预设模板的对应字段），逐条给出通过/被过滤及原因。

        返回:
        {
            "total_entries": N,
            "recognized_count": Y,
            "filter_passed_count": W,
            "detected_shows": [
                {
                    "tmdb_id": "12345",
                    "title": "番剧名",
                    "media_type": "tv",
                    "season": 1,
                    "year": "2024",
                    "poster_path": "...",
                    "entry_count": 5,
                    "matched_entry_count": 3,
                    "is_subscribed": false
                },
                ...
            ],
            "entries": [ ... 每条条目的识别与筛选明细 ... ],
            "failed_entries": [...]
        }
        """
        from config_manager import ConfigManager

        entries, error = await RssDetector.parse_rss(rss_url)
        if error:
            return {"error": error, "total_entries": 0, "detected_shows": []}

        if not entries:
            return {"total_entries": 0, "detected_shows": [], "message": "RSS 源为空"}

        # 筛选条件：请求参数优先，未填的字段回退到所选预设模板
        tmpl = None
        if template_id:
            async with db.session_scope():
                tmpl = await db.get(SubscriptionTemplate, template_id)
        filter_cfg = Subscription(
            tmdb_id="", title="",
            include_keywords=include_keywords or (tmpl.include_keywords if tmpl else None),
            exclude_keywords=exclude_keywords or (tmpl.exclude_keywords if tmpl else None),
            filter_res=filter_res or (tmpl.filter_res if tmpl else None),
            filter_team=filter_team or (tmpl.filter_team if tmpl else None),
            filter_source=filter_kwargs.get("filter_source") or (tmpl.filter_source if tmpl else None),
            filter_codec=filter_kwargs.get("filter_codec") or (tmpl.filter_codec if tmpl else None),
            filter_audio=filter_kwargs.get("filter_audio") or (tmpl.filter_audio if tmpl else None),
            filter_sub=filter_kwargs.get("filter_sub") or (tmpl.filter_sub if tmpl else None),
            filter_effect=filter_kwargs.get("filter_effect") or (tmpl.filter_effect if tmpl else None),
            filter_platform=filter_kwargs.get("filter_platform") or (tmpl.filter_platform if tmpl else None),
        )

        config = ConfigManager.get_config()
        can_recognize = bool(config.get("tmdb_api_key"))
        global_anime_prio = config.get("anime_priority", True)
        bgm_prio = config.get("bangumi_priority", False)
        bgm_failover = config.get("bangumi_failover", True)

        entries_out: List[Dict] = []
        show_map: Dict[str, Dict] = {}
        failed_titles: List[str] = []

        for entry in entries:
            detail: Dict[str, Any] = {
                "title": entry["title"],
                "tmdb_id": None, "tmdb_title": None, "media_type": None,
                "season": None, "episode": None,
                "resolution": None, "team": None, "source": None,
                "video_encode": None, "audio_encode": None,
                "subtitle": None, "video_effect": None, "platform": None,
                "recognized": False,
                "filter_passed": False,
                "filter_reason": "",
                "is_subscribed": False,
            }

            final: Optional[Dict[str, Any]] = None

            async with db.session_scope():
                item_stmt = select(FeedItem).where(FeedItem.guid == entry["guid"])
                item = await db.first(FeedItem, item_stmt)

            if item and item.tmdb_id and item.tmdb_id not in ("", "None"):
                # 已落库且识别过：直接取缓存，避免重复请求 TMDB
                final = {
                    "tmdb_id": item.tmdb_id, "title": item.tmdb_title,
                    "category": "电影" if item.media_type == "movie" else "剧集",
                    "season": item.season, "episode": item.episode,
                    "resolution": item.resolution, "team": item.team,
                    "source": item.source, "video_encode": item.video_encode,
                    "audio_encode": item.audio_encode, "video_effect": item.video_effect,
                    "subtitle": item.subtitle, "platform": item.platform,
                }
            elif can_recognize:
                # 未落库/识别未成功：内存中即时识别（仅当已有落库条目时回写缓存）
                try:
                    result, _logs = await MovieRecognizer.recognize_full(
                        entry["title"], force_filename=True,
                        anime_priority=global_anime_prio, bangumi_priority=bgm_prio,
                        bangumi_failover=bgm_failover,
                        batch_enhancement=True,
                        description=None
                    )
                    if result.get("success") and result.get("final_result"):
                        final = result["final_result"]
                        if item:
                            await RssManager.update_item_recognition(item.id, final)
                except Exception as e:
                    logger.warning(f"[RssDetector] 预览识别失败: {entry['title'][:50]} - {e}")

            if final and final.get("tmdb_id") and str(final.get("tmdb_id")) not in ("", "None"):
                tmdb_id = str(final["tmdb_id"])
                detail.update({
                    "recognized": True,
                    "tmdb_id": tmdb_id,
                    "tmdb_title": final.get("title"),
                    "media_type": "movie" if final.get("category") == "电影" else "tv",
                    "season": final.get("season") or 1,
                    "episode": str(final.get("episode")) if final.get("episode") is not None else None,
                    "resolution": final.get("resolution"),
                    "team": final.get("team"),
                    "source": final.get("source"),
                    "video_encode": final.get("video_encode"),
                    "audio_encode": final.get("audio_encode"),
                    "subtitle": final.get("subtitle"),
                    "video_effect": final.get("video_effect"),
                    "platform": final.get("platform"),
                })
                passed, reason = SubscriptionManager.check_subscription_filter(filter_cfg, final, entry["title"])
                detail["filter_passed"] = passed
                detail["filter_reason"] = reason

                if tmdb_id not in show_map:
                    async with db.session_scope():
                        sub_stmt = select(Subscription).where(Subscription.tmdb_id == tmdb_id)
                        existing_sub = await db.first(Subscription, sub_stmt)

                    show_map[tmdb_id] = {
                        "tmdb_id": tmdb_id,
                        "title": final.get("title") or re.split(r'[/\[]', entry["title"])[0].strip(),
                        "media_type": detail["media_type"],
                        "season": detail["season"],
                        "year": final.get("year"),
                        "poster_path": final.get("poster_path"),
                        "entry_count": 0,
                        "matched_entry_count": 0,
                        "is_subscribed": existing_sub is not None
                    }
                elif not show_map[tmdb_id]["poster_path"] and final.get("poster_path"):
                    show_map[tmdb_id]["poster_path"] = final.get("poster_path")
                    if not show_map[tmdb_id]["year"]:
                        show_map[tmdb_id]["year"] = final.get("year")

                show_map[tmdb_id]["entry_count"] += 1
                if passed:
                    show_map[tmdb_id]["matched_entry_count"] += 1
                detail["is_subscribed"] = show_map[tmdb_id]["is_subscribed"]
            else:
                failed_titles.append(entry["title"])

            entries_out.append(detail)

        detected_shows = list(show_map.values())

        for show in detected_shows:
            show["total_episodes"] = await RssDetector._get_season_episode_count(
                show["tmdb_id"], show.get("season", 1)
            )

        return {
            "total_entries": len(entries),
            "recognized_count": sum(1 for d in entries_out if d["recognized"]),
            "filter_passed_count": sum(1 for d in entries_out if d["filter_passed"]),
            "detected_shows": detected_shows,
            "entries": entries_out,
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
    async def subscribe_show(
        tmdb_id: str,
        title: str,
        media_type: str = "tv",
        season: int = 1,
        poster_path: Optional[str] = None,
        year: Optional[str] = None,
        filter_res: Optional[str] = None,
        filter_team: Optional[str] = None,
        target_client_id: Optional[str] = None,
        save_path: Optional[str] = None,
        category: str = "Anime",
        auto_fill: bool = True,
        **filter_kwargs
    ) -> Dict[str, Any]:
        """
        从预览结果直接添加单个订阅（按 TMDB ID 去重，不重复创建）。
        筛选规格由前端从预览条目明细中提取后传入，未传的字段回退到默认模板。
        海报/年份优先使用预览识别结果，缺失时从 TMDB 现查兜底。
        """
        tmdb_id = str(tmdb_id)

        async with db.session_scope():
            existing = await db.first(
                Subscription, select(Subscription).where(Subscription.tmdb_id == tmdb_id)
            )
        if existing:
            return {"success": True, "created": False, "message": f"《{existing.title}》已存在订阅"}

        if not poster_path:
            try:
                from recognition.data_provider.tmdb.client import TMDBProvider
                details = await TMDBProvider().get_subject_details(tmdb_id, media_type or "tv")
                if details:
                    poster_path = details.get("poster_path") or poster_path
                    if not year:
                        date_val = details.get("release_date") or details.get("first_air_date") or ""
                        year = str(date_val)[:4] or None
            except Exception as e:
                logger.warning(f"[RssDetector] 订阅海报查询失败: {tmdb_id} - {e}")

        tmpl = None
        async with db.session_scope():
            stmt = select(SubscriptionTemplate).where(SubscriptionTemplate.is_default == True)
            tmpl = await db.first(SubscriptionTemplate, stmt)

        end_episode = await RssDetector._get_season_episode_count(tmdb_id, season)

        sub = Subscription(
            tmdb_id=tmdb_id,
            media_type=media_type or "tv",
            title=title,
            year=year,
            poster_path=poster_path,
            season=season,
            start_episode=1,
            end_episode=end_episode,
            enabled=True,
            auto_fill=auto_fill,
            target_client_id=target_client_id or (tmpl.target_client_id if tmpl else None),
            save_path=save_path or (tmpl.save_path if tmpl else None),
            category=category or (tmpl.category if tmpl else "Anime"),
            filter_res=filter_res or (tmpl.filter_res if tmpl else None),
            filter_team=filter_team or (tmpl.filter_team if tmpl else None),
            filter_source=filter_kwargs.get("filter_source") or (tmpl.filter_source if tmpl else None),
            filter_codec=filter_kwargs.get("filter_codec") or (tmpl.filter_codec if tmpl else None),
            filter_audio=filter_kwargs.get("filter_audio") or (tmpl.filter_audio if tmpl else None),
            filter_sub=filter_kwargs.get("filter_sub") or (tmpl.filter_sub if tmpl else None),
            filter_effect=filter_kwargs.get("filter_effect") or (tmpl.filter_effect if tmpl else None),
            filter_platform=filter_kwargs.get("filter_platform") or (tmpl.filter_platform if tmpl else None),
        )

        async with db.session_scope():
            saved = await db.save(sub)

        ep_info = f"S{season} E1-{end_episode}" if end_episode > 0 else f"S{season}"
        log_audit("RSS探测", "预览订阅", f"已订阅: {saved.title} ({ep_info}) TMDB: {tmdb_id}")
        return {"success": True, "created": True, "subscription_id": saved.id, "end_episode": end_episode}

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
