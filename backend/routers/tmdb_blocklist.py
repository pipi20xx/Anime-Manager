from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from sqlmodel import select

from models import TmdbBlocklist
from database import db
from logger import log_audit
from rss_core.field_match import FIELD_MATCH_STRATEGY
from tmdbmatefull.models import TmdbDeepMeta

router = APIRouter(tags=["TMDB屏蔽列表"])


def _sanitize_conditions(conditions: Any) -> Dict[str, str]:
    """只保留 field_match 支持的规格字段，剔除空白值；全部为空则返回空 dict。"""
    if not isinstance(conditions, dict):
        return {}
    cleaned = {
        k: str(v).strip()
        for k, v in conditions.items()
        if k in FIELD_MATCH_STRATEGY and str(v or "").strip()
    }
    return cleaned


@router.get("/tmdb-blocklist", summary="获取 TMDB 屏蔽列表")
async def get_tmdb_blocklist():
    """获取屏蔽列表，并关联数据中心查出对应的名称。"""
    async with db.session_scope():
        stmt = select(TmdbBlocklist).order_by(TmdbBlocklist.created_at.desc())
        items = await db.all(TmdbBlocklist, stmt)

        # ── 批量从数据中心查出名称（全局条件条目无 tmdb_id，跳过反查） ──
        meta_map: Dict[str, str] = {}
        if items:
            pairs = [(i.tmdb_id, i.media_type) for i in items if i.tmdb_id]
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
        # 归一化：tmdb_id 去空白，兼容 * / any / 任意 等哨兵写法 -> 留空（全局条件屏蔽）
        item.tmdb_id = str(item.tmdb_id or "").strip()
        if item.tmdb_id in ("*", "any", "ANY", "任意"):
            item.tmdb_id = ""
        if item.media_type not in ("tv", "movie", "all"):
            item.media_type = "tv"
        item.conditions = _sanitize_conditions(item.conditions)

        # 全局条件条目（不锚定作品）必须至少有一个规格条件，否则会拦下一切资源
        if not item.tmdb_id and not item.conditions:
            raise HTTPException(
                status_code=400,
                detail="留空 TMDB ID 时必须至少填写一个规格条件（如制作组）"
            )

        # 锚定作品的条目按 tmdb_id + media_type 去重；全局条件条目允许多条并存
        if item.tmdb_id:
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
        item.conditions = item.conditions or None
        saved = await db.save(item)
        cond_desc = ", ".join(f"{k}={v}" for k, v in (item.conditions or {}).items())
        scope = f"tmdb_id={item.tmdb_id}, 类型={item.media_type}" if item.tmdb_id else "全局条件(不锚定作品)"
        log_audit("TMDB屏蔽", "添加", f"添加屏蔽: {scope}, 条件={cond_desc or '整部作品'}, 备注={item.title or ''}")
        return saved


@router.put("/tmdb-blocklist/{item_id}", summary="编辑 TMDB 屏蔽条目")
async def update_tmdb_blocklist(item_id: int, data: TmdbBlocklist):
    async with db.session_scope():
        existing = await db.get(TmdbBlocklist, item_id)
        if not existing:
            raise HTTPException(status_code=404, detail="屏蔽条目不存在")

        # 归一化规则与添加时一致（title/reason 备注不在编辑范围，保持原值）
        existing.tmdb_id = str(data.tmdb_id or "").strip()
        if existing.tmdb_id in ("*", "any", "ANY", "任意"):
            existing.tmdb_id = ""
        if data.media_type in ("tv", "movie", "all"):
            existing.media_type = data.media_type
        else:
            existing.media_type = "tv"
        existing.conditions = _sanitize_conditions(data.conditions) or None

        # 全局条件条目（不锚定作品）必须至少有一个规格条件，否则会拦下一切资源
        if not existing.tmdb_id and not existing.conditions:
            raise HTTPException(
                status_code=400,
                detail="留空 TMDB ID 时必须至少填写一个规格条件（如制作组）"
            )

        # 锚定作品的条目按 tmdb_id + media_type 去重（排除自身）；全局条件条目允许多条并存
        if existing.tmdb_id:
            stmt = select(TmdbBlocklist).where(
                TmdbBlocklist.tmdb_id == existing.tmdb_id,
                TmdbBlocklist.media_type == existing.media_type,
                TmdbBlocklist.id != item_id
            )
            if await db.first(TmdbBlocklist, stmt):
                raise HTTPException(
                    status_code=400,
                    detail=f"TMDB ID {existing.tmdb_id} ({existing.media_type}) 已在屏蔽列表中"
                )

        saved = await db.save(existing)
        cond_desc = ", ".join(f"{k}={v}" for k, v in (existing.conditions or {}).items())
        scope = f"tmdb_id={existing.tmdb_id}, 类型={existing.media_type}" if existing.tmdb_id else "全局条件(不锚定作品)"
        log_audit("TMDB屏蔽", "编辑", f"编辑屏蔽 #{item_id}: {scope}, 条件={cond_desc or '整部作品'}")
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
