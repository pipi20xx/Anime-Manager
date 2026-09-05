from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from sqlmodel import select

from models import TmdbBlocklist
from database import db
from logger import log_audit
from tmdbmatefull.models import TmdbDeepMeta

router = APIRouter(tags=["TMDB屏蔽列表"])


@router.get("/tmdb-blocklist", summary="获取 TMDB 屏蔽列表")
async def get_tmdb_blocklist():
    """获取屏蔽列表，并关联数据中心查出对应的名称。"""
    async with db.session_scope():
        stmt = select(TmdbBlocklist).order_by(TmdbBlocklist.created_at.desc())
        items = await db.all(TmdbBlocklist, stmt)

        # ── 批量从数据中心查出名称 ──
        meta_map: Dict[str, str] = {}
        if items:
            pairs = [(i.tmdb_id, i.media_type) for i in items]
            meta_stmt = select(TmdbDeepMeta).where(
                TmdbDeepMeta.tmdb_id.in_([p[0] for p in pairs])
            )
            metas = await db.all(TmdbDeepMeta, meta_stmt)
            for m in metas:
                meta_map[f"{m.tmdb_id}:{m.media_type}"] = m.custom_title or m.title or ""

        result = []
        for item in items:
            d = item.model_dump()
            key = f"{item.tmdb_id}:{item.media_type}"
            d["resolved_title"] = meta_map.get(key, "")
            result.append(d)
        return result


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
