"""
任务计划 API — 统一查看/启停/手动触发所有系统级定时任务，
并支持创建自定义定时任务（选择动作 + 间隔/每日定时）。
数据源: task_scheduler.JOB_REGISTRY + APScheduler 实际状态 + task_records 最近执行记录。
"""
import asyncio
import re
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from config_manager import ConfigManager
from database import db
from logger import log_audit
from models import TaskRecord, CustomScheduledJob
from task_scheduler import (
    JOB_REGISTRY,
    ENABLED_DEFAULTS,
    get_registry_entry,
    get_action_catalog,
    build_schedule_desc,
    describe_cron,
    legacy_job_cron,
    builtin_cron,
    register_custom_job,
    unregister_custom_job,
    _run_job_dispatch,
)

router = APIRouter(prefix="/api/scheduler", tags=["任务计划"])

RUN_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


def _validate_cron(cron: str) -> str:
    """校验 cron 表达式（5 段），合法则原样返回，否则抛 400"""
    from apscheduler.triggers.cron import CronTrigger
    cron = (cron or "").strip()
    try:
        CronTrigger.from_crontab(cron)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"无效的 cron 表达式: {cron} ({e})")
    return cron


class ToggleBody(BaseModel):
    enabled: bool


class CustomJobBody(BaseModel):
    name: Optional[str] = None
    action: str
    cron: Optional[str] = None  # 5 段 cron 表达式（推荐）
    # 以下为 legacy 字段：未提供 cron 时用于推导
    schedule_type: Optional[str] = None
    interval_minutes: Optional[int] = None
    run_time: Optional[str] = None
    enabled: bool = True
    params: Optional[dict] = None  # 动作参数（按动作目录的 params_schema 校验）


def _builtin_extra_params(entry: dict, config: dict) -> list:
    """内置任务的附加配置参数（编辑弹窗里与周期一起修改）"""
    result = []
    for p in entry.get("extra_params") or []:
        value = config.get(p["key"], p.get("default"))
        try:
            value = int(value) if p.get("type") == "number" else value
        except (TypeError, ValueError):
            value = p.get("default")
        result.append({**p, "value": value})
    return result


class BuiltinJobBody(BaseModel):
    enabled: Optional[bool] = None
    cron: Optional[str] = None  # 提供时写入 scheduler_cron_overrides；空串/None 表示取消覆盖
    interval_value: Optional[float] = None  # legacy，未提供 cron 时按 spec 单位写入
    run_time: Optional[str] = None  # legacy
    extra: Optional[dict] = None  # 附加配置参数 {config_key: value}


class CronPreviewBody(BaseModel):
    cron: str


async def _get_last_runs(modules: list) -> dict:
    """按模块批量查询最近一条任务记录 (PostgreSQL DISTINCT ON)"""
    modules = [m for m in modules if m]
    if not modules:
        return {}
    async with db.session_scope(force_new=True):
        stmt = (
            select(TaskRecord)
            .where(TaskRecord.module.in_(modules))
            .distinct(TaskRecord.module)
            .order_by(TaskRecord.module, TaskRecord.started_at.desc())
        )
        result = await db.session.execute(stmt)
        rows = result.scalars().all()
        return {r.module: r for r in rows}


def _serialize_last_run(record) -> dict:
    duration = None
    if record.finished_at and record.started_at:
        duration = round((record.finished_at - record.started_at).total_seconds())
    return {
        "task_id": record.task_id,
        "status": record.status,
        "started_at": record.started_at.isoformat() if record.started_at else None,
        "finished_at": record.finished_at.isoformat() if record.finished_at else None,
        "duration_seconds": duration,
        "processed": record.processed,
    }


def _builtin_schedule_info(entry: dict, config: dict, overrides: dict) -> dict:
    """解析内置任务的周期，返回前端可展示/编辑的字段（cron 为统一模型）"""
    spec = entry["schedule"]
    info = {
        "schedule_type": spec["type"],
        "interval_value": None,
        "interval_unit": None,
        "run_time": None,
        "cron": None,
        "cron_source": None,  # override=用户自定义 / default=系统默认
    }
    if spec["type"] == "interval":
        try:
            info["interval_value"] = type(spec["default"])(config.get(spec["key"], spec["default"]))
        except (TypeError, ValueError):
            info["interval_value"] = spec["default"]
        info["interval_unit"] = spec.get("unit", "分钟")
    elif spec["type"] == "daily":
        info["run_time"] = config.get(spec["key"], spec["default"])

    cron = builtin_cron(entry, config, overrides)
    info["cron"] = cron
    info["cron_source"] = "override" if (overrides or {}).get(entry["job_id"]) else ("default" if cron else None)
    return info


@router.get("/jobs", summary="获取所有定时任务及状态")
async def list_jobs():
    from monitor import MonitorManager

    config = ConfigManager.get_config()
    overrides = config.get("scheduler_cron_overrides") or {}
    scheduler = MonitorManager._scheduler
    job_map = {job.id: job for job in scheduler.get_jobs()} if scheduler else {}

    entries = [e for e in JOB_REGISTRY if not e.get("aggregate")]
    last_runs = await _get_last_runs([e.get("task_module") for e in entries])

    items = []
    for entry in JOB_REGISTRY:
        job_id = entry["job_id"]
        job = job_map.get(job_id)
        enabled_key = entry.get("enabled_config_key")
        enabled = bool(config.get(enabled_key, ENABLED_DEFAULTS.get(enabled_key, True))) if enabled_key else True
        last_record = last_runs.get(entry.get("task_module")) if entry.get("task_module") else None

        schedule_info = _builtin_schedule_info(entry, config, overrides)
        # 有覆盖时周期描述按 cron 翻译
        schedule_desc = (
            describe_cron(schedule_info["cron"])
            if schedule_info["cron_source"] == "override"
            else build_schedule_desc(entry, config)
        )

        items.append({
            "job_id": job_id,
            "name": entry["name"],
            "module": entry["module"],
            "description": entry["description"],
            "schedule_desc": schedule_desc,
            "enabled": enabled,
            "scheduled": job is not None and job.next_run_time is not None,
            "locked": bool(entry.get("locked", False)),
            "editable": not entry.get("locked", False) and entry["schedule"]["type"] != "fixed",
            "can_run": True,
            **schedule_info,
            "extra_params": _builtin_extra_params(entry, config),
            "next_run": job.next_run_time.isoformat() if job and job.next_run_time else None,
            "last_run": _serialize_last_run(last_record) if last_record else None,
        })

    return {"jobs": items}


@router.put("/jobs/{job_id}", summary="修改内置定时任务的周期/开关")
async def update_builtin_job(job_id: str, body: BuiltinJobBody):
    entry = get_registry_entry(job_id)
    if not entry or entry.get("aggregate"):
        raise HTTPException(status_code=404, detail="任务不存在")
    if entry.get("locked") or entry["schedule"]["type"] == "fixed":
        raise HTTPException(status_code=400, detail="该任务不支持修改周期")

    spec = entry["schedule"]
    config_updates: dict = {}
    if body.enabled is not None and entry.get("enabled_config_key"):
        config_updates[entry["enabled_config_key"]] = body.enabled

    # 附加配置参数（仅接受注册表声明的键）
    extra_defs = {p["key"]: p for p in entry.get("extra_params") or []}
    for key, value in (body.extra or {}).items():
        if key not in extra_defs:
            raise HTTPException(status_code=400, detail=f"不支持的配置项: {key}")
        p = extra_defs[key]
        if p.get("type") == "number":
            try:
                value = int(float(value))
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail=f"{p['label']} 需为数字")
            if "min" in p and value < p["min"]:
                raise HTTPException(status_code=400, detail=f"{p['label']} 不能小于 {p['min']}")
            if "max" in p and value > p["max"]:
                raise HTTPException(status_code=400, detail=f"{p['label']} 不能大于 {p['max']}")
        config_updates[key] = value

    if body.cron is not None:
        # cron 覆盖模式：空串表示取消覆盖回退系统默认
        cron = body.cron.strip()
        if cron:
            _validate_cron(cron)
            config_updates["scheduler_cron_overrides"] = {job_id: cron}
        else:
            config_updates["scheduler_cron_overrides"] = {job_id: None}
    else:
        # legacy 直改配置键（会自动清除 cron 覆盖）
        if spec["type"] == "interval" and body.interval_value is not None:
            value = float(body.interval_value)
            unit = spec.get("unit", "分钟")
            max_value = 168 if unit == "小时" else 10080
            if value <= 0 or value > max_value:
                raise HTTPException(status_code=400, detail=f"间隔需在 1 ~ {max_value} {unit}之间")
            if unit == "小时" and value != int(value):
                raise HTTPException(status_code=400, detail="小时间隔需为整数")
            config_updates[spec["key"]] = int(value)
            config_updates["scheduler_cron_overrides"] = {job_id: None}

        if spec["type"] == "daily" and body.run_time:
            if not RUN_TIME_RE.match(body.run_time.strip()):
                raise HTTPException(status_code=400, detail="执行时间格式需为 HH:MM")
            config_updates[spec["key"]] = body.run_time.strip()
            config_updates["scheduler_cron_overrides"] = {job_id: None}

    if not config_updates:
        return {"status": "success"}

    ConfigManager.update_config(config_updates)
    from monitor import MonitorManager
    await MonitorManager.reload()
    log_audit("系统", "任务计划", f"修改定时任务配置: {entry['name']}")
    return {"status": "success"}


@router.post("/cron/preview", summary="预览 cron 表达式的未来触发时间")
async def cron_preview(body: CronPreviewBody):
    from apscheduler.triggers.cron import CronTrigger
    cron = _validate_cron(body.cron)
    trigger = CronTrigger.from_crontab(cron)
    next_runs = []
    nxt = trigger.get_next_fire_time(None, datetime.now())
    for _ in range(3):
        if not nxt:
            break
        next_runs.append(nxt.isoformat())
        # 传入上一次触发时刻作为 previous_fire_time，才能推出下一次
        nxt = trigger.get_next_fire_time(nxt, nxt)
    return {"cron": cron, "desc": describe_cron(cron), "next_runs": next_runs}


@router.post("/jobs/{job_id}/toggle", summary="启用/停用定时任务")
async def toggle_job(job_id: str, body: ToggleBody):
    entry = get_registry_entry(job_id)
    if not entry or entry.get("aggregate"):
        raise HTTPException(status_code=404, detail="任务不存在")
    enabled_key = entry.get("enabled_config_key")
    if not enabled_key or entry.get("locked"):
        raise HTTPException(status_code=400, detail="该任务不支持启停")

    ConfigManager.update_config({enabled_key: body.enabled})
    from monitor import MonitorManager
    await MonitorManager.reload()
    log_audit("系统", "任务计划", f"{'启用' if body.enabled else '停用'}定时任务: {entry['name']}")
    return {"status": "success", "job_id": job_id, "enabled": body.enabled}


@router.post("/jobs/{job_id}/run", summary="立即手动执行定时任务")
async def run_job(job_id: str):
    entry = get_registry_entry(job_id)
    if not entry or entry.get("aggregate"):
        raise HTTPException(status_code=404, detail="任务不存在")

    task_module = entry.get("task_module")
    if task_module:
        async with db.session_scope(force_new=True):
            stmt = (
                select(TaskRecord)
                .where(TaskRecord.module == task_module, TaskRecord.status == "running")
                .limit(1)
            )
            result = await db.session.execute(stmt)
            if result.scalar_one_or_none():
                raise HTTPException(status_code=409, detail="该任务正在运行中，请稍后再试")

    asyncio.create_task(_run_job_dispatch(job_id))
    log_audit("系统", "任务计划", f"手动触发定时任务: {entry['name']}")
    return {"status": "started", "job_id": job_id, "name": entry["name"]}


# ---------------------------------------------------------------------------
# 自定义定时任务（用户创建：选动作 + 设定周期）
# ---------------------------------------------------------------------------

_ACTION_MAP = {a["action"]: a for a in get_action_catalog()}


def _resolve_cron(body: CustomJobBody) -> str:
    """解析请求里的 cron：优先用 cron 字段，否则从 legacy 字段推导"""
    if body.cron is not None:
        return _validate_cron(body.cron)
    schedule_type = body.schedule_type or "interval"
    if schedule_type == "daily":
        if not body.run_time or not RUN_TIME_RE.match(body.run_time.strip()):
            raise HTTPException(status_code=400, detail="执行时间格式需为 HH:MM")
    else:
        minutes = body.interval_minutes or 0
        if minutes < 1 or minutes > 10080:
            raise HTTPException(status_code=400, detail="间隔需在 1 分钟 ~ 7 天之间")
    return legacy_job_cron(schedule_type, body.interval_minutes, body.run_time)


def _validate_action_params(action: str, params: Optional[dict]) -> Optional[dict]:
    """按动作目录的 params_schema 校验并清洗任务参数"""
    schema = (_ACTION_MAP.get(action) or {}).get("params_schema") or []
    if not schema:
        return None
    if not params:
        return None
    cleaned: dict = {}
    for p in schema:
        v = params.get(p["key"])
        if v is None or v == "":
            continue
        if p.get("type") == "number":
            try:
                v = int(float(v))
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail=f"{p['label']} 需为数字")
            if p.get("min") is not None and v < p["min"]:
                raise HTTPException(status_code=400, detail=f"{p['label']} 不能小于 {p['min']}")
            if p.get("max") is not None and v > p["max"]:
                raise HTTPException(status_code=400, detail=f"{p['label']} 不能大于 {p['max']}")
        cleaned[p["key"]] = v
    return cleaned or None


@router.get("/actions", summary="获取可选的任务动作目录")
async def list_actions():
    return {"actions": get_action_catalog()}


@router.get("/custom", summary="获取自定义定时任务列表")
async def list_custom_jobs():
    from monitor import MonitorManager

    scheduler = MonitorManager._scheduler
    job_map = {job.id: job for job in scheduler.get_jobs()} if scheduler else {}

    async with db.session_scope(force_new=True):
        result = await db.session.execute(
            select(CustomScheduledJob).order_by(CustomScheduledJob.created_at.desc())
        )
        rows = result.scalars().all()

    last_runs = await _get_last_runs(
        [_ACTION_MAP.get(r.action, {}).get("module") for r in rows]
    )

    items = []
    for r in rows:
        action_info = _ACTION_MAP.get(r.action, {})
        registry = get_registry_entry(r.action)
        task_record = last_runs.get(action_info.get("module")) if action_info.get("module") else None
        job = job_map.get(f"custom_job_{r.id}")
        cron = (r.cron or "").strip() or legacy_job_cron(r.schedule_type, r.interval_minutes, r.run_time)
        items.append({
            "id": r.id,
            "name": r.name or action_info.get("name", r.action),
            "action": r.action,
            "action_name": action_info.get("name", r.action),
            "module": action_info.get("module", ""),
            "cron": cron,
            "schedule_desc": describe_cron(cron),
            "params": r.params,
            "enabled": r.enabled,
            "scheduled": job is not None and job.next_run_time is not None,
            "next_run": job.next_run_time.isoformat() if job and job.next_run_time else None,
            "last_run": _serialize_last_run(task_record) if task_record else (
                {"status": "unknown", "started_at": r.last_run_at.isoformat() if r.last_run_at else None,
                 "finished_at": None, "duration_seconds": None, "processed": 0} if r.last_run_at else None
            ),
            "task_module": registry.get("task_module") if registry else None,
        })
    return {"jobs": items}


@router.post("/custom", summary="创建自定义定时任务")
async def create_custom_job(body: CustomJobBody):
    if body.action not in _ACTION_MAP:
        raise HTTPException(status_code=400, detail=f"未知的任务动作: {body.action}")
    cron = _resolve_cron(body)
    action_info = _ACTION_MAP[body.action]
    async with db.session_scope(force_new=True):
        record = CustomScheduledJob(
            name=(body.name or "").strip() or action_info["name"],
            action=body.action,
            cron=cron,
            params=_validate_action_params(body.action, body.params),
            enabled=body.enabled,
        )
        db.session.add(record)
        await db.session.commit()
        await db.session.refresh(record)

    if record.enabled:
        register_custom_job(record)
    log_audit("系统", "任务计划", f"创建自定义定时任务: {record.name} ({record.action}, cron: {cron})")
    return {"status": "success", "id": record.id}


@router.put("/custom/{job_id}", summary="修改自定义定时任务")
async def update_custom_job(job_id: int, body: CustomJobBody):
    if body.action not in _ACTION_MAP:
        raise HTTPException(status_code=400, detail=f"未知的任务动作: {body.action}")
    cron = _resolve_cron(body)
    action_info = _ACTION_MAP[body.action]
    async with db.session_scope(force_new=True):
        result = await db.session.execute(
            select(CustomScheduledJob).where(CustomScheduledJob.id == job_id)
        )
        record = result.scalar_one_or_none()
        if not record:
            raise HTTPException(status_code=404, detail="定时任务不存在")
        record.name = (body.name or "").strip() or action_info["name"]
        record.action = body.action
        record.cron = cron
        record.params = _validate_action_params(body.action, body.params)
        record.enabled = body.enabled
        record.updated_at = datetime.now()
        db.session.add(record)
        await db.session.commit()

    if record.enabled:
        register_custom_job(record)
    else:
        unregister_custom_job(job_id)
    log_audit("系统", "任务计划", f"修改自定义定时任务: {record.name}")
    return {"status": "success"}


@router.delete("/custom/{job_id}", summary="删除自定义定时任务")
async def delete_custom_job(job_id: int):
    async with db.session_scope(force_new=True):
        result = await db.session.execute(
            select(CustomScheduledJob).where(CustomScheduledJob.id == job_id)
        )
        record = result.scalar_one_or_none()
        if not record:
            raise HTTPException(status_code=404, detail="定时任务不存在")
        await db.session.delete(record)
        await db.session.commit()

    unregister_custom_job(job_id)
    log_audit("系统", "任务计划", f"删除自定义定时任务: {record.name}")
    return {"status": "success"}


@router.post("/custom/{job_id}/toggle", summary="启用/停用自定义定时任务")
async def toggle_custom_job(job_id: int, body: ToggleBody):
    async with db.session_scope(force_new=True):
        result = await db.session.execute(
            select(CustomScheduledJob).where(CustomScheduledJob.id == job_id)
        )
        record = result.scalar_one_or_none()
        if not record:
            raise HTTPException(status_code=404, detail="定时任务不存在")
        record.enabled = body.enabled
        db.session.add(record)
        await db.session.commit()

    if body.enabled:
        register_custom_job(record)
    else:
        unregister_custom_job(job_id)
    log_audit("系统", "任务计划", f"{'启用' if body.enabled else '停用'}自定义定时任务: {record.name}")
    return {"status": "success", "enabled": body.enabled}


@router.post("/custom/{job_id}/run", summary="立即执行自定义定时任务")
async def run_custom_job(job_id: int):
    async with db.session_scope(force_new=True):
        result = await db.session.execute(
            select(CustomScheduledJob).where(CustomScheduledJob.id == job_id)
        )
        record = result.scalar_one_or_none()
        if not record:
            raise HTTPException(status_code=404, detail="定时任务不存在")

    registry = get_registry_entry(record.action)
    task_module = registry.get("task_module") if registry else None
    if task_module:
        async with db.session_scope(force_new=True):
            stmt = (
                select(TaskRecord)
                .where(TaskRecord.module == task_module, TaskRecord.status == "running")
                .limit(1)
            )
            dup = await db.session.execute(stmt)
            if dup.scalar_one_or_none():
                raise HTTPException(status_code=409, detail="该任务正在运行中，请稍后再试")

    asyncio.create_task(_run_job_dispatch(record.action, record.params))
    log_audit("系统", "任务计划", f"手动执行自定义定时任务: {record.name}")
    return {"status": "started", "name": record.name}
