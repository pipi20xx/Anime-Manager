import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from sqlalchemy import select, delete
from sqlalchemy.sql import func

from database import db
from models import TaskRecord

_log_buffer: Dict[str, List[Dict]] = {}
MAX_LOGS_PER_TASK = 500

async def start_task(task_id: str, module: str, name: str = None):
    async with db.session_scope(force_new=True):
        record = TaskRecord(task_id=task_id, module=module, name=name, logs=[])
        db.session.add(record)
        await db.session.commit()
    _log_buffer[task_id] = []

async def log_task(task_id: str, message: str, level: str = "INFO"):
    if task_id not in _log_buffer:
        _log_buffer[task_id] = []
    
    logs = _log_buffer[task_id]
    logs.append({
        "time": datetime.now().strftime("%H:%M:%S"),
        "level": level,
        "message": message
    })
    
    if len(logs) > MAX_LOGS_PER_TASK:
        _log_buffer[task_id] = logs[-MAX_LOGS_PER_TASK:]

async def finish_task(task_id: str, status: str, processed: int = 0, stats: Dict[str, Any] = None):
    logs = _log_buffer.pop(task_id, [])
    
    async with db.session_scope(force_new=True):
        result = await db.session.execute(
            select(TaskRecord).where(TaskRecord.task_id == task_id)
        )
        record = result.scalar_one_or_none()
        if record:
            record.status = status
            record.finished_at = datetime.now()
            record.processed = processed
            record.logs = logs[-MAX_LOGS_PER_TASK:]
            if stats:
                record.stats = stats
            db.session.add(record)
            await db.session.commit()

async def get_task_list(limit: int = 50, offset: int = 0, module: str = None) -> List[Dict]:
    async with db.session_scope(force_new=True):
        query = select(TaskRecord).order_by(TaskRecord.started_at.desc()).limit(limit).offset(offset)
        if module:
            query = query.where(TaskRecord.module == module)
        result = await db.session.execute(query)
        records = result.scalars().all()
        return [{
            "id": r.id,
            "task_id": r.task_id,
            "module": r.module,
            "name": r.name,
            "status": r.status,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            "processed": r.processed,
            "log_count": len(r.logs) if r.logs else 0,
            "stats": r.stats or {}
        } for r in records]

async def get_task_detail(task_id: str) -> Optional[Dict]:
    async with db.session_scope(force_new=True):
        result = await db.session.execute(
            select(TaskRecord).where(TaskRecord.task_id == task_id)
        )
        record = result.scalar_one_or_none()
        if not record:
            return None
        return {
            "id": record.id,
            "task_id": record.task_id,
            "module": record.module,
            "name": record.name,
            "status": record.status,
            "started_at": record.started_at.isoformat() if record.started_at else None,
            "finished_at": record.finished_at.isoformat() if record.finished_at else None,
            "processed": record.processed,
            "logs": record.logs or [],
            "stats": record.stats or {}
        }

async def delete_task(task_id: str) -> bool:
    async with db.session_scope(force_new=True):
        result = await db.session.execute(
            delete(TaskRecord).where(TaskRecord.task_id == task_id)
        )
        await db.session.commit()
        return result.rowcount > 0

async def cleanup_old_tasks(max_records: int = 500, max_days: int = 30):
    async with db.session_scope(force_new=True):
        limit_date = datetime.now() - timedelta(days=max_days)
        deleted_time = await db.session.execute(
            delete(TaskRecord).where(
                TaskRecord.started_at < limit_date
            )
        )
        
        subq = select(TaskRecord.id).order_by(TaskRecord.started_at.desc()).limit(max_records)
        deleted_count = await db.session.execute(
            delete(TaskRecord).where(TaskRecord.id.not_in(subq))
        )
        
        await db.session.commit()
        return deleted_time.rowcount + deleted_count.rowcount
