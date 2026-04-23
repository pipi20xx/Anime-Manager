from ..tools import tool, ToolResult
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)


@tool(
    name="search_tmdb",
    description="在 TMDB 数据库中搜索电影或电视剧。返回作品的标题、年份、TMDB ID 等信息。会同时搜索剧集和电影。",
    category="媒体搜索",
    parameters=[
        {"name": "query", "type": "string", "description": "搜索关键词，作品名称（请保持原样，不要修改用户输入）", "required": True}
    ]
)
async def search_tmdb(query: str) -> ToolResult:
    try:
        from recognition.data_provider.tmdb.client import TMDBProvider
        from recognition_engine.tmdb_matcher.logic import TMDBMatcher
        
        provider = TMDBProvider()
        results, _ = await provider.search_multi(query)
        
        if not results:
            return ToolResult(success=False, error=f"未找到 '{query}' 的搜索结果")
        
        simplified = []
        for item in results[:10]:
            media_type = item.get("media_type", "tv")
            normalized = TMDBMatcher.normalize(item, media_type_hint=media_type)
            simplified.append({
                "tmdb_id": normalized.get("id"),
                "title": normalized.get("title") or normalized.get("name"),
                "original_title": normalized.get("original_title") or normalized.get("original_name"),
                "year": (normalized.get("release_date") or normalized.get("first_air_date") or "")[:4],
                "overview": (normalized.get("overview") or "")[:200],
                "media_type": media_type,
                "poster_path": normalized.get("poster_path")
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
    name="get_bangumi_calendar",
    description="获取当季新番日历，返回正在播出的动画列表。包含番剧名称、Bangumi ID、更新星期、评分等信息。",
    category="媒体搜索",
    parameters=[]
)
async def get_bangumi_calendar() -> ToolResult:
    try:
        from recognition.data_provider.bangumi.client import BangumiProvider
        
        result = await BangumiProvider.get_calendar()
        
        items = result.get("data", []) if isinstance(result, dict) else []
        
        simplified = []
        for day_item in items[:7]:
            weekday = day_item.get("weekday", {})
            is_today = day_item.get("is_today", False)
            for anime in day_item.get("items", []):
                rating_info = anime.get("rating") or {}
                simplified.append({
                    "bangumi_id": anime.get("id"),
                    "title": anime.get("title"),
                    "original_title": anime.get("original_title"),
                    "weekday": weekday.get("cn", ""),
                    "weekday_id": weekday.get("id"),
                    "is_today": is_today,
                    "rating": rating_info.get("score") if isinstance(rating_info, dict) else None,
                    "image": anime.get("image")
                })
        
        formatted_lines = ["📺 **本季番剧列表**\n"]
        formatted_lines.append("| 编号 | 番剧名称 | 更新日 | 评分 | Bangumi ID |")
        formatted_lines.append("|:----:|:---------|:------:|:----:|:----------:|")
        
        for idx, anime in enumerate(simplified, 1):
            rating_str = f"{anime['rating']:.1f}" if anime.get("rating") else "-"
            weekday = anime.get("weekday", "-")
            title = anime.get("title", "未知")
            bangumi_id = anime.get("bangumi_id", "-")
            formatted_lines.append(f"| {idx} | {title} | {weekday} | {rating_str} | {bangumi_id} |")
        
        formatted_lines.append("\n📌 **热门推荐：**\n")
        
        hot_keywords = ["Re：从零", "史莱姆", "实力至上", "租借女友", "航海王", "柯南", "入间"]
        hot_anime = []
        for anime in simplified:
            title = anime.get("title", "")
            for kw in hot_keywords:
                if kw in title:
                    hot_anime.append(anime)
                    break
        
        for anime in hot_anime[:5]:
            idx = simplified.index(anime) + 1
            title = anime.get("title", "")
            formatted_lines.append(f"- **{title}** (编号{idx})")
        
        formatted_lines.append("\n💡 请输入要订阅的番剧编号（多个用空格分隔，输入\"全部\"订阅所有）：")
        
        formatted_message = "\n".join(formatted_lines)
        
        return ToolResult(
            success=True,
            data=simplified,
            message=f"获取到 {len(simplified)} 部当季新番",
            formatted_message=formatted_message
        )
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


@tool(
    name="get_bangumi_subject",
    description="获取 Bangumi 条目的详细信息，包括评分、集数、简介等。",
    category="媒体搜索",
    parameters=[
        {"name": "bangumi_id", "type": "integer", "description": "Bangumi 条目 ID", "required": True}
    ]
)
async def get_bangumi_subject(bangumi_id: int) -> ToolResult:
    try:
        from recognition.data_provider.bangumi.client import BangumiProvider
        
        result = await BangumiProvider.get_subject_details(bangumi_id)
        
        if not result:
            return ToolResult(success=False, error=f"未找到 Bangumi ID {bangumi_id} 的条目")
        
        rating = result.get("rating", {})
        
        return ToolResult(
            success=True,
            data={
                "bangumi_id": result.get("id"),
                "title": result.get("title"),
                "original_title": result.get("original_title"),
                "summary": result.get("summary"),
                "rating": rating.get("score") if isinstance(rating, dict) else None,
                "rating_count": rating.get("total") if isinstance(rating, dict) else None,
                "episodes": result.get("eps"),
                "status": result.get("status", {}).get("cn") if isinstance(result.get("status"), dict) else None,
                "air_date": result.get("date"),
                "image": result.get("images", {}).get("large") if result.get("images") else None
            }
        )
    except Exception as e:
        logger.error(f"[Tool] get_bangumi_subject 失败: {e}")
        return ToolResult(success=False, error=str(e))


@tool(
    name="search_jackett",
    description="在 Jackett 中搜索资源种子。返回种子名称、大小、种子数、下载链接等信息。",
    category="媒体搜索",
    parameters=[
        {"name": "query", "type": "string", "description": "搜索关键词", "required": True},
        {"name": "indexer", "type": "string", "description": "指定站点（可选，不填则搜索所有站点）", "required": False}
    ]
)
async def search_jackett(query: str, indexer: str = "") -> ToolResult:
    try:
        from clients.jackett_client import JackettClient
        from config_manager import ConfigManager
        
        config = ConfigManager.get_config()
        jackett_config = config.get("jackett", {})
        
        if not jackett_config.get("host"):
            return ToolResult(success=False, error="Jackett 未配置，请先在设置中配置 Jackett")
        
        client = JackettClient(
            host=jackett_config.get("host"),
            api_key=jackett_config.get("api_key")
        )
        
        results = await client.search(query, indexer if indexer else None)
        
        if not results:
            return ToolResult(success=True, data=[], message=f"未找到 '{query}' 的资源")
        
        simplified = []
        for item in results[:20]:
            simplified.append({
                "title": item.get("Title"),
                "size": item.get("Size"),
                "seeders": item.get("Seeders"),
                "peers": item.get("Peers"),
                "link": item.get("Link"),
                "indexer": item.get("Tracker"),
                "pub_date": item.get("PublishDate")
            })
        
        return ToolResult(
            success=True,
            data=simplified,
            message=f"找到 {len(simplified)} 个资源"
        )
    except Exception as e:
        logger.error(f"[Tool] search_jackett 失败: {e}")
        return ToolResult(success=False, error=str(e))
