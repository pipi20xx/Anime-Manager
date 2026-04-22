from ..tools import tool, ToolResult
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@tool(
    name="search_tmdb",
    description="在 TMDB 数据库中搜索电影或电视剧。返回作品的标题、年份、TMDB ID 等信息。",
    category="媒体搜索",
    parameters=[
        {"name": "query", "type": "string", "description": "搜索关键词，作品名称", "required": True},
        {"name": "media_type", "type": "string", "description": "媒体类型：tv(剧集) 或 movie(电影)", "required": False, "enum": ["tv", "movie"]},
        {"name": "year", "type": "string", "description": "发行年份，用于精确匹配", "required": False}
    ]
)
async def search_tmdb(query: str, media_type: str = "tv", year: Optional[str] = None) -> ToolResult:
    try:
        from recognition.data_provider.tmdb.client import TMDBProvider
        from recognition_engine.tmdb_matcher.logic import TMDBMatcher
        
        provider = TMDBProvider()
        results, _ = await provider.search(query, year, media_type)
        
        if not results:
            return ToolResult(success=False, error=f"未找到 '{query}' 的搜索结果")
        
        formatted = [TMDBMatcher.normalize(i, media_type_hint=media_type) for i in results]
        
        simplified = []
        for item in formatted[:10]:
            simplified.append({
                "tmdb_id": item.get("id"),
                "title": item.get("title") or item.get("name"),
                "original_title": item.get("original_title") or item.get("original_name"),
                "year": (item.get("release_date") or item.get("first_air_date") or "")[:4],
                "overview": (item.get("overview") or "")[:200],
                "media_type": item.get("media_type", media_type),
                "poster_path": item.get("poster_path")
            })
        
        return ToolResult(
            success=True,
            data=simplified,
            message=f"找到 {len(simplified)} 个结果"
        )
    except Exception as e:
        logger.error(f"[Tool] search_tmdb 失败: {e}")
        return ToolResult(success=False, error=str(e))


@tool(
    name="get_tmdb_detail",
    description="获取 TMDB 作品的详细信息，包括季数、集数、演职员等。",
    category="媒体搜索",
    parameters=[
        {"name": "tmdb_id", "type": "string", "description": "TMDB ID", "required": True},
        {"name": "media_type", "type": "string", "description": "媒体类型：tv 或 movie", "required": True, "enum": ["tv", "movie"]}
    ]
)
async def get_tmdb_detail(tmdb_id: str, media_type: str) -> ToolResult:
    try:
        from recognition.data_provider.tmdb.client import TMDBProvider
        
        provider = TMDBProvider()
        result = await provider.get_subject_details(tmdb_id, media_type)
        
        if not result:
            return ToolResult(success=False, error=f"未找到 TMDB ID {tmdb_id} 的详情")
        
        simplified = {
            "tmdb_id": result.get("id"),
            "title": result.get("title") or result.get("name"),
            "original_title": result.get("original_title") or result.get("original_name"),
            "overview": result.get("overview"),
            "status": result.get("status"),
            "seasons": result.get("number_of_seasons"),
            "episodes": result.get("number_of_episodes"),
            "genres": [g.get("name") for g in result.get("genres", [])],
            "vote_average": result.get("vote_average"),
            "poster_path": result.get("poster_path"),
            "backdrop_path": result.get("backdrop_path")
        }
        
        if media_type == "tv" and "seasons" in result:
            simplified["season_details"] = [
                {
                    "season_number": s.get("season_number"),
                    "episode_count": s.get("episode_count"),
                    "name": s.get("name"),
                    "air_date": s.get("air_date")
                }
                for s in result.get("seasons", [])
            ]
        
        return ToolResult(success=True, data=simplified)
    except Exception as e:
        logger.error(f"[Tool] get_tmdb_detail 失败: {e}")
        return ToolResult(success=False, error=str(e))


@tool(
    name="get_trending",
    description="获取当前热门的电影或电视剧列表。",
    category="媒体搜索",
    parameters=[
        {"name": "media_type", "type": "string", "description": "媒体类型：tv 或 movie", "required": False, "enum": ["tv", "movie"]}
    ]
)
async def get_trending(media_type: str = "tv") -> ToolResult:
    try:
        from recognition.data_provider.tmdb.client import TMDBProvider
        
        provider = TMDBProvider()
        result = await provider.get_trending()
        
        items = result.get("results", [])
        simplified = []
        for item in items[:15]:
            simplified.append({
                "tmdb_id": item.get("id"),
                "title": item.get("title") or item.get("name"),
                "year": (item.get("release_date") or item.get("first_air_date") or "")[:4],
                "vote_average": item.get("vote_average"),
                "overview": (item.get("overview") or "")[:150],
                "media_type": item.get("media_type", "tv")
            })
        
        return ToolResult(success=True, data=simplified, message=f"获取到 {len(simplified)} 个热门作品")
    except Exception as e:
        logger.error(f"[Tool] get_trending 失败: {e}")
        return ToolResult(success=False, error=str(e))


@tool(
    name="search_bangumi",
    description="在 Bangumi 数据库中搜索动画作品。返回作品的标题、Bangumi ID 等信息。",
    category="媒体搜索",
    parameters=[
        {"name": "query", "type": "string", "description": "搜索关键词", "required": True}
    ]
)
async def search_bangumi(query: str) -> ToolResult:
    try:
        from recognition.data_provider.bangumi.client import BangumiProvider
        
        provider = BangumiProvider()
        results = await provider.search(query)
        
        if not results:
            return ToolResult(success=False, error=f"未找到 '{query}' 的搜索结果")
        
        simplified = []
        for item in results[:10]:
            simplified.append({
                "bangumi_id": item.get("id"),
                "title": item.get("name"),
                "name_cn": item.get("name_cn"),
                "type": item.get("type"),
                "eps": item.get("eps"),
                "rating": item.get("rating", {}).get("score"),
                "air_date": item.get("air_date")
            })
        
        return ToolResult(success=True, data=simplified, message=f"找到 {len(simplified)} 个结果")
    except Exception as e:
        logger.error(f"[Tool] search_bangumi 失败: {e}")
        return ToolResult(success=False, error=str(e))


@tool(
    name="get_bangumi_calendar",
    description="获取当季新番日历，返回正在播出的动画列表。",
    category="媒体搜索",
    parameters=[]
)
async def get_bangumi_calendar() -> ToolResult:
    try:
        from recognition.data_provider.bangumi.client import BangumiProvider
        
        provider = BangumiProvider()
        result = await provider.get_calendar()
        
        items = result.get("data", []) if isinstance(result, dict) else []
        
        simplified = []
        for day_item in items[:7]:
            weekday = day_item.get("weekday", {})
            is_today = day_item.get("is_today", False)
            for anime in day_item.get("items", [])[:5]:
                simplified.append({
                    "bangumi_id": anime.get("id"),
                    "title": anime.get("title"),
                    "original_title": anime.get("original_title"),
                    "weekday": weekday.get("cn", ""),
                    "weekday_id": weekday.get("id"),
                    "is_today": is_today,
                    "rating": anime.get("rating"),
                    "image": anime.get("image")
                })
        
        return ToolResult(success=True, data=simplified, message=f"获取到 {len(simplified)} 部当季新番")
    except Exception as e:
        logger.error(f"[Tool] get_bangumi_calendar 失败: {e}")
        return ToolResult(success=False, error=str(e))


@tool(
    name="recognize_filename",
    description="识别文件名，提取作品名、季度、集数等信息。",
    category="媒体搜索",
    parameters=[
        {"name": "filename", "type": "string", "description": "要识别的文件名", "required": True}
    ]
)
async def recognize_filename(filename: str) -> ToolResult:
    try:
        from recognition.recognizer import MovieRecognizer
        from config_manager import ConfigManager
        
        config = ConfigManager.get_config()
        anime_prio = config.get("anime_priority", True)
        bgm_prio = config.get("bangumi_priority", False)
        bgm_failover = config.get("bangumi_failover", True)
        
        result, _ = await MovieRecognizer.recognize_full(
            filename,
            force_filename=True,
            anime_priority=anime_prio,
            bangumi_priority=bgm_prio,
            bangumi_failover=bgm_failover
        )
        
        if not result.get("success"):
            return ToolResult(success=False, error="识别失败", data=result)
        
        final = result.get("final_result", {})
        
        return ToolResult(
            success=True,
            data={
                "title": final.get("title"),
                "tmdb_id": final.get("tmdb_id"),
                "season": final.get("season"),
                "episode": final.get("episode"),
                "resolution": final.get("resolution"),
                "source": final.get("source"),
                "release_group": final.get("release_group"),
                "category": final.get("category"),
                "year": final.get("year")
            },
            message=f"识别成功: {final.get('title')}"
        )
    except Exception as e:
        logger.error(f"[Tool] recognize_filename 失败: {e}")
        return ToolResult(success=False, error=str(e))
