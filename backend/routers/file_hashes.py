from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import asyncio
import os
from sqlmodel import select, desc, func

from database import db
from models import FileHash
from utils.hash_calculator import HashCalculator
from recognition.recognizer import MovieRecognizer
from logger import log_audit

router = APIRouter(prefix="/api/file_hashes", tags=["文件哈希"])


def _country_str(val):
    """origin_country 落库归一：上游可能传 list（PG 数组列）或 str，file_hashes 表为逗号字符串列"""
    if isinstance(val, (list, tuple)):
        return ",".join(str(x).strip() for x in val if str(x).strip()) or None
    return val


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


class FileHashInfoUpdate(BaseModel):
    season: Optional[int] = Field(None, description="季号 (如 Specials 传 0), 传 null 清空")
    episode: Optional[str] = Field(None, description="集号, 传 null 清空")
    tmdb_id: Optional[str] = Field(None, description="TMDB ID, 传 null 清空")


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


@router.patch("/{hash_id}", summary="修正哈希记录的季集/TMDB ID", response_model=FileHashResponse)
async def update_file_hash_season_episode(hash_id: int, payload: FileHashInfoUpdate):
    """
    手动修正单条哈希记录的季号/集号/TMDB ID (如 Specials 的 S0)。
    字段传 null 表示清空。
    """
    async with db.session_scope() as session:
        item = await session.get(FileHash, hash_id)
        if not item:
            raise HTTPException(status_code=404, detail="记录不存在")
        item.season = payload.season
        item.episode = payload.episode
        item.tmdb_id = payload.tmdb_id
        session.add(item)
        await session.commit()
        await session.refresh(item)
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
    source_via: str = Field("local", description="路径归属域: local | cd2")
    client_id: Optional[str] = Field(None, description="CD2 客户端 ID (source_via=cd2 时可选)")
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
    本地路径直接读文件；CD2 云路径通过下载接口流式计算（不落盘）。
    """
    import posixpath

    hash_result = None

    if request.source_via == "cd2":
        # --- CD2 云路径：流式计算 ---
        try:
            from config_manager import ConfigManager
            from clients.manager import ClientManager
            config = ConfigManager.get_config()
            cd2_conf = next((c for c in config.get("download_clients", []) if c.get("type") == "cd2"), None)
            if request.client_id:
                cd2_conf = next((c for c in config.get("download_clients", [])
                                 if c.get("type") == "cd2" and c.get("id") == request.client_id), cd2_conf)
            if not cd2_conf:
                raise HTTPException(status_code=400, detail="未找到已配置的 CD2 客户端")
            cd2_client = ClientManager.get_client(cd2_conf.get("id"))
            if not cd2_client:
                raise HTTPException(status_code=400, detail="CD2 客户端初始化失败")

            browser = cd2_client._file_browser
            # 大小以下载响应的 Content-Length 为准（get_cloud_file_size 对单文件不可靠）
            resp, file_size = await asyncio.to_thread(browser.open_download_stream, request.file_path)
            try:
                hash_result = await HashCalculator.calculate_hashes_from_stream(
                    resp, file_size, posixpath.basename(request.file_path)
                )
            finally:
                await asyncio.to_thread(resp.close)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"云源哈希计算失败: {e}")

        if not hash_result:
            raise HTTPException(status_code=500, detail="哈希计算失败，请检查日志")
    else:
        # --- 本地路径 ---
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


class FixTitlesRequest(BaseModel):
    """一键修复标题请求"""
    ids: Optional[List[int]] = Field(None, description="指定记录 ID 列表，为空则修复全部")
    q: Optional[str] = Field(None, description="关键词搜索筛选")
    tmdb_id: Optional[str] = Field(None, description="按 TMDB ID 筛选")
    media_type: Optional[str] = Field(None, description="按媒体类型筛选 (tv/movie)")
    season: Optional[int] = Field(None, description="按季号筛选")
    team: Optional[str] = Field(None, description="按制作组筛选")


@router.post("/fix_titles", summary="一键修复标题：根据 TMDBID 和类型从数据中心补全标题")
async def fix_titles(request: FixTitlesRequest):
    """
    根据 file_hashes 表中记录的 tmdb_id 和 media_type，
    去数据中心的 metadata.tmdb_deep_meta 表查询正确标题（优先 custom_title），
    批量更新 file_hashes.title 字段。

    支持传入 ids 列表精确修复，或使用筛选条件批量修复。
    """
    from metadata.meta_cache import MetaCacheManager

    async with db.session_scope() as session:
        # 构建查询
        base_stmt = select(FileHash)

        filters = []
        if request.ids:
            filters.append(FileHash.id.in_(request.ids))
        if request.tmdb_id:
            filters.append(FileHash.tmdb_id == request.tmdb_id)
        if request.media_type:
            filters.append(FileHash.media_type == request.media_type)
        if request.season is not None:
            filters.append(FileHash.season == request.season)
        if request.team:
            filters.append(FileHash.team == request.team)
        if request.q:
            pattern = f"%{request.q}%"
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

        result = await session.execute(base_stmt)
        records = result.scalars().all()

        total = len(records)
        fixed = 0
        skipped = 0
        not_found = 0
        details = []

        for record in records:
            # 没有 tmdb_id 的记录跳过
            if not record.tmdb_id:
                skipped += 1
                details.append({
                    "id": record.id,
                    "original_filename": record.original_filename,
                    "status": "skipped",
                    "reason": "无 tmdb_id"
                })
                continue

            # 没有 media_type 的记录跳过
            if not record.media_type:
                skipped += 1
                details.append({
                    "id": record.id,
                    "original_filename": record.original_filename,
                    "status": "skipped",
                    "reason": "无 media_type"
                })
                continue

            # [重要] file_hashes.media_type 存的是中文 "电影"/"剧集"
            # 而数据中心 metadata.tmdb_deep_meta.media_type 存的是英文 "movie"/"tv"
            # 需要做映射转换
            raw_type = record.media_type.strip()
            if raw_type == "电影":
                dc_media_type = "movie"
            elif raw_type == "剧集":
                dc_media_type = "tv"
            elif raw_type in ("movie", "tv"):
                dc_media_type = raw_type
            else:
                skipped += 1
                details.append({
                    "id": record.id,
                    "original_filename": record.original_filename,
                    "tmdb_id": record.tmdb_id,
                    "media_type": record.media_type,
                    "status": "skipped",
                    "reason": f"无法识别的 media_type: {record.media_type}"
                })
                continue

            # 从数据中心查询元数据 (使用英文类型)
            key = f"{dc_media_type}:{record.tmdb_id}"
            meta = await MetaCacheManager.get(key)

            if not meta:
                not_found += 1
                details.append({
                    "id": record.id,
                    "original_filename": record.original_filename,
                    "tmdb_id": record.tmdb_id,
                    "media_type": record.media_type,
                    "status": "not_found",
                    "reason": f"数据中心未找到 {record.media_type}:{record.tmdb_id}"
                })
                continue

            # 获取正确标题（MetaCacheManager.get 已处理 custom_title 优先逻辑）
            correct_title = meta.get("title")
            if not correct_title:
                not_found += 1
                details.append({
                    "id": record.id,
                    "original_filename": record.original_filename,
                    "tmdb_id": record.tmdb_id,
                    "media_type": record.media_type,
                    "status": "not_found",
                    "reason": "元数据中无标题"
                })
                continue

            # 如果标题一致则跳过
            if record.title == correct_title:
                skipped += 1
                details.append({
                    "id": record.id,
                    "original_filename": record.original_filename,
                    "old_title": record.title,
                    "new_title": correct_title,
                    "status": "unchanged",
                    "reason": "标题已一致"
                })
                continue

            # 更新标题
            old_title = record.title
            record.title = correct_title
            fixed += 1
            details.append({
                "id": record.id,
                "original_filename": record.original_filename,
                "tmdb_id": record.tmdb_id,
                "media_type": record.media_type,
                "old_title": old_title,
                "new_title": correct_title,
                "status": "fixed"
            })

        await session.commit()

        log_audit("哈希", "一键修复标题", f"共 {total} 条, 修复 {fixed}, 跳过 {skipped}, 未找到 {not_found}", level="SUCCESS")

        return {
            "status": "success",
            "total": total,
            "fixed": fixed,
            "skipped": skipped,
            "not_found": not_found,
            "details": details,
        }


@router.post("/re_recognize", summary="重新识别并覆盖识别信息")
async def re_recognize_file_hashes(request: FixTitlesRequest):
    """
    对筛选范围内的哈希记录, 使用其源路径重新执行完整识别流程
    (文件名解析 + TMDB 匹配 + 深度元数据补全), 覆盖写回
    季集/TMDB ID/标题/识别信息等字段。文件无需真实存在于磁盘。
    注意: 会覆盖这些字段的现有值 (包括人工修改过的值)。
    """
    async with db.session_scope() as session:
        base_stmt = select(FileHash)

        filters = []
        if request.ids:
            filters.append(FileHash.id.in_(request.ids))
        if request.tmdb_id:
            filters.append(FileHash.tmdb_id == request.tmdb_id)
        if request.media_type:
            filters.append(FileHash.media_type == request.media_type)
        if request.season is not None:
            filters.append(FileHash.season == request.season)
        if request.team:
            filters.append(FileHash.team == request.team)
        if request.q:
            pattern = f"%{request.q}%"
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

        result = await session.execute(base_stmt)
        records = result.scalars().all()

        total = len(records)
        updated = 0
        skipped = 0
        errors = 0
        details = []

        for record in records:
            if not record.source_path:
                skipped += 1
                details.append({
                    "id": record.id,
                    "original_filename": record.original_filename,
                    "status": "skipped",
                    "reason": "无源路径"
                })
                continue

            try:
                result_data, _logs = await MovieRecognizer.recognize_full(
                    record.source_path,
                    original_input_path=record.source_path
                )
            except Exception as e:
                errors += 1
                details.append({
                    "id": record.id,
                    "original_filename": record.original_filename,
                    "source_path": record.source_path,
                    "status": "error",
                    "reason": f"识别异常: {str(e)}"
                })
                continue

            final = result_data.get("final_result", {}) if isinstance(result_data, dict) else {}

            if not final.get("tmdb_id"):
                skipped += 1
                details.append({
                    "id": record.id,
                    "original_filename": record.original_filename,
                    "source_path": record.source_path,
                    "status": "skipped",
                    "reason": "未能识别出 TMDB ID"
                })
                continue

            old_snapshot = {
                "title": record.title,
                "tmdb_id": record.tmdb_id,
                "season": record.season,
                "episode": record.episode,
            }

            # 字段映射与 organizer_core/processor.py 的哈希入库逻辑保持一致
            record.tmdb_id = str(final.get("tmdb_id"))
            record.title = final.get("title")
            record.season = final.get("season")
            record.episode = str(final.get("episode")) if final.get("episode") else None
            record.media_type = final.get("category")
            record.resolution = final.get("resolution")
            record.team = final.get("team")
            record.video_encode = final.get("video_encode")
            record.audio_encode = final.get("audio_encode")
            record.video_effect = final.get("video_effect")
            record.source = final.get("source")
            record.subtitle = final.get("subtitle")
            record.platform = final.get("platform")
            record.year = str(final.get("year")) if final.get("year") else None
            record.secondary_category = final.get("secondary_category")
            record.origin_country = _country_str(final.get("origin_country"))
            record.release_date = final.get("release_date")

            updated += 1
            details.append({
                "id": record.id,
                "original_filename": record.original_filename,
                "source_path": record.source_path,
                "old_title": old_snapshot["title"],
                "new_title": record.title,
                "old_tmdb_id": old_snapshot["tmdb_id"],
                "new_tmdb_id": record.tmdb_id,
                "old_season": old_snapshot["season"],
                "new_season": record.season,
                "old_episode": old_snapshot["episode"],
                "new_episode": record.episode,
                "status": "updated"
            })

        await session.commit()

        log_audit("哈希", "重新识别", f"共 {total} 条, 更新 {updated}, 跳过 {skipped}, 失败 {errors}", level="SUCCESS")

        return {
            "status": "success",
            "total": total,
            "updated": updated,
            "skipped": skipped,
            "errors": errors,
            "details": details,
        }
