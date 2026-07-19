import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Tuple, Any, List
from fastapi import APIRouter, HTTPException
from recognition.data_provider.tmdb.client import TMDBProvider
from tmdbmatefull.database import DEFAULT_GENRE_MAPPINGS, DEFAULT_COUNTRY_MAPPINGS, DEFAULT_LANGUAGE_MAPPINGS
from logger import log_audit
from emby_index_service import wrap_emby_with_index, sync_index

router = APIRouter(prefix="/api/tmdb", tags=["TMDB 云端数据"])

# Emby 查询内存缓存 (5 分钟 TTL)
_emby_cache: Dict[str, Tuple[Any, datetime]] = {}
_emby_cache_ttl = timedelta(minutes=5)

# 流派 ID 到中文名称的映射
_GENRE_MAP: Dict[int, str] = {g["id"]: g["name_zh"] for g in DEFAULT_GENRE_MAPPINGS}

# 国家/地区代码到中文名称的映射
_COUNTRY_MAP: Dict[str, str] = {g["code"]: g["name_zh"] for g in DEFAULT_COUNTRY_MAPPINGS}

# 语言代码到中文名称的映射
_LANGUAGE_MAP: Dict[str, str] = {g["code"]: g["name_zh"] for g in DEFAULT_LANGUAGE_MAPPINGS}


def _get_emby_cache(key: str) -> Any:
    if key in _emby_cache:
        data, expire_at = _emby_cache[key]
        if expire_at > datetime.now():
            return data
        del _emby_cache[key]
    return None


def _set_emby_cache(key: str, data: Any):
    _emby_cache[key] = (data, datetime.now() + _emby_cache_ttl)


# ── TMDB 详情页季度集信息预热 ──────────────────────────────
# 进入详情页时后台异步拉取所有季的集信息到 discover 缓存，
# 用户点季集时直接命中缓存秒开，无需等待 TMDB 实时请求
_tmdb_preheat_logger = logging.getLogger("TMDBPreheat")
# 仅为近期已预热条目做内存级去重，避免短时间内重复触发；进程重启后自动清空
_preheat_recent: Dict[str, datetime] = {}
_preheat_recent_ttl = timedelta(minutes=10)
# 限制并发请求数，避免一次性请求过多被 TMDB 限流
_preheat_semaphore = asyncio.Semaphore(3)


async def _preheat_season_episodes(tmdb_id: str, seasons: List[Dict]):
    """
    后台预热指定作品所有季的集信息到 discover 缓存。
    - 应以 fire-and-forget 方式调用（asyncio.create_task），不阻塞主流程
    - get_season_episodes 内部已有缓存检查，已缓存的季会直接跳过，不会重复请求 TMDB
    - 全程吞掉异常，绝不影响主流程
    """
    # 短期去重：10 分钟内已预热过的直接跳过，避免频繁刷新触发重复任务
    now = datetime.now()
    recent_key = str(tmdb_id)
    last = _preheat_recent.get(recent_key)
    if last and now - last < _preheat_recent_ttl:
        return
    _preheat_recent[recent_key] = now

    # 顺手清理过期的去重标记，避免内存无限增长
    expired_keys = [k for k, v in _preheat_recent.items() if now - v > _preheat_recent_ttl * 6]
    for k in expired_keys:
        _preheat_recent.pop(k, None)

    preheated = 0
    skipped = 0
    failed = 0
    try:
        provider = TMDBProvider()

        async def _do_one(sn: int):
            nonlocal preheated, skipped, failed
            async with _preheat_semaphore:
                try:
                    # 命中缓存会立即返回；未命中才会真正请求 TMDB
                    res = await provider.get_season_episodes(tmdb_id, sn)
                    if res and res.get("episodes"):
                        preheated += 1
                    else:
                        skipped += 1
                except Exception as e:
                    failed += 1
                    _tmdb_preheat_logger.warning(f"[TMDB 预热] tmdb_id={tmdb_id} S{sn} 失败: {e}")

        # 收集需要预热的季号（过滤掉无 season_number 的异常项）
        season_numbers = [s.get("season_number") for s in seasons if s.get("season_number") is not None]
        if season_numbers:
            # return_exceptions=True 确保单个季失败不影响其他季
            await asyncio.gather(*[_do_one(sn) for sn in season_numbers], return_exceptions=True)

        log_audit("TMDB", "预热", f"季度集预热完成: tmdb_id={tmdb_id} 共 {len(season_numbers)} 季 (预热 {preheated}, 跳过 {skipped}, 失败 {failed})")
    except Exception as e:
        log_audit("TMDB", "预热", f"季度集预热异常: tmdb_id={tmdb_id} - {e}", level="WARN")


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

    # 补充中文映射字段
    if isinstance(result, dict):
        if result.get("origin_country"):
            result["origin_country_zh"] = [_COUNTRY_MAP.get(code, code) for code in result["origin_country"]]
        if result.get("original_language"):
            result["original_language_zh"] = _LANGUAGE_MAP.get(result["original_language"].lower(), result["original_language"].upper())
        if result.get("genres"):
            result["genres"] = [g if isinstance(g, str) else g.get("name", g) for g in result["genres"]]

    log_audit("TMDB", "详情", f"获取成功: {result.get('title')}", details="\n".join(logs))

    # TV 类型：后台异步预热所有季的集信息，用户点季集时直接命中缓存秒开
    # fire-and-forget，不阻塞详情接口返回；已缓存的季会自动跳过
    if media_type == "tv" and isinstance(result.get("seasons"), list) and result["seasons"]:
        asyncio.create_task(_preheat_season_episodes(tmdb_id, result["seasons"]))

    return result

@router.get("/detail/{media_type}/{tmdb_id}/emby", summary="获取作品在Emby库中的状态")
async def get_detail_emby_status(media_type: str, tmdb_id: str):
    """
    获取指定作品在 Emby 库中的入库状态。
    优先用索引标题搜索 Emby，未命中时兜底遍历并回写索引。
    """
    cache_key = f"emby:status:{media_type}:{tmdb_id}"
    cached = _get_emby_cache(cache_key)
    if cached is not None:
        log_audit("Emby", "库状态", f"TMDB ID {tmdb_id}: 缓存命中")
        return cached

    log_audit("Emby", "库状态", f"TMDB ID {tmdb_id}: 开始查询...")

    from emby_client import get_emby_client
    emby = get_emby_client()
    cleanup = await wrap_emby_with_index(emby, tmdb_id, media_type)

    def _fetch():
        if media_type == 'movie':
            return emby.get_movie_info(tmdb_id)
        else:
            return emby.get_series_library_status(tmdb_id)

    result = await asyncio.to_thread(_fetch)
    await cleanup()

    _set_emby_cache(cache_key, result)

    # 记录查询结果
    if result and result.get('exists'):
        if media_type == 'movie':
            movie_name = result.get('name', 'Unknown')
            files_count = len(result.get('files', []))
            log_audit("Emby", "库状态", f"TMDB ID {tmdb_id}: ✅ 电影 '{movie_name}' 已入库 ({files_count} 个文件)")
        else:
            series_name = result.get('series_name', 'Unknown')
            seasons_count = len(result.get('seasons', {}))
            log_audit("Emby", "库状态", f"TMDB ID {tmdb_id}: ✅ 剧集 '{series_name}' 已入库 ({seasons_count} 季)")
    else:
        log_audit("Emby", "库状态", f"TMDB ID {tmdb_id}: ❌ 未入库")

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
        log_audit("Emby", "季度集", f"TMDB ID {tmdb_id} S{season_number}: 缓存命中")
        return cached

    log_audit("Emby", "季度集", f"TMDB ID {tmdb_id} S{season_number}: 开始查询...")

    from emby_client import get_emby_client
    emby = get_emby_client()
    cleanup = await wrap_emby_with_index(emby, tmdb_id, 'tv')

    def _fetch():
        return emby.get_season_episodes_info(tmdb_id, season_number)

    episodes_info = await asyncio.to_thread(_fetch)
    await cleanup()

    result = {"episodes": episodes_info}
    _set_emby_cache(cache_key, result)

    # 记录查询结果
    episodes_count = len(episodes_info)
    total_files = sum(len(ep.get('files', [])) for ep in episodes_info.values())
    if episodes_count > 0:
        log_audit("Emby", "季度集", f"TMDB ID {tmdb_id} S{season_number}: ✅ 已入库 ({episodes_count} 集, {total_files} 个文件)")
    else:
        log_audit("Emby", "季度集", f"TMDB ID {tmdb_id} S{season_number}: ❌ 未入库")

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


@router.post("/emby/sync-index", summary="同步 Emby 库索引")
async def sync_emby_index():
    """
    从 Emby 库拉取所有媒体的 TMDB ID + 类型 + 标题，写入索引表。
    用于加速后续的库状态查询。
    """
    log_audit("Emby", "索引同步", "开始同步...")
    count = await sync_index()
    if count < 0:
        raise HTTPException(status_code=500, detail="索引同步失败，请检查 Emby 连接")
    log_audit("Emby", "索引同步", f"完成，共 {count} 条")
    return {"status": "success", "count": count}
