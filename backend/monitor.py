import os
import time
import asyncio
import logging
import threading
import uuid
from typing import Dict, Any, List, Optional
from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver
from watchdog.events import FileSystemEventHandler
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from organizer_core.organizer import Organizer
from strm.strm_generator import StrmGenerator
from strm.processor import StrmProcessor
from config_manager import ConfigManager
from metadata.meta_cache import MetaCacheManager
from rss_core.scheduler import refresh_all_feeds, check_stalled_downloads
from clients.cd2_monitor import CD2TransferMonitor
from task_history import start_task, log_task, finish_task

logger = logging.getLogger("Monitor")

class StabilityChecker:
    TEMP_EXTENSIONS = ['.tmp', '.part', '.crdownload', '.!qB', '.download']

    @staticmethod
    def is_temp_file(file_path: str) -> bool:
        ext = os.path.splitext(file_path)[1].lower()
        return ext in StabilityChecker.TEMP_EXTENSIONS

    @staticmethod
    async def wait_for_stability(file_path: str, stability_duration: int = 5, check_interval: int = 2) -> bool:
        """
        等待文件大小稳定。
        """
        if not os.path.exists(file_path):
            return False
        
        last_size = -1
        stable_count = 0
        max_checks = 30 # Max wait 60s
        
        for _ in range(max_checks):
            try:
                current_size = os.path.getsize(file_path)
            except FileNotFoundError:
                return False

            if current_size == last_size and current_size > 0:
                stable_count += 1
            else:
                stable_count = 0
            
            last_size = current_size
            
            # 连续几次检测大小一致，且总等待时间超过 stability_duration
            if stable_count * check_interval >= stability_duration:
                return True
            
            await asyncio.sleep(check_interval)
            
        return False

class OrganizerEventHandler(FileSystemEventHandler):
    def __init__(self, tasks: List[Dict[str, Any]], loop: asyncio.AbstractEventLoop, queues: Dict[str, asyncio.Queue]):
        self.tasks = tasks
        self.loop = loop
        self.queues = queues
        self.recent_events = {} # path -> timestamp

    def _process(self, file_path: str, event_type: str = "created"):
        if os.path.isdir(file_path): return

        abs_path = os.path.abspath(file_path)
        filename = os.path.basename(file_path)
        now = time.time()
        
        if abs_path in self.recent_events:
            if now - self.recent_events[abs_path] < 5:
                return
        self.recent_events[abs_path] = now

        if len(self.recent_events) > 100:
            self.recent_events = {p: t for p, t in self.recent_events.items() if now - t < 60}
        
        ext = os.path.splitext(file_path)[1].lower()
        from strm.constants import VIDEO_EXTENSIONS
        if ext not in Organizer.VIDEO_EXTS and ext not in VIDEO_EXTENSIONS:
            if not StabilityChecker.is_temp_file(file_path):
                return
            else:
                logger.debug(f"[实时监控] 跳过临时文件: {filename}")
                return

        if StabilityChecker.is_temp_file(file_path):
            logger.debug(f"[实时监控] 临时文件等待: {filename}")
            return
            
        matched_any = False
        
        config = ConfigManager.get_config()
        all_clients = {c.get('id'): c for c in config.get("download_clients", [])}

        for task in self.tasks:
            task_name = task.get("name", "未命名")
            source_dir = task.get("source_dir") or task.get("source_path")
            if not source_dir: continue
            
            local_match_root = source_dir
            if task.get("is_strm") and task.get("sync_mode") == "cd2_api":
                client_id = task.get("cd2_client_id")
                client_conf = all_clients.get(client_id, {})
                mapping_root = task.get("cd2_mapping_path") or client_conf.get("mount_path") or ""
                mapping_root = mapping_root.rstrip('/')
                source_dir_clean = '/' + source_dir.lstrip('/')
                local_match_root = mapping_root + source_dir_clean

            abs_source = os.path.abspath(local_match_root)
            if not abs_path.startswith(abs_source):
                continue
            
            exclude_keywords = task.get("exclude_keywords", [])
            is_excluded = False
            for kw in exclude_keywords:
                if kw and kw in file_path:
                    is_excluded = True
                    break
            if is_excluded: continue

            queue = self.queues.get(task.get("id"))
            if queue:
                self.loop.call_soon_threadsafe(queue.put_nowait, (file_path, None))
                matched_any = True

        if matched_any:
            logger.info(f"✨ [实时监控] 检测到新文件: {filename}")
        else:
            if ext in Organizer.VIDEO_EXTS or ext in VIDEO_EXTENSIONS:
                logger.debug(f"[实时监控] 文件未匹配任何任务: {filename}")

    def _process_dir(self, dir_path: str, event_type: str):
        if not os.path.exists(dir_path): return
        for root, _, files in os.walk(dir_path):
            for f in files:
                self._process(os.path.join(root, f), event_type)

    def on_moved(self, event):
        if event.is_directory:
            self._process_dir(event.dest_path, "moved")
        else:
            self._process(event.dest_path, "moved")

    def on_closed(self, event):
        # 某些系统(Linux)在文件关闭时触发 process 比较稳妥
        if not event.is_directory:
            self._process(event.src_path, "closed")
        
    def on_created(self, event):
        if event.is_directory:
            self._process_dir(event.src_path, "created")
        else:
            self._process(event.src_path, "created")
        
    def on_modified(self, event):
        # 只有在 polling 模式下 modified 可能被用来检测新文件
        pass

class MonitorManager:
    _observers: List[Observer] = []
    _scheduler: AsyncIOScheduler = None
    _loop: asyncio.AbstractEventLoop = None
    _queues: Dict[str, asyncio.Queue] = {} # task_id -> queue
    _workers: List[asyncio.Task] = []

    @staticmethod
    def _get_task_config(task_id: str, is_strm: bool = False) -> Optional[Dict[str, Any]]:
        config = ConfigManager.get_config()
        if is_strm:
            tasks = config.get("strm_tasks", [])
        else:
            tasks = config.get("organize_tasks", [])
        return next((t for t in tasks if t.get("id") == task_id), None)

    @staticmethod
    def init(loop: asyncio.AbstractEventLoop):
        MonitorManager._loop = loop
        
        import logging
        apscheduler_logger = logging.getLogger('apscheduler')
        apscheduler_logger.setLevel(logging.WARNING)
        
        MonitorManager._scheduler = AsyncIOScheduler(event_loop=loop)
        MonitorManager._scheduler.start()
        from logger import log_audit
        log_audit("系统", "监控初始化", "后台监控管理服务已初始化")

    @staticmethod
    def _setup_system_jobs():
        """配置并启动系统级定时任务"""
        if not MonitorManager._scheduler:
            return

        config = ConfigManager.get_config()
        
        # 1. 注册每日日志清理任务 (保留30天)
        MonitorManager._scheduler.add_job(
            MonitorManager._daily_cleanup,
            'cron',
            hour=3, # 凌晨3点
            minute=0,
            id="daily_cleanup_job",
            replace_existing=True
        )
        
        # 2. [RSS] 自动刷新任务
        if config.get("rss_auto_refresh", True):
            interval = int(config.get("rss_refresh_interval", 15))
            MonitorManager._scheduler.add_job(
                refresh_all_feeds,
                'interval',
                minutes=interval,
                id="rss_refresh_job",
                replace_existing=True
            )
            logger.info(f"[RSS] 已调度自动刷新，间隔 {interval} 分钟。")
        
        # 2.5 [RSS Detect] 探测自动订阅任务
        from rss_core.detector import RssDetector
        detect_interval = int(config.get("rss_detect_interval", 30))
        if detect_interval > 0:
            MonitorManager._scheduler.add_job(
                RssDetector.run_scheduled_tasks,
                'interval',
                minutes=detect_interval,
                id="rss_detect_job",
                replace_existing=True
            )
            logger.info(f"[RSS探测] 已调度自动探测订阅，间隔 {detect_interval} 分钟。")
        
        # 3. [Subscription] 自动搜寻补全任务
        if config.get("sub_auto_fill", False):
            fill_interval = int(config.get("sub_fill_interval", 12))
            MonitorManager._scheduler.add_job(
                MonitorManager._auto_fill_subscriptions,
                'interval',
                hours=fill_interval,
                id="sub_auto_fill_job",
                replace_existing=True
            )
            logger.info(f"[Subscription] 已调度自动搜寻补全，间隔 {fill_interval} 小时。")
        
        # 4. [Rule] 自动规则同步
        if config.get("rule_auto_update", False):
            rule_interval = int(config.get("rule_update_interval", 24))
            MonitorManager._scheduler.add_job(
                MonitorManager._auto_sync_rules,
                'interval',
                hours=rule_interval,
                id="rule_auto_sync_job",
                replace_existing=True
            )
            logger.info(f"[Rule] 已调度规则自动同步，间隔 {rule_interval} 小时。")
        
        # 5. [Stalled Monitor] 下载超时检查
        stalled_interval = int(config.get("stalled_monitor_interval", 30))
        if stalled_interval > 0:
            MonitorManager._scheduler.add_job(
                check_stalled_downloads,
                'interval',
                minutes=stalled_interval,
                id="stalled_monitor_job",
                replace_existing=True
            )
            logger.info(f"[Monitor] 已启动死种清理监控，巡检间隔 {stalled_interval} 分钟。")
        else:
            logger.info("[Monitor] 死种清理已禁用 (间隔设为 0)。")

        # 6. [Health Check] 掉盘与失效自动检测
        health_enabled = config.get("health_check_enabled", True)
        health_interval = int(config.get("health_check_interval", 30))
        
        if health_enabled and health_interval > 0:
            MonitorManager._scheduler.add_job(
                MonitorManager._auto_health_check,
                'interval',
                minutes=health_interval,
                id="auto_health_check_job",
                replace_existing=True
            )
            logger.info(f"[Monitor] 已启动健康检查自动巡检，间隔 {health_interval} 分钟。")
        else:
            logger.info("[Monitor] 健康检查自动巡检已禁用。")

        # 7. [Calendar] 每日播报任务
        calendar_push = config.get("calendar_daily_push", False)
        if calendar_push:
            push_time = config.get("calendar_push_time", "09:00")
            try:
                hour, minute = map(int, push_time.split(':'))
                MonitorManager._scheduler.add_job(
                    MonitorManager._calendar_daily_push,
                    'cron',
                    hour=hour,
                    minute=minute,
                    id="calendar_daily_push_job",
                    replace_existing=True
                )
                logger.info(f"[Calendar] 已开启每日播报，推送时间: {push_time}")
            except Exception as e:
                logger.error(f"[Calendar] 每日播报设置解析失败: {e}")
        
        # 8. [Subscription Notifier] 订阅智能提醒
        sub_notify_enabled = config.get("subscription_notify_enabled", True)
        if sub_notify_enabled:
            sub_notify_interval = int(config.get("subscription_notify_interval", 60))
            MonitorManager._scheduler.add_job(
                MonitorManager._subscription_notifier_check,
                'interval',
                minutes=sub_notify_interval,
                id="subscription_notifier_job",
                replace_existing=True
            )
            logger.info(f"[订阅提醒] 已启动订阅更新检查，间隔 {sub_notify_interval} 分钟")
            
            # 每日摘要
            if config.get("subscription_daily_summary", False):
                summary_time = config.get("subscription_summary_time", "08:00")
                try:
                    hour, minute = map(int, summary_time.split(':'))
                    MonitorManager._scheduler.add_job(
                        MonitorManager._subscription_daily_summary,
                        'cron',
                        hour=hour,
                        minute=minute,
                        id="subscription_daily_summary_job",
                        replace_existing=True
                    )
                    logger.info(f"[订阅提醒] 已开启每日摘要，推送时间: {summary_time}")
                except Exception as e:
                    logger.error(f"[订阅提醒] 每日摘要设置解析失败: {e}")
        
        # 9. [Telegram Bot] 智能体对话
        tg_bot_enabled = config.get("telegram_bot_enabled", False)
        if tg_bot_enabled:
            try:
                from telegram_bot import start_telegram_bot
                if MonitorManager._loop:
                    asyncio.create_task(start_telegram_bot())
                    logger.info("[TG Bot] 智能体对话已启动")
            except Exception as e:
                logger.error(f"[TG Bot] 启动失败: {e}")
        
        # 10. [BGM-TMDB Mapping] 每7天自动同步映射表
        bgm_mapping_enabled = config.get("bgm_mapping_auto_sync", True)
        if bgm_mapping_enabled:
            MonitorManager._scheduler.add_job(
                MonitorManager._auto_sync_bgm_mapping,
                'interval',
                days=7,
                id="bgm_mapping_sync_job",
                replace_existing=True
            )
            logger.info("[BangumiData] 已启动自动同步任务，间隔 7 天")
            
            asyncio.create_task(MonitorManager._auto_sync_bgm_mapping())
        
        # 11. [Discover Cache] 每日预热发现页第一页缓存 (Bangumi + TMDB)
        MonitorManager._scheduler.add_job(
            MonitorManager._warmup_discover_cache,
            'cron',
            hour=4,
            minute=0,
            id="discover_cache_warmup_job",
            replace_existing=True
        )
        logger.info("[Discover] 已调度每日发现页第一页缓存预热 (04:00)")

    @staticmethod
    async def _warmup_discover_cache():
        """预热发现页第一页缓存 (Bangumi + TMDB)"""
        # Bangumi
        try:
            from recognition.data_provider.bangumi.client import BangumiProvider
            await BangumiProvider.discover({"page": 1, "sort_by": "popularity.desc"})
            await BangumiProvider.discover({"page": 1, "sort_by": "match"})
            await BangumiProvider.get_calendar()
            logger.info("[Bangumi] 发现页 + 日历缓存预热完成")
        except Exception as e:
            logger.warning(f"[Bangumi] 发现页缓存预热失败: {e}")
        
        # TMDB
        try:
            from recognition.data_provider.tmdb.client import TMDBProvider
            config = ConfigManager.get_config()
            tmdb_key = config.get("tmdb_api_key")
            if tmdb_key:
                tmdb = TMDBProvider(tmdb_key)
                await tmdb.discover("tv", {"page": 1, "sort_by": "popularity.desc"})
                await tmdb.discover("movie", {"page": 1, "sort_by": "popularity.desc"})
                logger.info("[TMDB] 发现页缓存预热完成")
        except Exception as e:
            logger.warning(f"[TMDB] 发现页缓存预热失败: {e}")

    @staticmethod
    async def _auto_sync_bgm_mapping():
        """自动同步 BangumiData 条目表"""
        task_id = f"bgm_mapping_{uuid.uuid4().hex[:8]}"
        try:
            await start_task(task_id, "BangumiData同步", "BangumiData条目表自动同步")
            
            from recognition.data_provider.bangumi.service import bangumi_data_service
            
            should, reason = await bangumi_data_service.should_sync()
            if not should:
                await log_task(task_id, f"⏭️ 跳过同步: {reason}")
                stats = await bangumi_data_service.get_stats()
                await log_task(task_id, f"📊 当前条目表: {stats.get('total', 0)} 条记录")
                await finish_task(task_id, "completed", 0, {"skipped": True})
                logger.info(f"[BangumiData] {reason}")
                return
            
            await log_task(task_id, "🚀 开始执行 BangumiData 条目表自动同步")
            await log_task(task_id, f"📝 原因: {reason}")
            await log_task(task_id, "📡 数据源: https://unpkg.com/bangumi-data@0.3/dist/data.json")
            
            result = await bangumi_data_service.sync_from_remote(force=True)
            
            if result.get("success"):
                count = result.get("count", 0)
                await log_task(task_id, f"✅ 同步成功: 共更新 {count} 条条目记录")
                
                stats = await bangumi_data_service.get_stats()
                await log_task(task_id, f"📊 条目表统计:")
                await log_task(task_id, f"   ┗ 总记录数: {stats.get('total', 0)}")
                for media_type, cnt in stats.get("by_type", {}).items():
                    await log_task(task_id, f"   ┗ {media_type}: {cnt} 条")
                
                await log_task(task_id, "🏁 BangumiData同步完成")
                await finish_task(task_id, "completed", count, stats)
                
                from logger import log_audit
                log_audit("BangumiData", "自动同步", f"成功更新 {count} 条条目记录")
            else:
                msg = result.get("message", "未知错误")
                await log_task(task_id, f"❌ 同步失败: {msg}", "ERROR")
                await finish_task(task_id, "error", 0)
                logger.error(f"[BangumiData] 自动同步失败: {msg}")
        except Exception as e:
            await log_task(task_id, f"❌ 同步异常: {str(e)}", "ERROR")
            await finish_task(task_id, "error", 0)
            logger.error(f"[BangumiData] 自动同步异常: {e}")

    @staticmethod
    async def _calendar_daily_push():
        """执行每日日历播报，返回: str)"""
        try:
            from database import db
            from models import CalendarSubject
            from sqlmodel import select
            from notification import NotificationManager
            from datetime import datetime

            today_str = datetime.now().strftime("%Y-%m-%d")
            
            async with db.session_scope():
                # 方案：查询所有条目，通过 episodes_cache 判定今天是否有更新
                stmt = select(CalendarSubject)
                all_subs = await db.all(CalendarSubject, stmt)
                
                airing_today = []
                for sub in all_subs:
                    episodes = sub.episodes_cache or []
                    if any(ep.get("air_date") == today_str for ep in episodes):
                        airing_today.append(sub.model_dump())
                
                success, msg = await NotificationManager.push_daily_calendar_summary(airing_today)
                
                if success:
                    if airing_today:
                        logger.info(f"[Calendar] 每日播报发送成功，今日共有 {len(airing_today)} 部作品更新。")
                    else:
                        logger.info(f"[Calendar] 每日播报已发送（今日无更新）。")
                    return True, f"今日共有 {len(airing_today)} 部作品更新"
                else:
                    logger.error(f"[Calendar] 每日播报发送失败: {msg}")
                    return False, msg
        except Exception as e:
            logger.error(f"[Calendar] 每日播报执行失败: {e}")
            return False, str(e)

    @staticmethod
    async def _auto_sync_rules():
        task_id = f"rule_sync_{uuid.uuid4().hex[:8]}"
        try:
            await start_task(task_id, "规则同步", "规则自动同步")
            await log_task(task_id, "🚀 开始执行规则自动同步")
            from config_manager import ConfigManager
            cache_data = await ConfigManager.refresh_remote_rules()
            
            total = sum(len(v) for v in cache_data.values())
            await log_task(task_id, f"✅ 同步成功: 共获取 {total} 条规则")
            await log_task(task_id, f"  ┗ 📥 噪声词: {len(cache_data.get('noise', []))} 条")
            await log_task(task_id, f"  ┗ 📥 制作组: {len(cache_data.get('groups', []))} 条")
            await log_task(task_id, f"  ┗ 📥 渲染词: {len(cache_data.get('render', []))} 条")
            await log_task(task_id, f"  ┗ 📥 特权规则: {len(cache_data.get('privileged', []))} 条")
            
            await log_task(task_id, f"🏁 规则同步完成")
            
            # 构建统计信息
            stats = {
                "total": total,
                "noise": len(cache_data.get('noise', [])),
                "groups": len(cache_data.get('groups', [])),
                "render": len(cache_data.get('render', [])),
                "privileged": len(cache_data.get('privileged', []))
            }
            
            await finish_task(task_id, "completed", total, stats)
        except Exception as e:
            await log_task(task_id, f"❌ 同步失败: {str(e)}", "ERROR")
            await finish_task(task_id, "error", 0)
            logger.error(f"[Monitor] Auto sync rules failed: {e}")

    @staticmethod
    async def _daily_cleanup():
        try:
            from logger import log_audit
            deleted = await MetaCacheManager.clear_system_logs(30)
            if deleted > 0:
                log_audit("维护", "自动清理", f"已自动清理 {deleted} 条 30 天前的系统日志。")
        except Exception as e:
            logger.error(f"[Maintenance] Log cleanup failed: {e}")
    
    @staticmethod
    async def _subscription_notifier_check():
        """订阅智能提醒检查"""
        try:
            from subscription_notifier import check_subscription_updates
            result = await check_subscription_updates()
            
            new_count = len(result.get("new_episodes", []))
            notify_count = result.get("notifications_sent", 0)
            
            if new_count > 0:
                logger.info(f"[订阅提醒] 发现 {new_count} 个新集，已发送 {notify_count} 条通知")
        except Exception as e:
            logger.error(f"[订阅提醒] 检查失败: {e}")
    
    @staticmethod
    async def _subscription_daily_summary():
        """订阅每日摘要"""
        try:
            from subscription_notifier import send_daily_anime_summary
            await send_daily_anime_summary()
        except Exception as e:
            logger.error(f"[订阅提醒] 每日摘要发送失败: {e}")

    @staticmethod
    async def _auto_fill_subscriptions():
        task_id = f"sub_fill_{uuid.uuid4().hex[:8]}"
        try:
            await start_task(task_id, "订阅补全", "自动搜寻补全")
            await log_task(task_id, "🚀 开始执行订阅自动搜寻补全")
            
            from rss_core.subscription_manager import SubscriptionManager
            subs = await SubscriptionManager.get_subscriptions(enabled_only=True)
            active_subs = [s for s in subs if getattr(s, 'auto_fill', True)]
            
            if not active_subs:
                await log_task(task_id, "⚠️ 没有需要自动补全的活跃订阅")
                await finish_task(task_id, "completed", 0)
                return

            await log_task(task_id, f"📋 共有 {len(active_subs)} 个订阅项目待检查")
            
            from routers.subscriptions import run_sub_fill_logic
            total_pushed = 0
            for sub in active_subs:
                try:
                    pushed = await run_sub_fill_logic(sub, logger_func=None, task_id=task_id)
                    if pushed > 0:
                        await log_task(task_id, f"  ✅ [{sub.title}]: 成功补全 {pushed} 集")
                    total_pushed += pushed
                except Exception as e:
                    await log_task(task_id, f"  ❌ [{sub.title}]: 处理失败 - {str(e)}", "ERROR")

            await log_task(task_id, f"🏁 订阅补全完成，累计推送 {total_pushed} 个项目")
            
            # 构建统计信息
            stats = {
                "total_pushed": total_pushed,
                "total_subs": len(active_subs)
            }
            
            await finish_task(task_id, "completed", total_pushed, stats)
        except Exception as e:
            await log_task(task_id, f"❌ 补全异常: {str(e)}", "ERROR")
            await finish_task(task_id, "error", 0)
            logger.error(f"[Monitor] Auto fill subscriptions failed: {e}")

    @staticmethod
    async def _auto_health_check():
        try:
            from routers.health import trigger_all_health_checks
            from fastapi import BackgroundTasks
            # 模拟 BackgroundTasks 执行
            bg = BackgroundTasks()
            from database import db
            async with db.session_scope() as session:
                await trigger_all_health_checks(bg, session)
            # 执行后台任务
            for task in bg.tasks:
                if asyncio.iscoroutinefunction(task.func):
                    await task.func(*task.args, **task.kwargs)
                else:
                    task.func(*task.args, **task.kwargs)
        except Exception as e:
            logger.error(f"[Monitor] Auto health check failed: {e}")

    @staticmethod
    def enqueue_file(task_id: str, file_path: str):
        """将文件推送到特定任务的异步处理队列中 (供外部 Webhook 调用)"""
        queue = MonitorManager._queues.get(task_id)
        if queue and MonitorManager._loop:
            # 使用 threadsafe 以防万一从非 asyncio 线程调用
            MonitorManager._loop.call_soon_threadsafe(queue.put_nowait, (file_path, None))
            return True
        return False

    @staticmethod
    async def get_services_status() -> Dict[str, Any]:
        """
        获取所有后台服务的运行状态
        返回: { services: [...], monitors: [...] }
        """
        from datetime import datetime
        config = ConfigManager.get_config()
        services = []
        monitors = []

        # 1. 获取调度任务状态
        if MonitorManager._scheduler:
            jobs = MonitorManager._scheduler.get_jobs()
            job_map = {job.id: job for job in jobs}

            # RSS 自动刷新
            rss_job = job_map.get("rss_refresh_job")
            services.append({
                "id": "rss_refresh",
                "name": "RSS 自动刷新",
                "type": "scheduler",
                "enabled": config.get("rss_auto_refresh", True),
                "running": rss_job is not None,
                "interval": f"{config.get('rss_refresh_interval', 15)} 分钟",
                "next_run": rss_job.next_run_time.isoformat() if rss_job and rss_job.next_run_time else None,
                "last_run": None,
                "description": "定时刷新所有 RSS 订阅源"
            })

            # 规则自动同步
            rule_job = job_map.get("rule_auto_sync_job")
            services.append({
                "id": "rule_sync",
                "name": "规则自动同步",
                "type": "scheduler",
                "enabled": config.get("rule_auto_update", False),
                "running": rule_job is not None,
                "interval": f"{config.get('rule_update_interval', 24)} 小时",
                "next_run": rule_job.next_run_time.isoformat() if rule_job and rule_job.next_run_time else None,
                "last_run": None,
                "description": "从远程仓库同步识别规则"
            })

            # 订阅自动补全
            sub_job = job_map.get("sub_auto_fill_job")
            services.append({
                "id": "sub_fill",
                "name": "订阅自动补全",
                "type": "scheduler",
                "enabled": config.get("sub_auto_fill", False),
                "running": sub_job is not None,
                "interval": f"{config.get('sub_fill_interval', 12)} 小时",
                "next_run": sub_job.next_run_time.isoformat() if sub_job and sub_job.next_run_time else None,
                "last_run": None,
                "description": "自动搜寻补全缺失的订阅集数"
            })

            # 死种清理
            stalled_job = job_map.get("stalled_monitor_job")
            stalled_interval = config.get("stalled_monitor_interval", 30)
            services.append({
                "id": "stalled_monitor",
                "name": "死种清理",
                "type": "scheduler",
                "enabled": stalled_interval > 0,
                "running": stalled_job is not None,
                "interval": f"{stalled_interval} 分钟" if stalled_interval > 0 else "已禁用",
                "next_run": stalled_job.next_run_time.isoformat() if stalled_job and stalled_job.next_run_time else None,
                "last_run": None,
                "description": "检测并清理超时的下载任务"
            })

            # 健康检查巡检
            health_job = job_map.get("auto_health_check_job")
            health_enabled = config.get("health_check_enabled", True)
            health_interval = config.get("health_check_interval", 30)
            services.append({
                "id": "health_check",
                "name": "健康检查巡检",
                "type": "scheduler",
                "enabled": health_enabled and health_interval > 0,
                "running": health_job is not None,
                "interval": f"{health_interval} 分钟" if health_interval > 0 else "已禁用",
                "next_run": health_job.next_run_time.isoformat() if health_job and health_job.next_run_time else None,
                "last_run": None,
                "description": "自动检测磁盘掉盘与服务状态"
            })

            # 每日日历播报
            calendar_job = job_map.get("calendar_daily_push_job")
            services.append({
                "id": "calendar_push",
                "name": "每日日历播报",
                "type": "scheduler",
                "enabled": config.get("calendar_daily_push", False),
                "running": calendar_job is not None,
                "interval": f"每日 {config.get('calendar_push_time', '09:00')}",
                "next_run": calendar_job.next_run_time.isoformat() if calendar_job and calendar_job.next_run_time else None,
                "last_run": None,
                "description": "每日定时推送今日更新的番剧"
            })
            
            # 订阅智能提醒
            sub_notify_job = job_map.get("subscription_notifier_job")
            services.append({
                "id": "subscription_notifier",
                "name": "订阅智能提醒",
                "type": "scheduler",
                "enabled": config.get("subscription_notify_enabled", True),
                "running": sub_notify_job is not None,
                "interval": f"每 {config.get('subscription_notify_interval', 60)} 分钟",
                "next_run": sub_notify_job.next_run_time.isoformat() if sub_notify_job and sub_notify_job.next_run_time else None,
                "last_run": None,
                "description": "检查订阅番剧新集播出并发送通知"
            })
            
            # 订阅每日摘要
            sub_summary_job = job_map.get("subscription_daily_summary_job")
            services.append({
                "id": "subscription_daily_summary",
                "name": "订阅每日摘要",
                "type": "scheduler",
                "enabled": config.get("subscription_daily_summary", False),
                "running": sub_summary_job is not None,
                "interval": f"每日 {config.get('subscription_summary_time', '08:00')}",
                "next_run": sub_summary_job.next_run_time.isoformat() if sub_summary_job and sub_summary_job.next_run_time else None,
                "last_run": None,
                "description": "每日推送订阅番剧播出摘要"
            })
            
            # Telegram Bot
            try:
                from telegram_bot import TelegramBot
                tg_bot = TelegramBot.get_instance()
                tg_running = tg_bot.is_running()
            except:
                tg_running = False
            
            services.append({
                "id": "telegram_bot",
                "name": "Telegram Bot 对话",
                "type": "thread",
                "enabled": config.get("telegram_bot_enabled", False),
                "running": tg_running,
                "interval": "长轮询",
                "next_run": None,
                "last_run": None,
                "description": "通过 Telegram 与智能体对话"
            })

            # 日志清理
            cleanup_job = job_map.get("daily_cleanup_job")
            services.append({
                "id": "daily_cleanup",
                "name": "日志自动清理",
                "type": "scheduler",
                "enabled": True,
                "running": cleanup_job is not None,
                "interval": "每日 03:00",
                "next_run": cleanup_job.next_run_time.isoformat() if cleanup_job and cleanup_job.next_run_time else None,
                "last_run": None,
                "description": "自动清理 30 天前的系统日志"
            })

            # BangumiData 同步
            bgm_job = job_map.get("bgm_mapping_sync_job")
            bgm_enabled = config.get("bgm_mapping_auto_sync", True)
            bgm_last_run = None
            bgm_interval_str = "7 天" if bgm_enabled else "已禁用"
            try:
                from recognition.data_provider.bangumi.service import bangumi_data_service
                bgm_status = await bangumi_data_service.get_sync_status()
                bgm_last_run = bgm_status.get("last_sync_time")
                bgm_count = bgm_status.get("mapping_count")
            except Exception as e:
                logger.warning(f"[Monitor] 获取BangumiData同步状态失败: {e}")
                bgm_count = None
            bgm_desc = "同步 BangumiData 条目表用于番剧识别"
            if bgm_count is not None:
                bgm_desc += f" (当前 {bgm_count} 条)"
            services.append({
                "id": "bgm_mapping_sync",
                "name": "BangumiData 同步",
                "type": "scheduler",
                "enabled": bgm_enabled,
                "running": bgm_job is not None,
                "interval": bgm_interval_str,
                "next_run": bgm_job.next_run_time.isoformat() if bgm_job and bgm_job.next_run_time else None,
                "last_run": bgm_last_run,
                "description": bgm_desc
            })

        # 2. CD2 传输监控
        cd2_running = CD2TransferMonitor._instance is not None and CD2TransferMonitor._thread is not None and CD2TransferMonitor._thread.is_alive()
        cd2_config = None
        clients = config.get("download_clients", [])
        for c in clients:
            if c.get("type") == "cd2":
                cd2_config = c
                break
        cd2_monitor_enabled = cd2_config.get("monitor_enabled", None) if cd2_config else None
        if cd2_monitor_enabled is None:
            cd2_monitor_enabled = config.get("enable_cd2_monitor", True)
        services.append({
            "id": "cd2_monitor",
            "name": "CD2 传输监控",
            "type": "thread",
            "enabled": cd2_config is not None and cd2_monitor_enabled,
            "running": cd2_running,
            "interval": f"{cd2_config.get('monitor_interval', 5)} 秒" if cd2_config else "-",
            "next_run": None,
            "last_run": None,
            "description": "监控 CD2 上传/下载任务完成并触发联动"
        })

        # 3. Emby 索引同步 (后台 asyncio 循环，非调度器任务)
        emby_configured = bool(config.get('emby_url') and config.get('emby_api_key'))
        emby_index_status = {}
        if emby_configured:
            try:
                from emby_index_service import get_emby_index_status
                emby_index_status = get_emby_index_status()
            except Exception as e:
                logger.warning(f"[Monitor] 获取Emby索引同步状态失败: {e}")
        emby_last_run = emby_index_status.get("last_sync_time")
        emby_next_run = emby_index_status.get("next_sync_time")
        emby_count = emby_index_status.get("last_sync_count")
        emby_desc = "同步 Emby 库索引以加速 TMDB ID 查询"
        if emby_count is not None and emby_count >= 0:
            emby_desc += f" (当前 {emby_count} 条)"
        elif emby_count == -1:
            emby_desc += " (上次同步失败)"
        services.append({
            "id": "emby_index_sync",
            "name": "Emby 索引同步",
            "type": "thread",
            "enabled": emby_configured,
            "running": emby_index_status.get("loop_running", False),
            "interval": "24 小时" if emby_configured else "未配置",
            "next_run": emby_next_run,
            "last_run": emby_last_run,
            "description": emby_desc
        })

        # 4. 文件监控任务 (整理任务)
        organize_tasks = config.get("organize_tasks", [])
        for task in organize_tasks:
            incremental_enabled = task.get("incremental_enabled", False)
            scheduler_enabled = task.get("scheduler_enabled", False)
            old_mode = task.get("monitor_mode", "none")
            if old_mode in ["realtime", "polling"]:
                incremental_enabled = True
            elif old_mode == "scheduled":
                scheduler_enabled = True

            source_dir = task.get("source_dir") or task.get("source_path")
            modes = []
            if incremental_enabled:
                modes.append("实时监控")
            if scheduler_enabled:
                modes.append("定时扫描")
            mode_str = " + ".join(modes) if modes else "未启用"

            monitors.append({
                "id": task.get("id"),
                "name": task.get("name", "未命名"),
                "type": "organize",
                "enabled": incremental_enabled or scheduler_enabled,
                "mode": mode_str,
                "running": task.get("id") in MonitorManager._queues,
                "source_dir": source_dir,
                "target_dir": task.get("target_dir") or task.get("target_path"),
                "queue_size": MonitorManager._queues.get(task.get("id"), asyncio.Queue()).qsize() if task.get("id") in MonitorManager._queues else 0,
                "check_emby_exists": task.get("check_emby_exists", False),
                "calculate_hash": task.get("calculate_hash", False)
            })

        # 4. STRM 监控任务
        strm_tasks = config.get("strm_tasks", [])
        for task in strm_tasks:
            incremental_enabled = task.get("incremental_enabled", False)
            scheduler_enabled = task.get("scheduler_enabled", False)
            old_mode = task.get("monitor_mode", "none")
            if old_mode in ["realtime", "polling"]:
                incremental_enabled = True
            elif old_mode == "scheduled":
                scheduler_enabled = True

            source_dir = task.get("source_dir") or task.get("source_path")
            modes = []
            if incremental_enabled:
                modes.append("实时监控")
            if scheduler_enabled:
                modes.append("定时扫描")
            mode_str = " + ".join(modes) if modes else "未启用"

            monitors.append({
                "id": task.get("id"),
                "name": task.get("name", "未命名"),
                "type": "strm",
                "enabled": incremental_enabled or scheduler_enabled,
                "mode": mode_str,
                "running": task.get("id") in MonitorManager._queues,
                "source_dir": source_dir,
                "target_dir": task.get("target_dir") or task.get("target_path"),
                "queue_size": MonitorManager._queues.get(task.get("id"), asyncio.Queue()).qsize() if task.get("id") in MonitorManager._queues else 0,
                "webhook_enabled": task.get("webhook_enabled", False)
            })

        # 获取规则统计
        cached_rules = ConfigManager.get_cached_rules()
        
        # 获取内置制作组数量
        from recognition_engine.builtin_group_loader import BuiltinGroupLoader
        builtin_groups = BuiltinGroupLoader.get_builtin_groups()
        
        rules_stats = {
            "custom_noise": {
                "local": len([r for r in config.get("custom_noise_words", []) if r]),
                "remote": len([r for r in cached_rules.get("noise", []) if r])
            },
            "custom_groups": {
                "local": len([r for r in config.get("custom_release_groups", []) if r]),
                "remote": len([r for r in cached_rules.get("groups", []) if r]),
                "builtin": len(builtin_groups)
            },
            "custom_render": {
                "local": len([r for r in config.get("custom_render_words", []) if r]),
                "remote": len([r for r in cached_rules.get("render", []) if r])
            },
            "privileged": {
                "local": len([r for r in config.get("custom_privileged_rules", []) if r]),
                "remote": len([r for r in cached_rules.get("privileged", []) if r])
            }
        }

        return {
            "services": services,
            "monitors": monitors,
            "observers_count": len(MonitorManager._observers),
            "workers_count": len(MonitorManager._workers),
            "queues_count": len(MonitorManager._queues),
            "rules": rules_stats
        }

    @staticmethod
    def get_queue_items(task_id: str) -> List[str]:
        """
        获取指定任务队列中的文件列表。
        注意：这会临时从队列中取出所有项目，然后再放回。
        """
        queue = MonitorManager._queues.get(task_id)
        if not queue:
            return []
        
        items = []
        temp_items = []
        
        try:
            while True:
                item = queue.get_nowait()
                temp_items.append(item)
                items.append(item)
                queue.task_done()
        except asyncio.QueueEmpty:
            pass
        
        for item in temp_items:
            queue.put_nowait(item)
        
        return [i[0] if isinstance(i, tuple) else i for i in items]

    @staticmethod
    async def reload():
        from logger import log_audit
        log_audit("系统", "监控重载", "正在重新加载所有监控任务...")
        # 重载配置时不建议清理掉正在排队执行的任务
        MonitorManager.stop_all(clear_tasks=False)
        MonitorManager.start_all()

    @staticmethod
    def stop_all(clear_tasks: bool = False):
        CD2TransferMonitor.stop()
        
        for obs in MonitorManager._observers:
            obs.stop()
            obs.join()
        MonitorManager._observers.clear()
        
        if clear_tasks:
            # 取消所有 Worker
            for w in MonitorManager._workers:
                w.cancel()
            MonitorManager._workers.clear()
            MonitorManager._queues.clear()
        
        if MonitorManager._scheduler:
             MonitorManager._scheduler.remove_all_jobs()
        
        logger.info("监控监听服务已停止" + (" (任务队列已清空)" if clear_tasks else ""))

    @staticmethod
    def start_all():
        # 1. 设置系统级任务
        MonitorManager._setup_system_jobs()

        # [New] 启动 CD2 传输监控
        try:
            CD2TransferMonitor.start()
        except Exception as e:
            logger.error(f"启动 CD2 监控失败: {e}")

        # 2. 设置文件监控任务 (由于涉及文件系统同步检查，我们将其放入后台任务，防止阻塞主线程)
        MonitorManager._loop.create_task(MonitorManager._async_start_all())

    @staticmethod
    async def _async_start_all():
        from logger import log_audit
        config = ConfigManager.get_config()
        organize_tasks = config.get("organize_tasks", [])
        strm_tasks = config.get("strm_tasks", [])
        
        all_tasks = []
        for t in organize_tasks:
            t["is_strm"] = False
            all_tasks.append(t)
        for t in strm_tasks:
            t["is_strm"] = True
            all_tasks.append(t)
        
        started_count = 0
        for task in all_tasks:
            # --- 兼容逻辑与新配置解析 ---
            incremental_enabled = task.get("incremental_enabled", False)
            incremental_mode = task.get("incremental_mode", "realtime")
            scheduler_enabled = task.get("scheduler_enabled", False)
            
            # 兼容旧版本数据
            old_mode = task.get("monitor_mode", "none")
            if old_mode != "none":
                if old_mode in ["realtime", "polling"]:
                    incremental_enabled = True
                    incremental_mode = old_mode
                elif old_mode == "scheduled":
                    scheduler_enabled = True

            if not incremental_enabled and not scheduler_enabled:
                continue
            
            source_dir = task.get("source_dir") or task.get("source_path")
            if not source_dir: continue

            # 初始化/复用 Worker 队列 (防止 reload 时冲掉旧任务)
            task_id = task.get("id")
            if task_id not in MonitorManager._queues:
                queue = asyncio.Queue()
                MonitorManager._queues[task_id] = queue
                
                # 只有新创建的队列才需要启动新 Worker
                worker_task = MonitorManager._loop.create_task(MonitorManager._task_worker(task, queue))
                MonitorManager._workers.append(worker_task)
            
            queue = MonitorManager._queues[task_id]

            # 启动实时监控
            if incremental_enabled:
                # [关键改进] 将 watchdog 的启动也扔进线程池，因为它在慢速挂载点上会阻塞很久
                MonitorManager._loop.run_in_executor(None, MonitorManager._start_watchdog_sync, task, queue, incremental_mode == "polling")

            # 启动定时扫描
            if scheduler_enabled:
                interval = int(task.get("scheduler_interval") or task.get("monitor_interval") or 3600)
                MonitorManager._start_scheduler(task, interval)
            
            started_count += 1

        log_audit("系统", "监控启动", f"后台任务监听器已重载 (队列保留, 共 {started_count} 个任务)")

    @staticmethod
    def _start_watchdog_sync(task: Dict[str, Any], queue: asyncio.Queue, use_polling: bool):
        """同步版本的启动逻辑，供线程池调用"""
        try:
            MonitorManager._start_watchdog(task, queue, use_polling)
        except Exception as e:
            logger.warning(f"后台初始化任务 '{task.get('name')}' 失败 (可能是路径不可达): {e}")

    @staticmethod
    async def _task_worker(task: Dict[str, Any], queue: asyncio.Queue):
        task_id = task.get("id")
        is_strm = task.get("is_strm", False)

        while True:
            try:
                item = await queue.get()
                batch_stats = None
                if isinstance(item, tuple):
                    if len(item) == 3:
                        file_path, batch_task_id, batch_stats = item
                    else:
                        file_path, batch_task_id = item
                else:
                    file_path, batch_task_id = item, None
                
                current_task = MonitorManager._get_task_config(task_id, is_strm)
                if not current_task:
                    logger.warning(f"[实时监控] 任务配置已删除: {task_id}")
                    queue.task_done()
                    continue
                
                task_name = current_task.get("name", "未命名")
                
                skip_stability_check = False
                
                ignore_history = current_task.get("ignore_history", False)
                if not ignore_history:
                    from database import db
                    from models import OrganizeHistory
                    from sqlmodel import select, and_
                    async with db.session_scope():
                        stmt = select(OrganizeHistory).where(
                            and_(
                                OrganizeHistory.source_path == file_path,
                                OrganizeHistory.status.in_(["success", "skipped"])
                            )
                        )
                        existing = await db.first(OrganizeHistory, stmt)
                        if existing:
                            skip_stability_check = True
                
                ignore_file_regex = current_task.get("ignore_file_regex", [])
                if not skip_stability_check and ignore_file_regex and Organizer._is_regex_match(os.path.basename(file_path), ignore_file_regex):
                    skip_stability_check = True
                
                if not skip_stability_check:
                    is_stable = await StabilityChecker.wait_for_stability(file_path)
                    if not is_stable:
                        logger.debug(f"[实时监控] 文件不稳定或已消失: {os.path.basename(file_path)}")
                        queue.task_done()
                        continue

                should_rate_limit = True
                mon_task_id = batch_task_id
                try:
                    if is_strm:
                        logger.info(f"✨ [实时监控] STRM处理: {os.path.basename(file_path)}")
                        if not mon_task_id:
                            try:
                                from task_history import start_task as _start_task, log_task as _log_task
                                import uuid as _uuid
                                mon_task_id = f"strm_mon_{_uuid.uuid4().hex[:12]}"
                                await _start_task(mon_task_id, "STRM", f"[实时监控] {os.path.basename(file_path)}")
                                await _log_task(mon_task_id, f"📄 处理文件: {file_path}")
                            except Exception:
                                mon_task_id = None
                        else:
                            try:
                                from task_history import log_task as _log_task
                                await _log_task(mon_task_id, f"📄 处理: {os.path.basename(file_path)}")
                            except Exception:
                                pass
                        res = await StrmProcessor.process_single_file(file_path, current_task)
                        status = res.get("status", "unknown") if isinstance(res, dict) else "error"
                        message = res.get("message", "") if isinstance(res, dict) else str(res)
                        if status == "success":
                            logger.info(f"✨ [实时监控] STRM完成: {os.path.basename(file_path)}")
                            if mon_task_id:
                                try:
                                    from task_history import log_task as _log_task
                                    await _log_task(mon_task_id, f"✅ 成功: {os.path.basename(file_path)} ({message})")
                                except Exception:
                                    pass
                        elif status == "skipped":
                            logger.info(f"✨ [实时监控] STRM跳过: {os.path.basename(file_path)}")
                            if mon_task_id:
                                try:
                                    from task_history import log_task as _log_task
                                    await _log_task(mon_task_id, f"⏭️ 跳过: {os.path.basename(file_path)} ({message})")
                                except Exception:
                                    pass
                        else:
                            logger.error(f"✨ [实时监控] STRM失败: {os.path.basename(file_path)} ({message})")
                            if mon_task_id:
                                try:
                                    from task_history import log_task as _log_task
                                    await _log_task(mon_task_id, f"❌ 失败: {os.path.basename(file_path)} ({message})", "ERROR")
                                except Exception:
                                    pass
                        if not batch_task_id and mon_task_id:
                            try:
                                from task_history import finish_task as _finish_task
                                await _finish_task(mon_task_id, "error" if status == "error" else "completed")
                            except Exception:
                                pass
                        if batch_stats:
                            if status == "success":
                                batch_stats["success"] += 1
                            elif status == "skipped":
                                batch_stats["skipped"] += 1
                            else:
                                batch_stats["error"] += 1
                    else:
                        logger.debug(f"[实时监控] 整理: {os.path.basename(file_path)}")
                        if not mon_task_id:
                            try:
                                from task_history import start_task as _start_task
                                import uuid as _uuid
                                mon_task_id = f"mon_{_uuid.uuid4().hex[:12]}"
                                await _start_task(mon_task_id, "整理", f"[实时监控] {os.path.basename(file_path)}")
                            except Exception:
                                mon_task_id = None
                        results = await Organizer.organize_video_file(file_path, current_task, dry_run=False, task_id=mon_task_id)
                        has_error = False
                        for res in results:
                            if res.get("type") == "skip":
                                skip_type = res.get("skip_type")
                                skip_rate_limit = current_task.get("skip_rate_limit", False)
                                skip_rate_limit_types = current_task.get("skip_rate_limit_types", [])
                                logger.debug(f"skip_type={skip_type}, enabled={skip_rate_limit}, types={skip_rate_limit_types}")
                                if skip_rate_limit and skip_type and skip_type in skip_rate_limit_types:
                                    should_rate_limit = False
                                    logger.debug(f"命中规则: {skip_type}，跳过限流等待")
                            elif res.get("type") == "item" and res.get("status") == "error":
                                has_error = True
                        if not batch_task_id and mon_task_id:
                            try:
                                from task_history import finish_task as _finish_task
                                await _finish_task(mon_task_id, "error" if has_error else "completed")
                            except Exception:
                                pass
                        if batch_stats:
                            for res in results:
                                if res.get("type") == "skip":
                                    batch_stats["skipped"] += 1
                                elif res.get("type") == "item":
                                    if res.get("status") == "error":
                                        batch_stats["error"] += 1
                                    else:
                                        batch_stats["success"] += 1
                except Exception as e:
                    import traceback
                    logger.error(f"✨ [实时监控] 处理错误: {str(e)}")
                    logger.debug(traceback.format_exc())
                    if mon_task_id and not batch_task_id:
                        try:
                            from task_history import log_task as _log_task, finish_task as _finish_task
                            await _log_task(mon_task_id, f"❌ 处理错误: {str(e)}", "ERROR")
                            await _finish_task(mon_task_id, "error")
                        except Exception:
                            pass
                    if batch_stats:
                        batch_stats["error"] += 1
                
                queue.task_done()
                
                if should_rate_limit:
                    interval = float(current_task.get("process_interval", 0))
                    if interval > 0:
                        await asyncio.sleep(interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                await asyncio.sleep(1)

    @staticmethod
    def _start_watchdog(task: Dict[str, Any], queue: asyncio.Queue, use_polling: bool):
        # 修改 OrganizerEventHandler 使其只处理关联的那个 queue 和 task
        handler = OrganizerEventHandler([task], MonitorManager._loop, {task.get("id"): queue})
        
        if use_polling:
            interval = int(task.get("monitor_interval", 10))
            observer = PollingObserver(timeout=interval)
        else:
            observer = Observer()
        
        path = task.get("source_dir") or task.get("source_path")
        if not path: return

        try:
            observer.schedule(handler, path, recursive=True)
            observer.start()
            MonitorManager._observers.append(observer)
        except Exception as e:
            # 捕获目录不存在或无权限的情况
            logger.error(f"Watchdog 无法监听目录 {path}: {e}")
            raise

    @staticmethod
    def _start_scheduler(task: Dict[str, Any], interval_seconds: int):
        task_id = task.get("id")
        is_strm = task.get("is_strm", False)
        MonitorManager._scheduler.add_job(
            MonitorManager._scheduled_scan_job,
            'interval',
            seconds=interval_seconds,
            args=[task_id, is_strm]
        )

    @staticmethod
    async def _scheduled_scan_job(task_id: str, is_strm: bool = False):
        current_task = MonitorManager._get_task_config(task_id, is_strm)
        if not current_task:
            logger.warning(f"[定时扫描] 任务配置已删除: {task_id}")
            return
            
        task_name = current_task.get("name", "未命名")
        source_dir = current_task.get("source_dir") or current_task.get("source_path")
        if not source_dir or not os.path.exists(source_dir): return
        
        queue = MonitorManager._queues.get(task_id)
        if not queue: return

        def _scan():
            found_files = []
            ignore_file_regex = current_task.get("ignore_file_regex", [])
            for root, dirs, files in os.walk(source_dir):
                if current_task.get("ignore_dir_regex") and Organizer._is_regex_match(os.path.basename(root), current_task.get("ignore_dir_regex")):
                    continue

                for f in files:
                    f_path = os.path.join(root, f)
                    if ignore_file_regex and Organizer._is_regex_match(f, ignore_file_regex): continue
                    if StabilityChecker.is_temp_file(f): continue
                    
                    ext = os.path.splitext(f)[1].lower()
                    if ext in Organizer.VIDEO_EXTS:
                        found_files.append(f_path)
            return found_files

        files_to_process = await MonitorManager._loop.run_in_executor(None, _scan)
        
        if files_to_process:
            logger.info(f"✨ [定时扫描] 开始任务: {task_name}")
            scan_task_id = None
            stats = {"success": 0, "skipped": 0, "error": 0}
            try:
                from task_history import start_task as _start_task, log_task as _log_task
                import uuid as _uuid
                scan_task_id = f"scan_{_uuid.uuid4().hex[:12]}"
                module = "STRM" if is_strm else "整理"
                await _start_task(scan_task_id, module, f"[定时扫描] {task_name}")
                await _log_task(scan_task_id, f"🚀 开始定时扫描: {task_name}")
                await _log_task(scan_task_id, f"📁 源: {source_dir}")
                target_dir = current_task.get("target_dir") or current_task.get("target_path")
                if target_dir:
                    await _log_task(scan_task_id, f"📁 目标: {target_dir}")
                if not is_strm:
                    action_type = current_task.get("action_type", "move")
                    action_label = {"move": "移动", "copy": "复制", "cd2_move": "CD2移动", "cd2_copy": "CD2复制", "hash_only": "仅记录哈希"}.get(action_type, action_type)
                    await _log_task(scan_task_id, f"🔧 模式: 正式执行 ({action_label})")
                else:
                    sync_mode = current_task.get("sync_mode", "local")
                    sync_label = {"local": "本地", "cd2_api": "CD2 API", "webdav": "WebDAV"}.get(sync_mode, sync_mode)
                    await _log_task(scan_task_id, f"🔧 模式: {sync_label}")
                await _log_task(scan_task_id, f"📋 发现 {len(files_to_process)} 个文件")
                await _log_task(scan_task_id, "──────────────────")
            except Exception:
                scan_task_id = None
            
            for f_path in files_to_process:
                await queue.put((f_path, scan_task_id, stats))
            
            if scan_task_id:
                await queue.join()
                try:
                    from task_history import log_task as _log_task, finish_task as _finish_task
                    await _log_task(scan_task_id, "──────────────────")
                    await _log_task(scan_task_id, f"🏁 定时扫描完成 - 成功 {stats['success']} | 跳过 {stats['skipped']} | 失败 {stats['error']}")
                    await _finish_task(scan_task_id, "completed", stats['success'], stats)
                except Exception:
                    pass
                logger.info(f"✨ [定时扫描] 完成: {task_name} - 成功 {stats['success']} | 跳过 {stats['skipped']} | 失败 {stats['error']}")
        else:
            logger.debug(f"[定时扫描] {task_name}: 无新文件")