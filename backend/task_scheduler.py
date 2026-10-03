"""
任务计划统一注册表。

所有系统级定时任务在这里登记元数据（名称、周期、开关配置键、手动触发入口），
任务计划页面 (GET /api/scheduler/jobs) 以此为唯一数据源，
与 monitor.py 中 APScheduler 的实际 job 状态做合并展示。

注意：
- run 入口均为协程，内部用惰性导入避免与 monitor.py 循环依赖。
- 带前缀 run_ 的包装函数会在执行前后写 task_history（任务中心可见），
  仅用于低频任务；高频轮询类（CD2 秒传队列 1 分钟、健康检查 30 分钟等）
  不写记录，避免 task_records 膨胀。
"""
import uuid
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, List, Optional

from config_manager import ConfigManager
from database import db
from task_history import start_task, log_task, finish_task


def _to_int(val: Any, default: int) -> int:
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


_DOW_NAMES = ["日", "一", "二", "三", "四", "五", "六"]


def describe_cron(cron: Optional[str]) -> str:
    """把 5 段 cron 表达式翻译成中文描述，无法识别时原样返回"""
    if not cron:
        return "-"
    fields = cron.split()
    if len(fields) != 5:
        return cron
    minute, hour, dom, month, dow = fields
    try:
        # 每分钟
        if minute == "*" and hour == "*":
            return "每分钟"
        # 间隔分钟：*/m * * * *
        if minute.startswith("*/") and hour == "*" and dom == "*" and month == "*" and dow == "*":
            m = int(minute[2:])
            if 60 % m == 0:
                return f"每 {m} 分钟"
            return cron
        # 间隔小时：0 */h * * *
        if hour.startswith("*/") and minute == "0" and dom == "*" and month == "*" and dow == "*":
            h = int(hour[2:])
            if 24 % h == 0:
                return f"每 {h} 小时"
            return cron
        # 间隔天：0 0 */d * *
        if dom.startswith("*/") and minute == "0" and hour == "0" and month == "*" and dow == "*":
            d = int(dom[2:])
            return f"每 {d} 天"
        # 每天：M H * * *
        if dom == "*" and month == "*" and dow == "*":
            return f"每天 {int(hour):02d}:{int(minute):02d}"
        # 每周：M H * * dow
        if dom == "*" and month == "*" and dow != "*":
            return f"每周{_DOW_NAMES[int(dow) % 7]} {int(hour):02d}:{int(minute):02d}"
        # 每月：M H D * *
        if month == "*" and dow == "*":
            return f"每月 {int(dom)} 日 {int(hour):02d}:{int(minute):02d}"
    except (ValueError, TypeError):
        pass
    return cron


def legacy_job_cron(schedule_type: str, interval_minutes: Any, run_time: Optional[str]) -> str:
    """从 legacy 字段（间隔分钟 / HH:MM）推导 cron 表达式"""
    if schedule_type == "daily" and run_time:
        try:
            h, m = map(int, run_time.split(":"))
            return f"{m} {h} * * *"
        except (ValueError, TypeError):
            pass
    m = _to_int(interval_minutes, 0)
    if m <= 0:
        return "0 * * * *"  # 兜底：每小时
    if m <= 60 and 60 % m == 0:
        return f"*/{m} * * * *"
    if m % 60 == 0 and 24 % (m // 60) == 0:
        return f"0 */{m // 60} * * *"
    return f"*/{m} * * * *"


def builtin_cron(entry: Dict[str, Any], config: Dict, overrides: Optional[Dict]) -> Optional[str]:
    """内置任务当前生效的 cron：优先取覆盖配置，否则由周期 spec 推导"""
    ov = (overrides or {}).get(entry["job_id"])
    if ov:
        return ov
    spec = entry["schedule"]
    if spec["type"] == "daily":
        t = config.get(spec["key"], spec["default"])
        try:
            h, m = map(int, str(t).split(":"))
            return f"{m} {h} * * *"
        except (ValueError, TypeError):
            return None
    if spec["type"] == "interval":
        v = _to_int(config.get(spec["key"], spec["default"]), spec["default"])
        if v <= 0:
            return None
        if spec.get("unit") == "天":
            return f"0 0 */{v} * *"
        if spec.get("unit") == "小时":
            return f"0 */{v} * * *"
        if v % 1440 == 0:
            return f"0 0 */{v // 1440} * *"
        return f"*/{v} * * * *"
    return None  # fixed


def build_schedule_desc(entry: Dict[str, Any], config: Dict) -> str:
    """根据注册表条目的 schedule spec 生成中文周期描述"""
    enabled_key = entry.get("enabled_config_key")
    if enabled_key and not config.get(enabled_key, ENABLED_DEFAULTS.get(enabled_key, True)):
        return "已禁用"
    spec = entry["schedule"]
    if spec["type"] == "fixed":
        return spec["desc"]
    if spec["type"] == "daily":
        return f"每天 {config.get(spec['key'], spec['default'])}"
    # interval
    value = _to_int(config.get(spec["key"], spec["default"]), spec["default"])
    if value <= 0:
        return "已禁用"
    if spec.get("unit") == "天":
        return f"每 {value} 天"
    if spec.get("unit") == "小时":
        return f"每 {value} 小时"
    if value % 1440 == 0:
        return f"每 {value // 1440} 天"
    if value % 60 == 0:
        return f"每 {value // 60} 小时"
    return f"每 {value} 分钟"


# ---------------------------------------------------------------------------
# 带任务记录的手动/定时执行包装（低频任务）
# ---------------------------------------------------------------------------

def _make_recorded(module: str, name: str, prefix: str, runner: Callable[[], Awaitable[Any]]):
    """包装一个协程执行入口：执行前后写 task_history。

    runner 返回值支持三种形式：
    - None: 视为完成
    - (success: bool, msg: str): 按成功与否落状态
    - int: >=0 视为完成且 processed=count，<0 视为失败
    """

    async def _wrapped():
        task_id = f"{prefix}_{uuid.uuid4().hex[:8]}"
        await start_task(task_id, module, name)
        try:
            result = await runner()
            if isinstance(result, tuple) and len(result) == 2:
                success, msg = bool(result[0]), result[1]
                await log_task(task_id, f"{'✅' if success else '❌'} {msg or ('执行完成' if success else '执行失败')}")
                await finish_task(task_id, "completed" if success else "error", 0)
            elif isinstance(result, (int, float)):
                count = int(result)
                if count < 0:
                    await log_task(task_id, "❌ 执行失败", "ERROR")
                    await finish_task(task_id, "error", 0)
                else:
                    await log_task(task_id, f"✅ 执行完成，处理 {count} 条")
                    await finish_task(task_id, "completed", count)
            else:
                await log_task(task_id, "✅ 执行完成")
                await finish_task(task_id, "completed", 0)
        except Exception as e:
            await log_task(task_id, f"❌ 执行异常: {e}", "ERROR")
            await finish_task(task_id, "error", 0)

    return _wrapped


async def run_daily_cleanup():
    from monitor import MonitorManager
    await MonitorManager._daily_cleanup()

async def run_discover_warmup():
    from monitor import MonitorManager
    await MonitorManager._warmup_discover_cache()

async def run_calendar_push():
    from monitor import MonitorManager
    return await MonitorManager._calendar_daily_push()

async def run_bgm_schedule_push():
    from monitor import MonitorManager
    return await MonitorManager._bgm_schedule_daily_push()

async def run_subscription_daily_summary():
    from monitor import MonitorManager
    await MonitorManager._subscription_daily_summary()

async def run_emby_index_sync():
    from emby_index_service import sync_index, mark_sync_loop_running
    mark_sync_loop_running(True)
    try:
        return await sync_index()
    finally:
        mark_sync_loop_running(False)


instrumented_daily_cleanup = _make_recorded("系统维护", "每日日志清理", "daily_cleanup", run_daily_cleanup)
instrumented_discover_warmup = _make_recorded("缓存预热", "发现页缓存预热", "discover_warmup", run_discover_warmup)
instrumented_calendar_push = _make_recorded("日历播报", "日历每日播报", "calendar_push", run_calendar_push)
instrumented_bgm_schedule_push = _make_recorded("BGM放送表", "BGM放送表每日推送", "bgm_schedule_push", run_bgm_schedule_push)
instrumented_subscription_summary = _make_recorded("订阅提醒", "订阅每日摘要", "sub_summary", run_subscription_daily_summary)
instrumented_emby_index_sync = _make_recorded("Emby索引同步", "Emby库索引定时同步", "emby_index_sync", run_emby_index_sync)

async def run_rss_cache_clear():
    from rss_core.scheduler import clear_rss_cache
    return await clear_rss_cache()

instrumented_rss_cache_clear = _make_recorded("RSS缓存清理", "RSS 缓存定时清空", "rss_cache_clear", run_rss_cache_clear)

async def run_task_record_cleanup():
    from task_history import cleanup_old_tasks
    from config_manager import ConfigManager
    days = _to_int(ConfigManager.get_config().get("task_record_retention_days", 30), 30)
    # 顺带清理联动记录台账（内部按 webhook_ledger.retention_days 独立控制保留期）
    try:
        from webhook_ledger import cleanup_old_events
        ledger_days = _to_int(ConfigManager.get_config().get("webhook_ledger", {}).get("retention_days", 90), 90)
        await cleanup_old_events(retention_days=ledger_days)
    except Exception:
        pass
    return await cleanup_old_tasks(max_records=500, max_days=days)

instrumented_task_record_cleanup = _make_recorded("任务记录清理", "任务记录定期清理", "task_record_cleanup", run_task_record_cleanup)


# ---------------------------------------------------------------------------
# 注册表本体
# ---------------------------------------------------------------------------

JOB_REGISTRY: List[Dict[str, Any]] = [
    # schedule spec: interval = {type, key(配置键), default, unit("分钟"/"小时")}
    #               daily   = {type, key(时间配置键), default("HH:MM")}
    #               fixed   = {type, desc}  不可编辑周期
    {
        "job_id": "rss_refresh_job",
        "name": "RSS 全量刷新",
        "module": "RSS",
        "description": "定时拉取所有 RSS 订阅源并自动匹配入库",
        "enabled_config_key": "rss_auto_refresh",
        "schedule": {"type": "interval", "key": "rss_refresh_interval", "default": 15, "unit": "分钟"},
        "task_module": "RSS",
        "task_name": "RSS 全量刷新",
    },
    {
        "job_id": "rss_cache_clear_job",
        "name": "RSS 缓存定时清空",
        "module": "RSS缓存清理",
        "description": "定时清空 RSS 订阅项缓存（FeedItem），避免无限膨胀",
        "enabled_config_key": "auto_clear_recognition",
        "schedule": {"type": "interval", "key": "auto_clear_interval", "default": 24, "unit": "小时"},
        "task_module": "RSS缓存清理",
    },
    {
        "job_id": "sub_auto_fill_job",
        "name": "订阅自动搜寻补全",
        "module": "订阅补全",
        "description": "自动搜寻补全缺失集数的订阅并推送下载",
        "enabled_config_key": "sub_auto_fill",
        "schedule": {"type": "interval", "key": "sub_fill_interval", "default": 12, "unit": "小时"},
        "task_module": "订阅补全",
        "task_name": "自动搜寻补全",
    },
    {
        "job_id": "rule_auto_sync_job",
        "name": "远程规则自动同步",
        "module": "规则同步",
        "description": "从远程仓库同步社区识别规则（噪声词/制作组等）",
        "enabled_config_key": "rule_auto_update",
        "schedule": {"type": "interval", "key": "rule_update_interval", "default": 24, "unit": "小时"},
        "task_module": "规则同步",
        "task_name": "规则自动同步",
    },
    {
        "job_id": "stalled_monitor_job",
        "name": "死种清理巡检",
        "module": "死种清理",
        "description": "检测下载器中超过超时阈值的死种并自动清理拉黑",
        "enabled_config_key": "stalled_monitor_enabled",
        "schedule": {"type": "interval", "key": "stalled_monitor_interval", "default": 30, "unit": "分钟"},
        # 编辑弹窗里可一并修改的附加配置项（非周期参数）
        "extra_params": [
            {
                "key": "stalled_timeout_minutes",
                "label": "死种超时阈值 (分钟)",
                "type": "number",
                "min": 0,
                "max": 43200,
                "default": 0,
                "hint": "运行超过该时长且进度未完成的任务将被删除并拉黑，0 为不清理",
            },
        ],
        "task_module": "死种清理",
        "task_name": "死种超时检查",
    },
    {
        "job_id": "space_cleanup_job",
        "name": "磁盘空间自动回收",
        "module": "空间回收",
        "description": "按路径阈值自动删除最老的种子以回收磁盘空间",
        "enabled_config_key": "space_cleanup_enabled",
        "schedule": {"type": "interval", "key": "space_cleanup_interval", "default": 30, "unit": "分钟"},
        "task_module": "空间回收",
        "task_name": "磁盘空间自动清理",
    },
    {
        "job_id": "auto_health_check_job",
        "name": "健康检查巡检",
        "module": "健康检查",
        "description": "定时检测硬盘掉线、CD2 云端可达性与下载源 Cookie 失效",
        "enabled_config_key": "health_check_enabled",
        "schedule": {"type": "interval", "key": "health_check_interval", "default": 30, "unit": "分钟"},
        "task_module": None,  # 高频巡检不写 task_history
    },
    {
        "job_id": "calendar_daily_push_job",
        "name": "日历每日播报",
        "module": "日历播报",
        "description": "每天定时推送今日更新作品的日历播报",
        "enabled_config_key": "calendar_daily_push",
        "schedule": {"type": "daily", "key": "calendar_push_time", "default": "09:00"},
        "task_module": "日历播报",
    },
    {
        "job_id": "bgm_schedule_daily_push_job",
        "name": "BGM 放送表每日推送",
        "module": "BGM放送表",
        "description": "每天定时推送 Bangumi 每日放送表",
        "enabled_config_key": "bgm_schedule_daily_push",
        "schedule": {"type": "daily", "key": "bgm_schedule_push_time", "default": "09:00"},
        "task_module": "BGM放送表",
    },
    {
        "job_id": "subscription_notifier_job",
        "name": "订阅智能提醒检查",
        "module": "订阅提醒",
        "description": "定时检查订阅作品的更新并推送提醒",
        "enabled_config_key": "subscription_notify_enabled",
        "schedule": {"type": "interval", "key": "subscription_notify_interval", "default": 60, "unit": "分钟"},
        "task_module": None,  # 高频巡检不写 task_history
    },
    {
        "job_id": "subscription_daily_summary_job",
        "name": "订阅每日摘要",
        "module": "订阅提醒",
        "description": "每天定时推送订阅更新汇总摘要",
        "enabled_config_key": "subscription_daily_summary",
        "schedule": {"type": "daily", "key": "subscription_summary_time", "default": "08:00"},
        "task_module": "订阅提醒",
        "task_name": "订阅每日摘要",
    },
    {
        "job_id": "bgm_mapping_sync_job",
        "name": "BangumiData 映射表同步",
        "module": "BangumiData同步",
        "description": "定时同步 BangumiData 条目映射表",
        "enabled_config_key": "bgm_mapping_auto_sync",
        "schedule": {"type": "interval", "key": "bgm_mapping_sync_interval", "default": 7, "unit": "天"},
        "task_module": "BangumiData同步",
    },
    {
        "job_id": "discover_cache_warmup_job",
        "name": "发现页缓存预热",
        "module": "缓存预热",
        "description": "每天凌晨预热发现页第一页缓存（Bangumi + TMDB）",
        "enabled_config_key": "discover_warmup_enabled",
        "schedule": {"type": "daily", "key": "discover_warmup_time", "default": "04:00"},
        "task_module": "缓存预热",
    },
    {
        "job_id": "daily_cleanup_job",
        "name": "每日日志清理",
        "module": "系统维护",
        "description": "每天凌晨清理 30 天前的系统审计日志",
        "enabled_config_key": "daily_cleanup_enabled",
        "schedule": {"type": "daily", "key": "daily_cleanup_time", "default": "03:00"},
        "task_module": "系统维护",
    },
    {
        "job_id": "task_record_cleanup_job",
        "name": "任务记录定期清理",
        "module": "任务记录清理",
        "description": "定期清理任务中心的执行记录（保留最近 500 条及设定天数内的记录）",
        "enabled_config_key": "task_record_cleanup_enabled",
        "schedule": {"type": "daily", "key": "task_record_cleanup_time", "default": "03:20"},
        "extra_params": [
            {
                "key": "task_record_retention_days",
                "label": "保留天数",
                "type": "number",
                "min": 1,
                "max": 3650,
                "default": 30,
                "hint": "超过该天数的任务执行记录将被清理（无论时间，始终保留最近 500 条）",
            },
        ],
        "task_module": "任务记录清理",
    },
    {
        "job_id": "emby_index_sync_job",
        "name": "Emby 库索引定时同步",
        "module": "Emby索引同步",
        "description": "定时全量同步 Emby 媒体库索引表（需已配置 Emby）",
        "enabled_config_key": "emby_index_sync_enabled",
        "schedule": {"type": "interval", "key": "emby_index_sync_interval", "default": 1440, "unit": "分钟"},
        "task_module": "Emby索引同步",
    },
    {
        "job_id": "cd2_rapid_retry_job",
        "name": "CD2 秒传重试队列轮询",
        "module": "CD2",
        "description": "轮询秒传失败的重试队列（系统内部任务，不可停用）",
        "enabled_config_key": None,
        "locked": True,
        "schedule": {"type": "fixed", "desc": "每 1 分钟"},
        "task_module": None,
    },
]

_REGISTRY_MAP = {e["job_id"]: e for e in JOB_REGISTRY}

# 各开关配置键的默认值（与 config_manager.DEFAULT_CONFIG 保持一致）
ENABLED_DEFAULTS: Dict[str, bool] = {
    "rss_auto_refresh": True,
    "auto_clear_recognition": False,
    "sub_auto_fill": False,
    "rule_auto_update": False,
    "stalled_monitor_enabled": True,
    "space_cleanup_enabled": False,
    "health_check_enabled": True,
    "calendar_daily_push": False,
    "bgm_schedule_daily_push": False,
    "subscription_notify_enabled": True,
    "subscription_daily_summary": False,
    "bgm_mapping_auto_sync": True,
    "discover_warmup_enabled": True,
    "daily_cleanup_enabled": True,
    "task_record_cleanup_enabled": True,
    "emby_index_sync_enabled": True,
}


# ---------------------------------------------------------------------------
# 手动触发入口（按 job_id 分发）
# ---------------------------------------------------------------------------

async def _run_job_dispatch(job_id: str, params: Optional[Dict[str, Any]] = None):
    if job_id == "rss_refresh_job":
        from rss_core.scheduler import refresh_all_feeds
        await refresh_all_feeds()
    elif job_id == "rss_cache_clear_job":
        await instrumented_rss_cache_clear()
    elif job_id == "rss_detect_job":
        from rss_core.detector import RssDetector
        await RssDetector.run_scheduled_tasks()
    elif job_id == "sub_auto_fill_job":
        from monitor import MonitorManager
        await MonitorManager._auto_fill_subscriptions()
    elif job_id == "rule_auto_sync_job":
        from monitor import MonitorManager
        await MonitorManager._auto_sync_rules()
    elif job_id == "stalled_monitor_job":
        from rss_core.scheduler import check_stalled_downloads
        await check_stalled_downloads()
    elif job_id == "space_cleanup_job":
        from clients.space_cleanup_task import run_space_cleanup
        await run_space_cleanup(manual=True)
    elif job_id == "auto_health_check_job":
        from monitor import MonitorManager
        await MonitorManager._auto_health_check()
    elif job_id == "calendar_daily_push_job":
        await instrumented_calendar_push()
    elif job_id == "bgm_schedule_daily_push_job":
        await instrumented_bgm_schedule_push()
    elif job_id == "subscription_notifier_job":
        from monitor import MonitorManager
        await MonitorManager._subscription_notifier_check()
    elif job_id == "subscription_daily_summary_job":
        await instrumented_subscription_summary()
    elif job_id == "bgm_mapping_sync_job":
        from monitor import MonitorManager
        await MonitorManager._auto_sync_bgm_mapping()
    elif job_id == "discover_cache_warmup_job":
        await instrumented_discover_warmup()
    elif job_id == "daily_cleanup_job":
        await instrumented_daily_cleanup()
    elif job_id == "emby_index_sync_job":
        await instrumented_emby_index_sync()
    elif job_id == "cd2_rapid_retry_job":
        from clients.cd2.rapid_retry import RapidUploadRetryManager
        await RapidUploadRetryManager.run_due_jobs()
    elif job_id == "task_record_cleanup_job":
        await instrumented_task_record_cleanup()
    elif job_id.startswith("maint_"):
        await _recorded_maintenance(job_id, params)
    else:
        raise ValueError(f"未知的定时任务: {job_id}")


def get_registry_entry(job_id: str) -> Optional[Dict[str, Any]]:
    return _REGISTRY_MAP.get(job_id)


# ---------------------------------------------------------------------------
# 用户自定义定时任务（任务计划页创建，持久化在 custom_scheduled_jobs 表）
# ---------------------------------------------------------------------------

# 可作为自定义任务动作的注册表条目：排除聚合条目与系统内部任务
CUSTOM_ACTION_EXCLUDE = {"cd2_rapid_retry_job"}


# ---------------------------------------------------------------------------
# 维护类动作（维护中心"清空/同步"按钮的定时任务化，仅供自定义任务选择）
# ---------------------------------------------------------------------------

# 可安全定时清空的缓存表白名单（与维护中心"缓存"分类对应）
TRUNCATABLE_CACHE_TABLES: Dict[str, str] = {
    "public.discover_cache": "发现页缓存",
    "public.calendar_subjects": "放送时刻表缓存",
    "public.system_logs": "系统审计日志",
    "public.task_records": "任务中心记录",
    "public.organize_history": "整理历史",
    "public.download_history": "下载历史",
    "metadata.media_title_index": "媒体标题索引缓存",
}

MAINTENANCE_ACTIONS: List[Dict[str, str]] = [
    {
        "action": "maint_clear_fingerprints",
        "name": "清空智能记忆",
        "module": "维护",
        "description": "清空全部智能记忆（指纹）记录，下次识别会重新进行云端搜索",
    },
    {
        "action": "maint_cleanup_invalid_fingerprints",
        "name": "清理无效智能记忆",
        "module": "维护",
        "description": "仅清理缺乏区分度的无效记忆，保留有效记忆",
    },
    {
        "action": "maint_bangumi_subject_warmup",
        "name": "预热Bangumi缓存",
        "module": "维护",
        "description": "遍历 BangumiData 条目预热 Subject 详情缓存，任务在后台执行",
    },
    {
        "action": "maint_sytmdb_sync",
        "name": "SYTMDB元数据同步",
        "module": "维护",
        "description": "从 SYTMDB 服务器拉取自定义元数据写入本地缓存（需已在设置中配置 SYTMDB 地址）",
    },
    {
        "action": "maint_calendar_refresh",
        "name": "刷新放送日期",
        "module": "维护",
        "description": "批量刷新所有追踪剧集的放送日期（从 TMDB 拉取），保持日历每日播报与订阅提醒的判定数据新鲜",
    },
    {
        "action": "maint_tmdb_refresh_all",
        "name": "TMDB元数据全量刷新",
        "module": "维护",
        "description": "对本地 TMDB 离线库条目强制与 TMDB 云端同步，可按更新时间/首播年份/媒体类型/流派筛选，不填则全量刷新",
        "params_schema": [
            {"key": "older_than_days", "label": "更新时间筛选（天）", "type": "number", "hint": "只刷新 N 天前更新的记录，留空表示不限制"},
            {"key": "year_from", "label": "首播年份（起）", "type": "number", "hint": "如 2020，留空表示不限制"},
            {"key": "year_to", "label": "首播年份（止）", "type": "number", "hint": "如 2024，留空表示不限制"},
            {"key": "media_type", "label": "媒体类型筛选", "type": "select", "default": "",
             "options": [{"title": "全部", "value": ""}, {"title": "电影", "value": "movie"}, {"title": "剧集", "value": "tv"}]},
            {"key": "genre_ids", "label": "流派 ID 筛选", "type": "text", "hint": "逗号分隔，如 16,10749，留空表示不限制"},
        ],
    },
]

for _table, _label in TRUNCATABLE_CACHE_TABLES.items():
    MAINTENANCE_ACTIONS.append({
        "action": f"maint_truncate_{_table.replace('.', '_')}",
        "name": f"清空{_label}",
        "module": "维护",
        "description": f"定时清空数据表 {_table}（缓存类，清空后自动重建）",
    })

_MAINTENANCE_ACTION_MAP = {a["action"]: a for a in MAINTENANCE_ACTIONS}

# 因界面精简而移除按钮的维护操作，启动时确保存在一条停用的自定义任务卡片，
# 作为手动触发的常驻入口（用户启用后即可按 cron 自动执行）
DEFAULT_CUSTOM_JOBS: List[Dict[str, str]] = [
    {"action": "maint_clear_fingerprints", "name": "清空智能记忆", "cron": "0 5 * * 1"},
    {"action": "maint_cleanup_invalid_fingerprints", "name": "清理无效智能记忆", "cron": "0 5 * * 1"},
    {"action": "maint_bangumi_subject_warmup", "name": "预热Bangumi缓存", "cron": "0 6 * * 1"},
    {"action": "maint_sytmdb_sync", "name": "SYTMDB元数据同步", "cron": "0 4 * * *"},
]


async def _run_maintenance_action(action_id: str, params: Optional[Dict[str, Any]] = None):
    """执行维护动作本体（不含任务记录包装）"""
    from sqlalchemy import text as sql_text
    if action_id == "maint_clear_fingerprints":
        from metadata.meta_cache import MetaCacheManager
        await MetaCacheManager.clear_fingerprints()
    elif action_id == "maint_cleanup_invalid_fingerprints":
        from routers.cache import cleanup_invalid_fingerprints
        await cleanup_invalid_fingerprints()
    elif action_id == "maint_bangumi_subject_warmup":
        from routers.bangumi import warmup_raw_cache
        await warmup_raw_cache(force=False)
    elif action_id == "maint_sytmdb_sync":
        from routers.sytmdb import _do_sytmdb_sync, _get_sytmdb_config
        addr, token = _get_sytmdb_config()
        if not addr:
            raise ValueError("未配置 SYTMDB 地址，请先在系统设置中填写 SYTMDB Host")
        await _do_sytmdb_sync(addr, token)
    elif action_id == "maint_calendar_refresh":
        from routers.calendar import refresh_all_subjects
        await refresh_all_subjects()
    elif action_id == "maint_tmdb_refresh_all":
        from routers.tmdb_full import task_refresh_all_metadata
        p = params or {}
        await task_refresh_all_metadata(
            older_than_days=int(p["older_than_days"]) if p.get("older_than_days") else None,
            year_from=int(p["year_from"]) if p.get("year_from") else None,
            year_to=int(p["year_to"]) if p.get("year_to") else None,
            media_type=p.get("media_type") or None,
            genre_ids=p.get("genre_ids") or None,
        )
    elif action_id.startswith("maint_truncate_"):
        # action_id 格式: maint_truncate_<schema>_<table>，schema 只有 public/metadata 两种
        raw = action_id[len("maint_truncate_"):]
        table = next((t for t in TRUNCATABLE_CACHE_TABLES if t.replace(".", "_") == raw), None)
        if not table:
            raise ValueError(f"不允许清空的表: {raw}")
        async with db.session_scope(force_new=True):
            await db.session.execute(sql_text(f'TRUNCATE TABLE {table} RESTART IDENTITY'))
            await db.session.commit()
    else:
        raise ValueError(f"未知的维护动作: {action_id}")


async def _recorded_maintenance(action_id: str, params: Optional[Dict[str, Any]] = None):
    """带任务记录的维护动作执行入口"""
    name = _MAINTENANCE_ACTION_MAP.get(action_id, {}).get("name", action_id)
    task_id = f"{action_id}_{uuid.uuid4().hex[:8]}"
    await start_task(task_id, "维护", name)
    try:
        result = await _run_maintenance_action(action_id, params)
        if isinstance(result, dict):
            if result.get("success") is False:
                raise ValueError(result.get("message") or "执行失败")
            if result.get("updated") is not None:
                await log_task(task_id, f"✅ 执行完成，更新 {result['updated']} 个条目")
            else:
                await log_task(task_id, "✅ 执行完成")
        else:
            await log_task(task_id, "✅ 执行完成")
        await finish_task(task_id, "completed", 0)
    except Exception as e:
        await log_task(task_id, f"❌ 执行失败: {e}", "ERROR")
        await finish_task(task_id, "error", 0)


def get_action_catalog() -> List[Dict[str, Any]]:
    """返回可被自定义定时任务选择的动作目录（内置调度任务 + 维护类动作）"""
    builtin = [
        {
            "action": e["job_id"],
            "name": e["name"],
            "module": e["module"],
            "description": e["description"],
        }
        for e in JOB_REGISTRY
        if not e.get("locked") and e["job_id"] not in CUSTOM_ACTION_EXCLUDE
    ]
    maintenance = [
        {**a, "params_schema": a.get("params_schema")} for a in MAINTENANCE_ACTIONS
    ]
    return builtin + maintenance


def _custom_job_runner(job_id: int, action: str):
    """自定义任务的执行体：跑动作（带任务参数）+ 回写 last_run_at"""

    async def _run():
        record_params: Optional[Dict[str, Any]] = None
        record_action = action
        try:
            from sqlmodel import select
            from models import CustomScheduledJob
            async with db.session_scope(force_new=True):
                result = await db.session.execute(
                    select(CustomScheduledJob).where(CustomScheduledJob.id == job_id)
                )
                record = result.scalar_one_or_none()
                if not record:
                    return
                record_action = record.action
                record_params = dict(record.params) if record.params else None
        except Exception:
            pass
        try:
            await _run_job_dispatch(record_action, record_params)
        finally:
            try:
                from sqlmodel import select
                from models import CustomScheduledJob
                async with db.session_scope(force_new=True):
                    result = await db.session.execute(
                        select(CustomScheduledJob).where(CustomScheduledJob.id == job_id)
                    )
                    record = result.scalar_one_or_none()
                    if record:
                        record.last_run_at = datetime.now()
                        db.session.add(record)
                        await db.session.commit()
            except Exception:
                pass

    return _run


def register_custom_job(job) -> bool:
    """把一条 CustomScheduledJob 注册进 APScheduler（已存在则替换触发器）。

    优先使用 cron 表达式；cron 为空时从 legacy 字段推导并回填。
    """
    from apscheduler.triggers.cron import CronTrigger
    from monitor import MonitorManager
    if not MonitorManager._scheduler:
        return False
    job_func = _custom_job_runner(job.id, job.action)
    custom_id = f"custom_job_{job.id}"

    cron = (job.cron or "").strip()
    if not cron:
        cron = legacy_job_cron(job.schedule_type, job.interval_minutes, job.run_time)
        try:
            job.cron = cron
            db.session.add(job)
        except Exception:
            pass
    try:
        trigger = CronTrigger.from_crontab(cron)
        MonitorManager._scheduler.add_job(
            job_func, trigger=trigger,
            id=custom_id, replace_existing=True,
        )
        return True
    except Exception:
        return False


def unregister_custom_job(job_id: int):
    """从 APScheduler 移除自定义任务（不存在时静默）"""
    from monitor import MonitorManager
    if not MonitorManager._scheduler:
        return
    try:
        MonitorManager._scheduler.remove_job(f"custom_job_{job_id}")
    except Exception:
        pass
