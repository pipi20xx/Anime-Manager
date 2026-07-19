from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from sqlmodel import select, desc, func

from database import db
from models import FileHash
from utils.hash_calculator import HashCalculator
from logger import log_audit

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
    audio_encode: Optional[str]
    video_effect: Optional[str]
    source: Optional[str]
    subtitle: Optional[str]
    platform: Optional[str]
    year: Optional[str]
    secondary_category: Optional[str]
    origin_country: Optional[str]
    release_date: Optional[str]
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
    team: Optional[str] = Query(None, description="按制作组筛选"),
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
        if team:
            filters.append(FileHash.team == team)

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


class SingleFileHashRequest(BaseModel):
    file_path: str = Field(..., description="文件的绝对路径")
    tmdb_id: Optional[str] = Field(None, description="TMDB ID")
    title: Optional[str] = Field(None, description="标题")
    season: Optional[int] = Field(None, description="季号")
    episode: Optional[str] = Field(None, description="集数")
    media_type: Optional[str] = Field(None, description="媒体类型 (tv/movie)")
    resolution: Optional[str] = Field(None, description="分辨率")
    team: Optional[str] = Field(None, description="制作组")
    video_encode: Optional[str] = Field(None, description="视频编码")
    audio_encode: Optional[str] = Field(None, description="音频编码")
    video_effect: Optional[str] = Field(None, description="视频特效 (HDR/DV等)")
    source: Optional[str] = Field(None, description="介质来源 (WEB-DL/Blu-ray等)")
    subtitle: Optional[str] = Field(None, description="字幕语言")
    platform: Optional[str] = Field(None, description="发布平台")
    year: Optional[str] = Field(None, description="年份")
    secondary_category: Optional[str] = Field(None, description="二级分类")
    origin_country: Optional[str] = Field(None, description="原产地")
    release_date: Optional[str] = Field(None, description="发布日期")


@router.post("/calculate", summary="计算单文件哈希并入库")
async def calculate_single_file_hash(request: SingleFileHashRequest):
    """
    对指定文件计算 SHA1 和 ED2K 哈希值，并按 ED2K 去重后存入数据库。
    支持同时传入识别结果信息（标题、季集等）一起写入。
    如果该文件的 ED2K 哈希已存在，则更新记录。
    """
    import os
    if not os.path.exists(request.file_path):
        raise HTTPException(status_code=404, detail=f"文件不存在: {request.file_path}")
    if not os.path.isfile(request.file_path):
        raise HTTPException(status_code=400, detail=f"路径不是文件: {request.file_path}")

    hash_result = await HashCalculator.calculate_hashes(request.file_path)
    if not hash_result:
        raise HTTPException(status_code=500, detail="哈希计算失败，请检查文件权限或日志")

    async with db.session_scope() as session:
        stmt = select(FileHash).where(FileHash.ed2k == hash_result.ed2k)
        result = await session.execute(stmt)
        existing = result.scalars().first()

        if existing:
            existing.sha1 = hash_result.sha1
            existing.ed2k_link = hash_result.ed2k_link
            existing.original_filename = hash_result.filename
            existing.file_size = hash_result.file_size
            existing.source_path = hash_result.file_path
            existing.calculated_at = datetime.now()
            if request.tmdb_id is not None:
                existing.tmdb_id = request.tmdb_id
            if request.title is not None:
                existing.title = request.title
            if request.season is not None:
                existing.season = request.season
            if request.episode is not None:
                existing.episode = request.episode
            if request.media_type is not None:
                existing.media_type = request.media_type
            if request.resolution is not None:
                existing.resolution = request.resolution
            if request.team is not None:
                existing.team = request.team
            if request.video_encode is not None:
                existing.video_encode = request.video_encode
            if request.audio_encode is not None:
                existing.audio_encode = request.audio_encode
            if request.video_effect is not None:
                existing.video_effect = request.video_effect
            if request.source is not None:
                existing.source = request.source
            if request.subtitle is not None:
                existing.subtitle = request.subtitle
            if request.platform is not None:
                existing.platform = request.platform
            if request.year is not None:
                existing.year = request.year
            if request.secondary_category is not None:
                existing.secondary_category = request.secondary_category
            if request.origin_country is not None:
                existing.origin_country = request.origin_country
            if request.release_date is not None:
                existing.release_date = request.release_date
            await session.commit()
            await session.refresh(existing)
            log_audit("哈希", "入库成功", f"{hash_result.filename} (已更新)", level="SUCCESS")
            return {"status": "success", "message": "哈希记录已更新", "data": existing}
        else:
            new_record = FileHash(
                sha1=hash_result.sha1,
                ed2k=hash_result.ed2k,
                ed2k_link=hash_result.ed2k_link,
                original_filename=hash_result.filename,
                file_size=hash_result.file_size,
                source_path=hash_result.file_path,
                tmdb_id=request.tmdb_id,
                title=request.title,
                season=request.season,
                episode=request.episode,
                media_type=request.media_type,
                resolution=request.resolution,
                team=request.team,
                video_encode=request.video_encode,
                audio_encode=request.audio_encode,
                video_effect=request.video_effect,
                source=request.source,
                subtitle=request.subtitle,
                platform=request.platform,
                year=request.year,
                secondary_category=request.secondary_category,
                origin_country=request.origin_country,
                release_date=request.release_date,
            )
            session.add(new_record)
            await session.commit()
            await session.refresh(new_record)
            log_audit("哈希", "入库成功", f"{hash_result.filename} (新建)", level="SUCCESS")
            return {"status": "success", "message": "哈希记录已创建", "data": new_record}
