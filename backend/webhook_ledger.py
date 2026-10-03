"""联动记录中心：Webhook 事件台账服务。

每个逻辑事件一行记录，判重在数据库完成（替代旧的进程内存窗口），
原生 Webhook 与内部 gRPC 监控对同一文件的重复触发会合并进同一行。
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from sqlalchemy import select, delete, func

from config_manager import ConfigManager
from database import db
from models import WebhookEvent

logger = logging.getLogger("WebhookLedger")

# 台账关闭时的兜底判重窗口（秒）：保留最小限度的双通道去重能力
_FALLBACK_DEDUP_WINDOW = 120
_fallback_events: Dict[str, float] = {}


def ledger_enabled() -> bool:
    return bool(ConfigManager.get_config().get("webhook_ledger", {}).get("enabled", True))


def _dedup_window() -> int:
    try:
        return int(ConfigManager.get_config().get("webhook_ledger", {}).get("dedup_window_seconds", 180))
    except (TypeError, ValueError):
        return 180


def build_event_key(action: str, file_path: str) -> str:
    """判重键：action + 规范化路径（同路径不同动作不算重复）。"""
    return f"{action}:{(file_path or '').strip()}"


def _is_duplicate_fallback(file_path: str) -> bool:
    """台账关闭时的内存判重兜底（与旧 _is_duplicate_event 行为一致）。"""
    now = datetime.now().timestamp()
    if len(_fallback_events) > 500:
        expired = [k for k, t in _fallback_events.items() if now - t >= _FALLBACK_DEDUP_WINDOW]
        for k in expired:
            _fallback_events.pop(k, None)
    last = _fallback_events.get(file_path)
    _fallback_events[file_path] = now
    return last is not None and now - last < _FALLBACK_DEDUP_WINDOW


async def record_event(action: str, file_path: str, is_dir: bool, source: str,
                       payload: Dict[str, Any], parent_event_id: Optional[int] = None) -> Optional[WebhookEvent]:
    """事件到达：落库判重并记录。

    返回新建的台账记录（含台账关闭时的内存临时记录）；窗口内的重复到达返回 None
    （已合并进原记录：sources 追加来源、dup_count +1）。
    """
    if not file_path:
        return None

    if not ledger_enabled():
        if _is_duplicate_fallback(file_path):
            return None
        # 关闭台账时不持久化，仅返回临时对象让执行链路照常走
        return WebhookEvent(event_key=build_event_key(action, file_path), action=action,
                            file_path=file_path, is_dir=is_dir, sources=[source],
                            payload=payload, status="pending")

    key = build_event_key(action, file_path)
    window_start = datetime.now() - timedelta(seconds=_dedup_window())
    now = datetime.now()

    async with db.session_scope(force_new=True):
        result = await db.session.execute(
            select(WebhookEvent)
            .where(WebhookEvent.event_key == key, WebhookEvent.last_event_at >= window_start)
            .order_by(WebhookEvent.last_event_at.desc())
            .limit(1)
        )
        existing = result.scalar_one_or_none()
        if existing:
            # 重复到达：合并进原记录（失败记录同样抑制，重试时机由人工掌握）
            sources = list(existing.sources or [])
            if source and source not in sources:
                sources.append(source)
            existing.sources = sources
            existing.dup_count = (existing.dup_count or 0) + 1
            existing.last_event_at = now
            db.session.add(existing)
            await db.session.commit()
            return None

        record = WebhookEvent(
            event_key=key, action=action, file_path=file_path, is_dir=is_dir,
            sources=[source] if source else [], payload=payload,
            status="pending", attempts=1, parent_event_id=parent_event_id,
            first_seen_at=now, last_event_at=now, updated_at=now,
        )
        db.session.add(record)
        await db.session.commit()
        await db.session.refresh(record)
        return record


async def update_event(event_id: Optional[int], status: str = None,
                       error_message: str = None, task_id: str = None):
    """更新台账记录的执行状态（event_id 为空或台账关闭时静默跳过）。"""
    if not event_id or not ledger_enabled():
        return
    try:
        async with db.session_scope(force_new=True):
            result = await db.session.execute(select(WebhookEvent).where(WebhookEvent.id == event_id))
            record = result.scalar_one_or_none()
            if not record:
                return
            if status:
                record.status = status
            if error_message is not None:
                record.error_message = error_message
            if task_id:
                record.task_id = task_id
            record.updated_at = datetime.now()
            db.session.add(record)
            await db.session.commit()
    except Exception as e:
        logger.warning(f"[联动记录] 更新事件状态失败 (id={event_id}): {e}")


async def mark_replaying(event_id: int) -> Optional[WebhookEvent]:
    """手动重放前置：attempts +1、状态回 processing。返回记录供重放链路复用。"""
    async with db.session_scope(force_new=True):
        result = await db.session.execute(select(WebhookEvent).where(WebhookEvent.id == event_id))
        record = result.scalar_one_or_none()
        if not record:
            return None
        record.attempts = (record.attempts or 0) + 1
        record.status = "processing"
        record.error_message = None
        record.updated_at = datetime.now()
        db.session.add(record)
        await db.session.commit()
        await db.session.refresh(record)
        return record


async def add_related_task(event_id: Optional[int], task_id: str):
    """后续链路（队列 STRM 处理、目录展开等）产生的任务记录回链到事件。"""
    if not event_id or not task_id or not ledger_enabled():
        return
    try:
        async with db.session_scope(force_new=True):
            result = await db.session.execute(select(WebhookEvent).where(WebhookEvent.id == event_id))
            record = result.scalar_one_or_none()
            if not record:
                return
            related = list(record.related_task_ids or [])
            if task_id not in related:
                related.append(task_id)
                record.related_task_ids = related
                db.session.add(record)
                await db.session.commit()
    except Exception as e:
        logger.warning(f"[联动记录] 关联任务回链失败 (event={event_id}, task={task_id}): {e}")


async def get_event_logs(event_id: int) -> Optional[List[Dict[str, Any]]]:
    """聚合事件全链路的任务中心日志：webhook 接收任务 + 关联的队列处理/目录展开任务。"""
    event = await get_event(event_id)
    if not event:
        return None
    task_ids = []
    if event.get("task_id"):
        task_ids.append(event["task_id"])
    task_ids.extend(t for t in (event.get("related_task_ids") or []) if t not in task_ids)

    from task_history import get_task_detail
    logs = []
    for tid in task_ids:
        detail = await get_task_detail(tid)
        if detail:
            logs.append({
                "task_id": detail["task_id"],
                "module": detail["module"],
                "name": detail["name"],
                "status": detail["status"],
                "started_at": detail["started_at"],
                "logs": detail["logs"],
            })
    return logs


async def get_event(event_id: int) -> Optional[Dict[str, Any]]:
    async with db.session_scope(force_new=True):
        result = await db.session.execute(select(WebhookEvent).where(WebhookEvent.id == event_id))
        record = result.scalar_one_or_none()
        return _to_dict(record) if record else None


async def list_events(limit: int = 50, offset: int = 0, status: str = None, source: str = None,
                      search: str = None, start_time: datetime = None, end_time: datetime = None,
                      parent_id: int = None) -> List[Dict[str, Any]]:
    async with db.session_scope(force_new=True):
        query = _apply_filters(
            select(WebhookEvent).order_by(WebhookEvent.first_seen_at.desc()).limit(limit).offset(offset),
            status=status, source=source, search=search,
            start_time=start_time, end_time=end_time, parent_id=parent_id,
        )
        result = await db.session.execute(query)
        return [_to_dict(r) for r in result.scalars().all()]


def _apply_filters(query, status: str = None, source: str = None, search: str = None,
                   start_time: datetime = None, end_time: datetime = None, parent_id: int = None):
    """列表/计数/批量操作共用的筛选条件。"""
    if status:
        query = query.where(WebhookEvent.status == status)
    if source:
        # sources 为 JSONB 数组， containment 匹配（如同时被双通道确认的事件）
        query = query.where(WebhookEvent.sources.contains([source]))
    if search:
        query = query.where(WebhookEvent.file_path.ilike(f"%{search}%"))
    if start_time:
        query = query.where(WebhookEvent.first_seen_at >= start_time)
    if end_time:
        query = query.where(WebhookEvent.first_seen_at <= end_time)
    if parent_id is not None:
        query = query.where(WebhookEvent.parent_event_id == parent_id)
    return query


async def get_event_ids(status: str = None, source: str = None, search: str = None,
                        start_time: datetime = None, end_time: datetime = None,
                        limit: int = 500) -> List[int]:
    """按筛选条件取事件 id 列表（批量重放用，按时间倒序）。"""
    async with db.session_scope(force_new=True):
        query = _apply_filters(
            select(WebhookEvent.id).order_by(WebhookEvent.first_seen_at.desc()).limit(limit),
            status=status, source=source, search=search, start_time=start_time, end_time=end_time,
        )
        result = await db.session.execute(query)
        return [r[0] for r in result.all()]


async def count_events(status: str = None, source: str = None, search: str = None,
                       start_time: datetime = None, end_time: datetime = None) -> int:
    async with db.session_scope(force_new=True):
        query = _apply_filters(select(func.count(WebhookEvent.id)),
                               status=status, source=source, search=search,
                               start_time=start_time, end_time=end_time)
        result = await db.session.execute(query)
        return result.scalar() or 0


async def get_stats() -> Dict[str, Any]:
    """状态分布统计 + 今日新增。"""
    async with db.session_scope(force_new=True):
        result = await db.session.execute(
            select(WebhookEvent.status, func.count(WebhookEvent.id)).group_by(WebhookEvent.status)
        )
        by_status = {s: c for s, c in result.all()}

        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_result = await db.session.execute(
            select(func.count(WebhookEvent.id)).where(WebhookEvent.first_seen_at >= today_start)
        )
        today_total = today_result.scalar() or 0
        today_failed_result = await db.session.execute(
            select(func.count(WebhookEvent.id)).where(
                WebhookEvent.first_seen_at >= today_start, WebhookEvent.status == "failed")
        )
        return {
            "by_status": by_status,
            "total": sum(by_status.values()),
            "today_total": today_total,
            "today_failed": today_failed_result.scalar() or 0,
        }


async def delete_event(event_id: int) -> bool:
    async with db.session_scope(force_new=True):
        result = await db.session.execute(delete(WebhookEvent).where(WebhookEvent.id == event_id))
        await db.session.commit()
        return result.rowcount > 0


async def clear_events(status: str = None, source: str = None, search: str = None,
                       start_time: datetime = None, end_time: datetime = None,
                       before_days: int = None) -> int:
    """批量清理：与列表共用同一套筛选条件（保证"清理"范围 = "重放"范围 = 筛选范围）。"""
    async with db.session_scope(force_new=True):
        query = _apply_filters(delete(WebhookEvent), status=status, source=source, search=search,
                               start_time=start_time, end_time=end_time)
        if before_days is not None:
            query = query.where(WebhookEvent.first_seen_at < datetime.now() - timedelta(days=before_days))
        result = await db.session.execute(query)
        await db.session.commit()
        return result.rowcount or 0


async def cleanup_old_events(retention_days: int = 90):
    """定期清理（挂在任务记录清理的每日巡检里执行）。"""
    if not ledger_enabled():
        return 0
    return await clear_events(before_days=retention_days)


def _to_dict(record: WebhookEvent) -> Dict[str, Any]:
    return {
        "id": record.id,
        "event_key": record.event_key,
        "action": record.action,
        "file_path": record.file_path,
        "is_dir": record.is_dir,
        "sources": record.sources or [],
        "payload": record.payload,
        "status": record.status,
        "error_message": record.error_message,
        "attempts": record.attempts,
        "dup_count": record.dup_count,
        "parent_event_id": record.parent_event_id,
        "task_id": record.task_id,
        "related_task_ids": record.related_task_ids or [],
        "first_seen_at": record.first_seen_at.isoformat() if record.first_seen_at else None,
        "last_event_at": record.last_event_at.isoformat() if record.last_event_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }
