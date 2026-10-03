from typing import Optional

from fastapi import APIRouter, Query, HTTPException
from sqlmodel import select, func as sqlfunc
from sqlalchemy import delete as sa_delete

from database import db
from models import NotificationRecord

router = APIRouter(prefix="/api/notifications", tags=["通知中心"])


@router.get("", summary="通知记录列表")
async def list_records(
    limit: int = Query(30, ge=1, le=200),
    offset: int = Query(0, ge=0),
    event_type: Optional[str] = Query(None, description="按事件类型筛选"),
    status: Optional[str] = Query(None, description="success / failed"),
):
    """分页获取发送到通知渠道的消息记录（含完整渲染内容）。"""
    async with db.session_scope():
        stmt = select(NotificationRecord)
        if event_type:
            stmt = stmt.where(NotificationRecord.event_type == event_type)
        if status:
            stmt = stmt.where(NotificationRecord.status == status)
        total_res = await db.execute(select(sqlfunc.count()).select_from(stmt.subquery()))
        total = total_res.scalar() or 0

        stmt = stmt.order_by(NotificationRecord.id.desc()).offset(offset).limit(limit)
        rows = (await db.execute(stmt)).scalars().all()

    return {"items": [r.model_dump() for r in rows], "total": total}


@router.delete("/{record_id}", summary="删除单条通知记录")
async def delete_record(record_id: int):
    async with db.session_scope():
        record = await db.get(NotificationRecord, record_id)
        if not record:
            raise HTTPException(status_code=404, detail="记录不存在")
        await db.delete(record, audit=False)
    return {"status": "success", "message": "记录已删除"}


@router.delete("", summary="清空全部通知记录")
async def clear_records():
    async with db.session_scope():
        await db.execute(sa_delete(NotificationRecord))
    return {"status": "success", "message": "通知记录已清空"}
