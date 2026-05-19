from fastapi import APIRouter, HTTPException
from recognition.data_provider.tmdb.client import TMDBProvider
from logger import log_audit

router = APIRouter(prefix="/api/tmdb", tags=["TMDB 云端数据"])

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
    from emby_client import get_emby_client
    emby = get_emby_client()
    
    if media_type == 'movie':
        result = emby.get_movie_info(tmdb_id)
    else:
        result = emby.get_series_library_status(tmdb_id)
    
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
    from emby_client import get_emby_client
    emby = get_emby_client()
    episodes_info = emby.get_season_episodes_info(tmdb_id, season_number)
    return {"episodes": episodes_info}

@router.get("/search", summary="搜索 TMDB 条目", operation_id="tmdb_search_global")
async def search_tmdb_endpoint(query: str, type: str = "tv", year: str = None):
    """
    直接调用 TMDB API 搜索作品。
    """
    from config_manager import ConfigManager
    proxy = ConfigManager.get_proxy("tmdb")
    proxy_info = f" [代理: {proxy}]" if proxy else " [直连]"
    log_audit("TMDB", "搜索", f"关键词: {query} (类型: {type}){proxy_info}")
    
    logs = []
    results, _ = await TMDBProvider().search(query, year, type, logs=logs)
    from recognition_engine.tmdb_matcher.logic import TMDBMatcher
    formatted = [TMDBMatcher.normalize(i, media_type_hint=type) for i in results]
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
