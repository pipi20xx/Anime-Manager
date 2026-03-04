from fastapi import APIRouter, Query
from typing import Optional, List, Dict, Any
from recognition.data_provider.tmdb.client import TMDBProvider
from recognition.data_provider.bangumi.client import BangumiProvider
from datetime import datetime
from logger import log_audit

router = APIRouter(prefix="/api/explore", tags=["探索发现"])

# === TMDB Config ===
TMDB_GENRES = [
    {"id": 16, "name": "动画 (Animation)"},
    {"id": 10759, "name": "动作冒险 (Action & Adventure)"},
    {"id": 28, "name": "动作 (Action)"},
    {"id": 12, "name": "冒险 (Adventure)"},
    {"id": 35, "name": "喜剧 (Comedy)"},
    {"id": 80, "name": "犯罪 (Crime)"},
    {"id": 99, "name": "纪录片 (Documentary)"},
    {"id": 18, "name": "剧情 (Drama)"},
    {"id": 10751, "name": "家庭 (Family)"},
    {"id": 14, "name": "奇幻 (Fantasy)"},
    {"id": 36, "name": "历史 (History)"},
    {"id": 27, "name": "恐怖 (Horror)"},
    {"id": 10402, "name": "音乐 (Music)"},
    {"id": 9648, "name": "悬疑 (Mystery)"},
    {"id": 10749, "name": "爱情 (Romance)"},
    {"id": 878, "name": "科幻 (Sci-Fi)"},
    {"id": 10765, "name": "科幻/奇幻 (Sci-Fi & Fantasy)"},
    {"id": 10762, "name": "儿童 (Kids)"},
    {"id": 10763, "name": "新闻 (News)"},
    {"id": 10764, "name": "真人秀 (Reality)"},
    {"id": 10766, "name": "肥皂剧 (Soap)"},
    {"id": 10767, "name": "脱口秀 (Talk)"},
    {"id": 10768, "name": "政治 (War & Politics)"},
    {"id": 10752, "name": "战争 (War)"},
    {"id": 53, "name": "惊悚 (Thriller)"},
    {"id": 37, "name": "西部 (Western)"}
]

TMDB_LANGUAGES = [
    {"label": "日语 (Japanese)", "value": "ja"},
    {"label": "国语 (Chinese)", "value": "zh"},
    {"label": "英语 (English)", "value": "en"},
    {"label": "韩语 (Korean)", "value": "ko"},
    {"label": "法语 (French)", "value": "fr"},
    {"label": "德语 (German)", "value": "de"},
    {"label": "西班牙语 (Spanish)", "value": "es"},
    {"label": "俄语 (Russian)", "value": "ru"},
    {"label": "泰语 (Thai)", "value": "th"},
    {"label": "意大利语 (Italian)", "value": "it"},
    {"label": "葡萄牙语 (Portuguese)", "value": "pt"},
    {"label": "粤语 (Cantonese)", "value": "cn"},
    {"label": "印地语 (Hindi)", "value": "hi"},
    {"label": "阿拉伯语 (Arabic)", "value": "ar"}
]

TMDB_SORT_OPTIONS = [
    {"label": "热度降序 (Popularity)", "value": "popularity.desc"},
    {"label": "评分降序 (Rating)", "value": "vote_average.desc"},
    {"label": "首播日期降序 (Newest)", "value": "first_air_date.desc"},
    {"label": "首播日期升序 (Oldest)", "value": "first_air_date.asc"},
]

# === Bangumi Config ===
# 基础风格 (原有)
BANGUMI_TAGS = [
    {"id": "战斗", "name": "战斗"}, {"id": "恋爱", "name": "恋爱"}, {"id": "校园", "name": "校园"},
    {"id": "日常", "name": "日常"}, {"id": "科幻", "name": "科幻"}, {"id": "治愈", "name": "治愈"},
    {"id": "后宫", "name": "后宫"}, {"id": "奇幻", "name": "奇幻"}, {"id": "悬疑", "name": "悬疑"},
    {"id": "推理", "name": "推理"}, {"id": "搞笑", "name": "搞笑"}, {"id": "机战", "name": "机战"},
    {"id": "百合", "name": "百合"}, {"id": "乙女", "name": "乙女"}, {"id": "纯爱", "name": "纯爱"},
    {"id": "异世界", "name": "异世界"}, {"id": "穿越", "name": "穿越"}, {"id": "竞技", "name": "竞技"},
    {"id": "励志", "name": "励志"}, {"id": "音乐", "name": "音乐"}, {"id": "美食", "name": "美食"}
]

# 新增维度
BANGUMI_TYPES = [
    {"id": "TV", "name": "TV"}, {"id": "WEB", "name": "WEB"},
    {"id": "OVA", "name": "OVA"}, {"id": "剧场版", "name": "剧场版"},
    {"id": "动态漫画", "name": "动态漫画"}, {"id": "其他", "name": "其他"}
]

BANGUMI_SOURCES = [
    {"id": "原创", "name": "原创"}, {"id": "漫画改", "name": "漫画改"},
    {"id": "游戏改", "name": "游戏改"}, {"id": "小说改", "name": "小说改"},
    {"id": "影视改", "name": "影视改"}
]

BANGUMI_REGIONS = [
    {"id": "日本", "name": "日本"}, {"id": "欧美", "name": "欧美"}, {"id": "中国", "name": "中国"},
    {"id": "美国", "name": "美国"}, {"id": "韩国", "name": "韩国"}, {"id": "法国", "name": "法国"},
    {"id": "中国香港", "name": "中国香港"}, {"id": "英国", "name": "英国"},
    {"id": "俄罗斯", "name": "俄罗斯"}, {"id": "苏联", "name": "苏联"},
    {"id": "捷克", "name": "捷克"}, {"id": "中国台湾", "name": "中国台湾"},
    {"id": "马来西亚", "name": "马来西亚"}
]

BANGUMI_AUDIENCES = [
    {"id": "BL", "name": "BL"}, {"id": "GL", "name": "GL"}, {"id": "子供向", "name": "子供向"},
    {"id": "女性向", "name": "女性向"}, {"id": "少女向", "name": "少女向"},
    {"id": "少年向", "name": "少年向"}, {"id": "青年向", "name": "青年向"}
]

BANGUMI_SORT_OPTIONS = [
    {"label": "上映时间 (Date)", "value": "match"},
    {"label": "全站排名 (Rank)", "value": "popularity.desc"},
]

@router.get("/config", summary="获取筛选配置")
async def get_explore_config(source: str = Query("tmdb", enum=["tmdb", "bangumi"])):
    """
    根据数据源返回对应的筛选配置
    """
    current_year = datetime.now().year
    years = [str(y) for y in range(current_year + 1, 1980, -1)]
    years.append("1980s")
    
    if source == "bangumi":
        return {
            "genres": BANGUMI_TAGS,
            "languages": [], 
            "sort_options": BANGUMI_SORT_OPTIONS,
            "years": years,
            # 扩展字段
            "bangumi_types": BANGUMI_TYPES,
            "bangumi_sources": BANGUMI_SOURCES,
            "bangumi_regions": BANGUMI_REGIONS,
            "bangumi_audiences": BANGUMI_AUDIENCES
        }
    
    return {
        "genres": TMDB_GENRES,
        "languages": TMDB_LANGUAGES,
        "sort_options": TMDB_SORT_OPTIONS,
        "years": years
    }

@router.get("/list", summary="通用发现查询")
async def explore_content(
    source: str = Query("tmdb", enum=["tmdb", "bangumi"]),
    media_type: str = Query("tv", enum=["tv", "movie"]),
    sort_by: str = Query("popularity.desc"),
    with_genres: Optional[str] = Query(None, description="流派/标签"),
    year: Optional[str] = Query(None),
    language: Optional[str] = Query(None),
    # 新增 Bangumi 专用参数
    subtype: Optional[str] = Query(None, description="分类 (TV/OVA...)"),
    story_source: Optional[str] = Query(None, description="来源 (原创/漫改...)"),
    region: Optional[str] = Query(None, description="地区 (日本/中国...)"),
    audience: Optional[str] = Query(None, description="受众 (少年向...)"),
    rank_range: Optional[str] = Query(None, description="排名范围 (e.g. 1-500)"),
    page: int = Query(1, ge=1)
):
    """
    通用发现接口，支持 TMDB 和 Bangumi (多维筛选)
    """
    logs = []
    params = {
        "page": page,
        "sort_by": sort_by,
        "with_genres": with_genres,
        "year": year
    }
    
    if source == "bangumi":
        # 注入新维度
        if subtype: params["subtype"] = subtype
        if story_source: params["source"] = story_source
        if region: params["region"] = region
        if audience: params["audience"] = audience
        if rank_range: params["rank_range"] = rank_range
        res = await BangumiProvider.discover(params, logs=logs)
        log_audit("探索", "Bangumi", f"发现查询: {params.get('keyword', '列表浏览')} | 结果数: {len(res.get('results', []))}", details="\n".join(logs))
        return res

    # --- TMDB Logic ---
    valid_tmdb_sorts = [opt["value"] for opt in TMDB_SORT_OPTIONS]
    if sort_by not in valid_tmdb_sorts:
        sort_by = "popularity.desc"

    tmdb_params = {
        "page": page,
        "sort_by": sort_by,
        "include_adult": "false",
        "include_null_first_air_dates": "false",
        "vote_count.gte": 0, 
    }
    
    if with_genres:
        tmdb_params["with_genres"] = with_genres
    
    if year:
        if year == "1980s":
            if media_type == "movie":
                tmdb_params["primary_release_date.lte"] = "1989-12-31"
            else:
                tmdb_params["first_air_date.lte"] = "1989-12-31"
        else:
            if media_type == "movie":
                tmdb_params["primary_release_year"] = year
            else:
                tmdb_params["first_air_date_year"] = year

    if language:
        tmdb_params["with_original_language"] = language
                
    provider = TMDBProvider()
    res = await provider.discover(media_type, tmdb_params, logs=logs)
    log_audit("探索", "TMDB", f"发现查询 ({media_type}) | 结果数: {len(res.get('results', []))}", details="\n".join(logs))
    return res

@router.get("/search", summary="手动综合搜索")
async def manual_search(
    keyword: str = Query(..., description="搜索关键词"),
):
    """
    同时搜索 TMDB (Movie/TV) 和 Bangumi，返回聚合结果。
    """
    if not keyword:
        return {"bangumi": [], "tmdb_movie": [], "tmdb_tv": []}

    logs = []
    tmdb = TMDBProvider()
    
    # 1. Bangumi Search (reuse discover)
    bgm_task = BangumiProvider.discover({"keyword": keyword, "sort_by": "match"}, logs=logs)
    
    # 2. TMDB Search (Movie & TV)
    tmdb_m_task = tmdb.search(keyword, None, "movie", lang="zh-CN", logs=logs)
    tmdb_t_task = tmdb.search(keyword, None, "tv", lang="zh-CN", logs=logs)
    
    import asyncio
    bgm_res, tmdb_m_res, tmdb_t_res = await asyncio.gather(bgm_task, tmdb_m_task, tmdb_t_task)
    
    log_audit("搜索", "聚合搜索", f"关键词: {keyword}", details="\n".join(logs))
    
    # Normalize TMDB results
    from recognition_engine.tmdb_matcher.logic import TMDBMatcher
    tmdb_movies = [TMDBMatcher.normalize(i, "movie") for i in (tmdb_m_res or [])]
    tmdb_tvs = [TMDBMatcher.normalize(i, "tv") for i in (tmdb_t_res or [])]
    
    return {
        "bangumi": bgm_res.get("results", []),
        "tmdb_movie": tmdb_movies,
        "tmdb_tv": tmdb_tvs
    }