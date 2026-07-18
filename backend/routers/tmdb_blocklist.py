from fastapi import APIRouter, HTTPException
from typing import List
from sqlmodel import select

from models import TmdbBlocklist
from database import db
from logger import log_audit

router = APIRouter(tags=["TMDB屏蔽列表"])


@router.get("/tmdb-blocklist", response_model=List[TmdbBlocklist], summary="获取 TMDB 屏蔽列表")
async def get_tmdb_blocklist():
    async with db.session_scope():
        stmt = select(TmdbBlocklist).order_by(TmdbBlocklist.created_at.desc())
        return await db.all(TmdbBlocklist, stmt)


@router.post("/tmdb-blocklist", summary="添加 TMDB 屏蔽条目")
async def add_tmdb_blocklist(item: TmdbBlocklist):
    async with db.session_scope():
        # 检查是否已存在（同 tmdb_id + media_type）
        stmt = select(TmdbBlocklist).where(
            TmdbBlocklist.tmdb_id == item.tmdb_id,
            TmdbBlocklist.media_type == item.media_type
        )
        if await db.first(TmdbBlocklist, stmt):
            raise HTTPException(
                status_code=400,
                detail=f"TMDB ID {item.tmdb_id} ({item.media_type}) 已在屏蔽列表中"
            )

        item.id = None
        saved = await db.save(item)
        log_audit("TMDB屏蔽", "添加", f"添加屏蔽: tmdb_id={item.tmdb_id}, 类型={item.media_type}, 备注={item.title or ''}")
        return saved


@router.delete("/tmdb-blocklist/{item_id}", summary="删除 TMDB 屏蔽条目")
async def delete_tmdb_blocklist(item_id: int):
    async with db.session_scope():
        item = await db.get(TmdbBlocklist, item_id)
        if not item:
            raise HTTPException(status_code=404, detail="屏蔽条目不存在")

        await db.delete(item)
        log_audit("TMDB屏蔽", "删除", f"删除屏蔽: tmdb_id={item.tmdb_id}, 类型={item.media_type}")
        return {"success": True}
