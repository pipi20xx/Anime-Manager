import time
from typing import Dict, Any
from .context import RecognitionContext
from .render.engine import RenderEngine
from .render.reporter import RenderReporter
from organizer_core.renamer import Renamer

_country_map_cache = None
_language_map_cache = None
_genre_map_cache = None

async def _load_mapping_cache():
    global _country_map_cache, _language_map_cache, _genre_map_cache
    if _country_map_cache is not None and _language_map_cache is not None and _genre_map_cache is not None:
        return
    
    try:
        from tmdbmatefull.database import TmdbFullDB
        from tmdbmatefull.models import UserCountryMapping, UserLanguageMapping, UserGenreMapping
        from sqlmodel import select
        
        async with await TmdbFullDB.get_session() as session:
            genres = await session.execute(select(UserGenreMapping))
            _genre_map_cache = {str(g.id): g.name_zh for g in genres.scalars().all()}
            
            countries = await session.execute(select(UserCountryMapping))
            _country_map_cache = {c.code.upper(): c.name_zh for c in countries.scalars().all()}
            
            languages = await session.execute(select(UserLanguageMapping))
            _language_map_cache = {l.code.lower(): l.name_zh for l in languages.scalars().all()}
    except Exception as e:
        _genre_map_cache = {
            "28": "动作", "12": "冒险", "16": "动画", "35": "喜剧", "80": "犯罪",
            "99": "纪录", "18": "剧情", "10751": "家庭", "14": "奇幻", "36": "历史",
            "27": "恐怖", "10402": "音乐", "9648": "悬疑", "10749": "爱情", "878": "科幻",
            "10770": "电视电影", "53": "惊悚", "10752": "战争", "37": "西部"
        }
        _country_map_cache = {
            "JP": "日本", "CN": "中国", "US": "美国", "KR": "韩国", "HK": "中国香港", 
            "TW": "中国台湾", "GB": "英国", "FR": "法国", "DE": "德国", "IT": "意大利",
            "CA": "加拿大", "AU": "澳大利亚", "TH": "泰国", "IN": "印度", "RU": "俄罗斯"
        }
        _language_map_cache = {
            "ja": "日语", "zh": "中文", "en": "英语", "ko": "韩语"
        }

async def refresh_mapping_cache():
    """强制刷新映射缓存"""
    global _country_map_cache, _language_map_cache, _genre_map_cache
    _country_map_cache = None
    _language_map_cache = None
    _genre_map_cache = None
    await _load_mapping_cache()

def get_genre_name(genre_id: int | str) -> str:
    if _genre_map_cache is None:
        return str(genre_id)
    return _genre_map_cache.get(str(genre_id), str(genre_id))

def get_country_name(code: str) -> str:
    if _country_map_cache is None:
        return code
    return _country_map_cache.get(code.upper(), code)

def get_language_name(code: str) -> str:
    if _language_map_cache is None:
        return code
    return _language_map_cache.get(code.lower(), code)

class ResultRenderer:
    """
    渲染器主入口 (Layer 3 - Final Stage)
    """
    @staticmethod
    async def apply_to_context(ctx: RecognitionContext) -> Dict[str, Any]:
        await _load_mapping_cache()
        
        # 1. 初始化结论数据包 (Data Normalization)
        data_packet = ResultRenderer._prepare_data_packet(ctx)
        
        # 2. 执行专家渲染规则 (Expert Rules Engine)
        render_start = time.time()
        if ctx.all_render:
            ctx.log("[DEBUG][Step 8: 自定义渲染词处理]: 启动子流程审计")
            r_logs = []
            data_packet = await RenderEngine.apply_rules(
                data_packet, ctx.filename, ctx.all_render, r_logs, ctx.api_key
            )
            for l in r_logs: ctx.log(l)
            ctx.log("✅ 渲染流程结束")
        
        ctx.add_perf("规则渲染", render_start)

        # 3. 同步并修正最终渲染名 (processed_name)
        # [Fallback] 如果渲染规则没生成名字，保留原始文件名作为兜底
        f = data_packet["final_result"]
        if not f.get("processed_name"):
            f["processed_name"] = ctx.filename.split('/')[-1].rsplit('.', 1)[0]

        # 4. 汇总汇报与审计 (Reporting)
        return RenderReporter.report(ctx, data_packet)

    @staticmethod
    def _prepare_data_packet(ctx: RecognitionContext) -> Dict[str, Any]:
        """
        将上下文碎片化信息整合为初步的最终结论。
        """
        meta = ctx.meta
        tmdb_data = ctx.tmdb_data or {}
        
        f_title = tmdb_data.get("title") or (meta.cn_name or meta.en_name)
        f_id = tmdb_data.get("id", "")
        f_year = tmdb_data.get("year") or meta.year or ""
        m_type_str = meta.type.value if hasattr(meta.type, 'value') else str(meta.type)
        f_category = tmdb_data.get("category") or ("电影" if m_type_str == "movie" else "剧集")
        f_season = meta.begin_season if meta.begin_season is not None else 1
        f_episode = f"{meta.begin_episode}-{meta.end_episode}" if meta.is_batch and meta.end_episode else (meta.begin_episode or "")

        # 继承内核处理过的完整名字作为基准，避免丢失制作组等信息
        processed_name = meta.processed_name or ctx.filename.split('/')[-1].rsplit('.', 1)[0]
        
        # 尝试应用系统模板
        current_rules = ctx.config.get("rename_rules", [])
        active_rule = current_rules[0] if current_rules else Renamer.get_default_rules()[0]
        template = active_rule.get("movie_pattern") if f_category == "电影" else active_rule.get("tv_pattern")
        if not template: template = "{title} ({year}) S{season_02}E{episode_02}"
        
        render_ctx = {
            "title": f_title, "tmdb_id": f_id, "year": f_year, "season": f_season, "episode": f_episode,
            "season_02": f"{f_season:02d}" if isinstance(f_season, int) else f_season,
            "episode_02": f"{f_episode:02d}" if isinstance(f_episode, int) else f_episode,
            "resolution": meta.resource_pix, "team": meta.resource_team, "source": meta.resource_type,
            "video_encode": meta.video_encode, "audio_encode": meta.audio_encode, "video_effect": meta.video_effect,
            "subtitle": meta.subtitle_lang, "platform": meta.resource_platform,
            "ext": ctx.filename.split('.')[-1] if '.' in ctx.filename else ""
        }
        
        try:
            p_name = Renamer.render_name(template, render_ctx).split('/')[-1].split('\\')[-1]
            if p_name.endswith(f".{render_ctx['ext']}"): p_name = p_name[:-(len(render_ctx['ext'])+1)]
            if p_name and "{title}" not in p_name and p_name != template:
                processed_name = p_name
        except: pass

        raw_c = tmdb_data.get("origin_country")
        c_code = raw_c[0] if isinstance(raw_c, list) and raw_c else str(raw_c or "")
        f_country = get_country_name(c_code)

        final_res = {
            "path": ctx.filename, "filename": ctx.filename.split('/')[-1],
            "title": f_title, "tmdb_id": f_id, "year": f_year, "category": f_category,
            "secondary_category": tmdb_data.get("secondary_category"),
            "origin_country": f_country,
            "season": f_season, "episode": f_episode,
            "resolution": meta.resource_pix, "team": meta.resource_team,
            "source": meta.resource_type, "video_encode": meta.video_encode,
            "audio_encode": meta.audio_encode, "video_effect": meta.video_effect,
            "subtitle": meta.subtitle_lang, "platform": meta.resource_platform,
            "processed_name": processed_name,
            "poster_path": tmdb_data.get("poster_path"),
            "release_date": tmdb_data.get("release_date"),
            "vote_average": tmdb_data.get("vote_average"),
            "duration": f"{ctx.duration:.1f}s"
        }

        # 构建元数据快照
        raw_meta_clean = vars(meta).copy()
        if 'type' in raw_meta_clean and hasattr(raw_meta_clean['type'], 'value'):
            raw_meta_clean['type'] = raw_meta_clean['type'].value

        return {
            "success": True, 
            "final_result": final_res, 
            "raw_meta": raw_meta_clean, 
            "tmdb_match": tmdb_data
        }
