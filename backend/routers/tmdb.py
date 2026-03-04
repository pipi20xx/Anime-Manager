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

@router.get("/search", summary="搜索 TMDB 条目", operation_id="tmdb_search_global")
async def search_tmdb_endpoint(query: str, type: str = "tv", year: str = None):
    """
    直接调用 TMDB API 搜索作品。
    """
    logs = []
    results = await TMDBProvider().search(query, year, type, logs=logs)
    from recognition_engine.tmdb_matcher.logic import TMDBMatcher
    formatted = [TMDBMatcher.normalize(i, media_type_hint=type) for i in results]
    log_audit("TMDB", "搜索", f"关键词: {query}", details="\n".join(logs))
    return {"results": formatted}
