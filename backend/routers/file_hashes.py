from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from sqlmodel import select, desc, func

from database import db
from models import FileHash

router = APIRouter(prefix="/api/file_hashes", tags=["文件哈希"])


class FileHashResponse(BaseModel):
    id: int
    sha1: str
    ed2k: str
    ed2k_link: str
    original_filename: str
    file_size: Optional[int]
    tmdb_id: Optional[str]
    title: Optional[str]
    season: Optional[int]
    episode: Optional[str]
    media_type: Optional[str]
    resolution: Optional[str]
    team: Optional[str]
    video_encode: Optional[str]
    source_path: str
    target_path: Optional[str]
    calculated_at: datetime

    class Config:
        from_attributes = True


class FileHashListResponse(BaseModel):
    status: str = "success"
    total: int
    limit: int
    offset: int
    data: List[FileHashResponse]


@router.get("", summary="查询文件哈希列表", response_model=FileHashListResponse)
async def list_file_hashes(
    q: Optional[str] = Query(None, description="关键词搜索：文件名、标题、ED2K、SHA1、路径"),
    tmdb_id: Optional[str] = Query(None, description="按 TMDB ID 筛选"),
    media_type: Optional[str] = Query(None, description="按媒体类型筛选 (tv/movie)"),
    season: Optional[int] = Query(None, description="按季号筛选"),
    limit: int = Query(50, ge=1, le=500, description="每页数量"),
    offset: int = Query(0, ge=0, description="分页偏移量"),
    sort_by: str = Query("calculated_at", description="排序字段"),
    sort_order: str = Query("desc", description="排序方向 (asc/desc)"),
):
    """
    查询已计算并存储的文件 ED2K/SHA1 哈希记录。
    支持关键词搜索、多字段筛选、分页和排序。
    """
    async with db.session_scope() as session:
        base_stmt = select(FileHash)
        count_stmt = select(func.count(FileHash.id))

        filters = []

        if tmdb_id:
            filters.append(FileHash.tmdb_id == tmdb_id)
        if media_type:
            filters.append(FileHash.media_type == media_type)
        if season is not None:
            filters.append(FileHash.season == season)

        if q:
            pattern = f"%{q}%"
            filters.append(
                FileHash.original_filename.ilike(pattern)
                | FileHash.title.ilike(pattern)
                | FileHash.ed2k.ilike(pattern)
                | FileHash.sha1.ilike(pattern)
                | FileHash.source_path.ilike(pattern)
                | FileHash.target_path.ilike(pattern)
            )

        if filters:
            base_stmt = base_stmt.where(*filters)
            count_stmt = count_stmt.where(*filters)

        # 排序
        order_col = getattr(FileHash, sort_by, FileHash.calculated_at)
        if sort_order.lower() == "asc":
            base_stmt = base_stmt.order_by(order_col.asc())
        else:
            base_stmt = base_stmt.order_by(desc(order_col))

        # 分页
        base_stmt = base_stmt.offset(offset).limit(limit)

        result = await session.execute(base_stmt)
        count_result = await session.execute(count_stmt)

        items = result.scalars().all()
        total = count_result.scalar() or 0

        return {
            "status": "success",
            "total": total,
            "limit": limit,
            "offset": offset,
            "data": items,
        }


@router.get("/{hash_id}", summary="获取单条哈希记录", response_model=FileHashResponse)
async def get_file_hash(hash_id: int):
    """
    根据数据库主键 ID 获取单条文件哈希记录。
    """
    async with db.session_scope() as session:
        item = await session.get(FileHash, hash_id)
        if not item:
            raise HTTPException(status_code=404, detail="记录不存在")
        return item


@router.get("/ed2k/{ed2k_hash}", summary="按 ED2K 哈希查询")
async def get_file_hash_by_ed2k(ed2k_hash: str):
    """
    根据 ED2K 哈希值查询单条文件记录（精确匹配）。
    """
    async with db.session_scope() as session:
        stmt = select(FileHash).where(FileHash.ed2k == ed2k_hash)
        result = await session.execute(stmt)
        item = result.scalars().first()
        if not item:
            raise HTTPException(status_code=404, detail="记录不存在")
        return {"status": "success", "data": item}


@router.get("/sha1/{sha1_hash}", summary="按 SHA1 哈希查询")
async def get_file_hash_by_sha1(sha1_hash: str):
    """
    根据 SHA1 哈希值查询单条文件记录（精确匹配）。
    """
    async with db.session_scope() as session:
        stmt = select(FileHash).where(FileHash.sha1 == sha1_hash)
        result = await session.execute(stmt)
        item = result.scalars().first()
        if not item:
            raise HTTPException(status_code=404, detail="记录不存在")
        return {"status": "success", "data": item}
