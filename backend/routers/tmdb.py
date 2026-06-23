import asyncio
from datetime import datetime, timedelta
from typing import Dict, Tuple, Any
from fastapi import APIRouter, HTTPException
from recognition.data_provider.tmdb.client import TMDBProvider
from tmdbmatefull.database import DEFAULT_GENRE_MAPPINGS
from logger import log_audit

router = APIRouter(prefix="/api/tmdb", tags=["TMDB 云端数据"])

# Emby 查询内存缓存 (5 分钟 TTL)
_emby_cache: Dict[str, Tuple[Any, datetime]] = {}
_emby_cache_ttl = timedelta(minutes=5)

# 流派 ID 到中文名称的映射
_GENRE_MAP: Dict[int, str] = {g["id"]: g["name_zh"] for g in DEFAULT_GENRE_MAPPINGS}


def _get_emby_cache(key: str) -> Any:
    if key in _emby_cache:
        data, expire_at = _emby_cache[key]
        if expire_at > datetime.now():
            return data
        del _emby_cache[key]
    return None


def _set_emby_cache(key: str, data: Any):
    _emby_cache[key] = (data, datetime.now() + _emby_cache_ttl)

@router.get("/trending", summary="获取动漫趋势")
async def get_trending():
    """
    获取当前 TMDB 上的热门日本动漫。
    """
    logs = []
    res = await TMDBProvider().get_trending()
    # Trending 逻辑内部目前不直接支持传 logs 到子请求，但我们可以记录总审计
    log_audit("TMDB", "看板", "获取趋势列表")
    return res

@router.get("/popular/{media_type}", summary="获取二次元分类榜单")
async def get_popular(media_type: str):
    """
    按分类获取热门日本动漫榜单。
    """
    if media_type not in ["movie", "tv"]:
        return {"results": []}
    res = await TMDBProvider().get_popular(media_type)
    log_audit("TMDB", "看板", f"获取热门列表: {media_type}")
    return res

@router.get("/detail/{media_type}/{tmdb_id}", summary="获取作品详细元数据")
async def get_detail(media_type: str, tmdb_id: str):
    """
    获取指定作品的详细信息。
    """
    logs = []
    result = await TMDBProvider().get_subject_details(tmdb_id, media_type, logs=logs)
    if not result:
        log_audit("TMDB", "详情", f"获取失败: {media_type}/{tmdb_id}", details="\n".join(logs), level="ERROR")
        raise HTTPException(status_code=404, detail="TMDB 内容未找到")
    
    log_audit("TMDB", "详情", f"获取成功: {result.get('title')}", details="\n".join(logs))
    return result

@router.get("/detail/{media_type}/{tmdb_id}/emby", summary="获取作品在Emby库中的状态")
async def get_detail_emby_status(media_type: str, tmdb_id: str):
    """
    获取指定作品在 Emby 库中的入库状态。
    """
    cache_key = f"emby:status:{media_type}:{tmdb_id}"
    cached = _get_emby_cache(cache_key)
    if cached is not None:
        return cached

    def _fetch():
        from emby_client import get_emby_client
        emby = get_emby_client()
        if media_type == 'movie':
            return emby.get_movie_info(tmdb_id)
        else:
            return emby.get_series_library_status(tmdb_id)

    result = await asyncio.to_thread(_fetch)
    _set_emby_cache(cache_key, result)
    return result

@router.get("/recommendations/{media_type}/{tmdb_id}", summary="获取推荐内容")
async def get_recommendations(media_type: str, tmdb_id: str):
    """
    获取指定作品的推荐内容。
    """
    result = await TMDBProvider().get_recommendations(tmdb_id, media_type)
    log_audit("TMDB", "推荐", f"获取推荐: {media_type}/{tmdb_id}")
    return result

@router.get("/season/{tmdb_id}/{season_number}", summary="获取季度集信息")
async def get_season_episodes(tmdb_id: str, season_number: int):
    """
    获取指定作品指定季度的集信息。
    """
    result = await TMDBProvider().get_season_episodes(tmdb_id, season_number)
    if not result:
        raise HTTPException(status_code=404, detail="季度信息未找到")
    log_audit("TMDB", "季度", f"获取集信息: {tmdb_id} S{season_number}")
    return result

@router.get("/season/{tmdb_id}/{season_number}/emby", summary="获取季度集的Emby库信息")
async def get_season_episodes_emby(tmdb_id: str, season_number: int):
    """
    获取指定季度在 Emby 库中的集信息。
    """
    cache_key = f"emby:season:{tmdb_id}:{season_number}"
    cached = _get_emby_cache(cache_key)
    if cached is not None:
        return cached

    def _fetch():
        from emby_client import get_emby_client
        emby = get_emby_client()
        return emby.get_season_episodes_info(tmdb_id, season_number)

    episodes_info = await asyncio.to_thread(_fetch)
    result = {"episodes": episodes_info}
    _set_emby_cache(cache_key, result)
    return result

@router.get("/search", summary="搜索 TMDB 条目", operation_id="tmdb_search_global")
async def search_tmdb_endpoint(query: str, type: str = "tv", year: str = None):
    """
    直接调用 TMDB API 搜索作品。
    type 为空或 'multi' 时同时搜索 movie 和 tv。
    """
    from config_manager import ConfigManager
    proxy = ConfigManager.get_proxy("tmdb")
    proxy_info = f" [代理: {proxy}]" if proxy else " [直连]"
    log_audit("TMDB", "搜索", f"关键词: {query} (类型: {type}){proxy_info}")

    logs = []
    provider = TMDBProvider()
    search_type = (type or "").strip().lower()
    if search_type in ("", "multi"):
        results, _ = await provider.search_multi(query, year, logs=logs)
    else:
        results, _ = await provider.search(query, year, search_type, logs=logs)
    from recognition_engine.tmdb_matcher.logic import TMDBMatcher
    formatted = []
    for i in results:
        norm = TMDBMatcher.normalize(i, media_type_hint=i.get("media_type") or type)
        genre_ids = i.get("genre_ids") or []
        norm["genres"] = [_GENRE_MAP.get(gid) for gid in genre_ids if _GENRE_MAP.get(gid)]
        formatted.append(norm)
    return {"results": formatted}

@router.get("/person/{person_id}", summary="获取人物详情")
async def get_person_detail(person_id: str):
    """
    获取指定人物的详细信息。
    """
    result = await TMDBProvider().get_person_details(person_id)
    if not result:
        raise HTTPException(status_code=404, detail="人物信息未找到")
    log_audit("TMDB", "人物详情", f"获取成功: {result.get('name')}")
    return result

@router.get("/person/{person_id}/credits", summary="获取人物参演作品")
async def get_person_credits(person_id: str):
    """
    获取指定人物的参演作品列表。
    """
    result = await TMDBProvider().get_person_credits(person_id)
    log_audit("TMDB", "人物作品", f"获取作品列表: {person_id}")
    return result
