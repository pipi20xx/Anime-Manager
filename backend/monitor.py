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
        from logger import log_audit

        # 获取基础信息
        abs_path = os.path.abspath(file_path)
        filename = os.path.basename(file_path)
        now = time.time()
        
        # 1. 防抖逻辑校验
        if abs_path in self.recent_events:
            if now - self.recent_events[abs_path] < 5:
                # 静默跳过极短时间内的重复事件，不记录审计以免刷屏
                return
        self.recent_events[abs_path] = now

        # 清理过期的记录 (保留 60 秒以上的)
        if len(self.recent_events) > 100:
            self.recent_events = {p: t for p, t in self.recent_events.items() if now - t < 60}
        
        # 决策审计日志启动
        audit_logs = [f"🔍 监控触发 ({event_type}): {filename}"]
        
        # 2. 扩展名校验 (快速过滤)
        ext = os.path.splitext(file_path)[1].lower()
        from strm.constants import VIDEO_EXTENSIONS
        if ext not in Organizer.VIDEO_EXTS and ext not in VIDEO_EXTENSIONS:
            # 只有当非临时文件且非视频时，才完全忽略
            if not StabilityChecker.is_temp_file(file_path):
                return
            else:
                log_audit("监控", "忽略", f"跳过临时文件: {filename} (等待下载完成)", level="INFO", details=file_path)
                return

        # 3. 临时文件校验 (详细日志)
        if StabilityChecker.is_temp_file(file_path):
            log_audit("监控", "忽略", f"检测到下载中临时文件: {filename}，稍后待其更名后再处理。", level="INFO", details=file_path)
            return
            
        matched_any = False
        
        # 预加载客户端配置
        config = ConfigManager.get_config()
        all_clients = {c.get('id'): c for c in config.get("download_clients", [])}

        # 遍历所有任务
        for task in self.tasks:
            task_name = task.get("name", "未命名")
            source_dir = task.get("source_dir") or task.get("source_path")
            if not source_dir: continue
            
            # --- 智能路径匹配逻辑 ---
            local_match_root = source_dir
            if task.get("is_strm") and task.get("sync_mode") == "cd2_api":
                client_id = task.get("cd2_client_id")
                client_conf = all_clients.get(client_id, {})
                mapping_root = task.get("cd2_mapping_path") or client_conf.get("mount_path") or ""
                mapping_root = mapping_root.rstrip('/')
                source_dir_clean = '/' + source_dir.lstrip('/')
                local_match_root = mapping_root + source_dir_clean

            # 1. 路径前缀校验 (必须在任务源目录下)
            abs_source = os.path.abspath(local_match_root)
            if not abs_path.startswith(abs_source):
                continue
            
            # 2. 排除词校验
            exclude_keywords = task.get("exclude_keywords", [])
            is_excluded = False
            for kw in exclude_keywords:
                if kw and kw in file_path:
                    audit_logs.append(f"┣ 任务 [{task_name}]: 命中排除词 '{kw}' ❌")
                    is_excluded = True
                    break
            if is_excluded: continue

            # 3. 判定成功
            queue = self.queues.get(task.get("id"))
            if queue:
                audit_logs.append(f"┣ 任务 [{task_name}]: 判定通过，加入处理队列 ✅")
                self.loop.call_soon_threadsafe(queue.put_nowait, file_path)
                matched_any = True
            else:
                audit_logs.append(f"┣ 任务 [{task_name}]: 内部队列异常 ❌")

        if matched_any:
            audit_logs.append(f"┗ 结论: 文件已分发至后台 Worker。")
            log_audit("监控", "命中", "\n".join(audit_logs), details=file_path)
        else:
            # 只有当文件确实是视频且没有任何任务匹配时才记录日志
            if ext in Organizer.VIDEO_EXTS or ext in VIDEO_EXTENSIONS:
                audit_logs.append(f"┗ 结论: ⚠️ 路径不在任何监控任务的覆盖范围内。")
                log_audit("监控", "忽略", "\n".join(audit_logs), level="WARN", details=file_path)

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
            logger.info(f"[Monitor] 已启动下载超时熔断监控，巡检间隔 {stalled_interval} 分钟。")
        else:
            logger.info("[Monitor] 下载超时巡检已禁用 (间隔设为 0)。")

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

    @staticmethod
    async def _calendar_daily_push():
        """执行每日日历播报"""
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
                        # 转换成 dict 以便 notification 使用
                        airing_today.append(sub.model_dump())
                
                # 无论是否有番剧，都执行推送逻辑（NotificationManager 内部会处理空列表显示）
                await NotificationManager.push_daily_calendar_summary(airing_today)
                
                if airing_today:
                    logger.info(f"[Calendar] 每日播报发送成功，今日共有 {len(airing_today)} 部作品更新。")
                else:
                    logger.info(f"[Calendar] 每日播报已发送（今日无更新）。")
        except Exception as e:
            logger.error(f"[Calendar] 每日播报执行失败: {e}")

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
                    pushed = await run_sub_fill_logic(sub, logger_func=None)
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
            MonitorManager._loop.call_soon_threadsafe(queue.put_nowait, file_path)
            return True
        return False

    @staticmethod
    def get_services_status() -> Dict[str, Any]:
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

            # 下载超时熔断
            stalled_job = job_map.get("stalled_monitor_job")
            stalled_interval = config.get("stalled_monitor_interval", 30)
            services.append({
                "id": "stalled_monitor",
                "name": "下载超时熔断",
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

        # 3. 文件监控任务 (整理任务)
        organize_tasks = config.get("organize_tasks", [])
        for task in organize_tasks:
            incremental_enabled = task.get("incremental_enabled", False)
            scheduler_enabled = task.get("scheduler_enabled", False)
            old_mode = task.get("monitor_mode", "none")
            if old_mode in ["realtime", "polling"]:
                incremental_enabled = True
            elif old_mode == "scheduled":
                scheduler_enabled = True

            if incremental_enabled or scheduler_enabled:
                source_dir = task.get("source_dir") or task.get("source_path")
                monitors.append({
                    "id": task.get("id"),
                    "name": task.get("name", "未命名"),
                    "type": "organize",
                    "mode": "实时监控" if incremental_enabled else "定时扫描",
                    "running": task.get("id") in MonitorManager._queues,
                    "source_dir": source_dir,
                    "target_dir": task.get("target_dir") or task.get("target_path"),
                    "queue_size": MonitorManager._queues.get(task.get("id"), asyncio.Queue()).qsize() if task.get("id") in MonitorManager._queues else 0
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

            if incremental_enabled or scheduler_enabled:
                source_dir = task.get("source_dir") or task.get("source_path")
                monitors.append({
                    "id": task.get("id"),
                    "name": task.get("name", "未命名"),
                    "type": "strm",
                    "mode": "实时监控" if incremental_enabled else "定时扫描",
                    "running": task.get("id") in MonitorManager._queues,
                    "source_dir": source_dir,
                    "target_dir": task.get("target_dir") or task.get("target_path"),
                    "queue_size": MonitorManager._queues.get(task.get("id"), asyncio.Queue()).qsize() if task.get("id") in MonitorManager._queues else 0
                })

        return {
            "services": services,
            "monitors": monitors,
            "observers_count": len(MonitorManager._observers),
            "workers_count": len(MonitorManager._workers),
            "queues_count": len(MonitorManager._queues)
        }

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
                file_path = await queue.get()
                from logger import log_audit
                
                current_task = MonitorManager._get_task_config(task_id, is_strm)
                if not current_task:
                    log_audit("监控", "配置丢失", f"任务配置已删除: {task_id}", level="WARN")
                    queue.task_done()
                    continue
                
                task_name = current_task.get("name", "未命名")
                
                is_stable = await StabilityChecker.wait_for_stability(file_path)
                if not is_stable:
                    log_audit("监控", "任务跳过", f"文件不稳定或已消失: {os.path.basename(file_path)}", level="WARN")
                    queue.task_done()
                    continue

                try:
                    if is_strm:
                        log_audit("监控", "STRM任务", f"正在后台处理: {os.path.basename(file_path)}", details=task_name)
                        res = await StrmProcessor.process_single_file(file_path, current_task)
                    else:
                        log_audit("监控", "整理任务", f"正在后台处理: {os.path.basename(file_path)}", details=task_name)
                        await Organizer.organize_video_file(file_path, current_task, dry_run=False)
                except Exception as e:
                    log_audit("监控", "处理错误", f"后台执行失败: {str(e)}", level="ERROR", details=file_path)
                
                queue.task_done()
                
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
            logger.warning(f"[Scheduled] 任务配置已删除: {task_id}")
            return
            
        task_name = current_task.get("name", "未命名")
        logger.info(f"[Scheduled] Starting scan for {task_name}")
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
        
        for f_path in files_to_process:
            await queue.put(f_path)
        
        logger.info(f"[Scheduled] Found {len(files_to_process)} files pushed to queue for {task_name}")