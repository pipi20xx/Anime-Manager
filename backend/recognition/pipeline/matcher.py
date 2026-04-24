import time
from ..context import RecognitionContext
from recognition_engine.constants import MediaType
from ..ai_helper import AIHelper

def _is_chinese(text: str) -> bool:
    if not text:
        return False
    for char in text:
        if '\u4e00' <= char <= '\u9fff':
            return True
    return False

def _split_title(title: str) -> list:
    if not title or '/' not in title:
        return [title] if title else []
    
    parts = [p.strip() for p in title.split('/') if p.strip()]
    if len(parts) < 2:
        return parts
    
    cn_titles = [p for p in parts if _is_chinese(p)]
    en_titles = [p for p in parts if not _is_chinese(p)]
    
    result = []
    if cn_titles:
        result.append(cn_titles[0])
    if en_titles:
        result.append(en_titles[0])
    
    return result if result else parts

def _clean_privileged_title(title: str) -> str:
    if not title:
        return title
    
    import re
    
    cleaned = re.sub(r'\.', ' ', title)
    cleaned = re.sub(r'\s+', ' ', cleaned)
    cleaned = cleaned.strip()
    
    return cleaned

async def _ai_fallback_search(ctx: RecognitionContext, meta) -> bool:
    """
    AI 智能体介入：当常规识别失败时，让 AI 猜测标题并重新搜索
    返回是否成功匹配
    """
    ai = AIHelper()
    if not ai.is_available() or not ai.is_fallback_enabled():
        return False
    
    ctx.log(f"┃")
    ctx.log(f"┃ [AI 智能体] 🤖 启动 AI 智能介入...")
    
    current_title = meta.cn_name or meta.en_name or meta.processed_name
    current_episode = meta.begin_episode
    
    ai_result = ai.guess_title_variants(ctx.filename, current_title, current_episode)
    
    if not ai_result:
        ctx.log(f"┣ [AI 智能体] ❌ AI 未返回有效结果")
        return False
    
    real_title = ai_result.get("real_title")
    original_name = ai_result.get("original_name")
    chinese_name = ai_result.get("chinese_name")
    alternatives = ai_result.get("alternative_titles", [])
    confidence = ai_result.get("confidence", 0)
    
    ctx.log(f"┣ [AI 智能体] 🎯 真实标题: {real_title}")
    ctx.log(f"┣ [AI 智能体] 📝 原名: {original_name}")
    ctx.log(f"┣ [AI 智能体] 🇨🇳 中文名: {chinese_name}")
    ctx.log(f"┣ [AI 智能体] 📊 置信度: {confidence:.0%}")
    
    if ai_result.get("season") is not None:
        meta.begin_season = ai_result["season"]
        ctx.log(f"┣ [AI 智能体] 🎬 季号修正: S{ai_result['season']}")
    
    if ai_result.get("episode") is not None and not meta.begin_episode:
        meta.begin_episode = ai_result["episode"]
        ctx.log(f"┣ [AI 智能体] 📺 集数补充: E{ai_result['episode']}")
    
    search_titles = []
    if real_title:
        search_titles.append(real_title)
    if original_name and original_name not in search_titles:
        search_titles.append(original_name)
    if chinese_name and chinese_name not in search_titles:
        search_titles.append(chinese_name)
    search_titles.extend([t for t in alternatives if t not in search_titles])
    
    ctx.log(f"┣ [AI 智能体] 🔍 尝试搜索变体: {search_titles[:3]}...")
    
    for title in search_titles:
        if ctx.tmdb_data:
            break
        
        cn = title if _is_chinese(title) else None
        en = title if not _is_chinese(title) else None
        
        ctx.tmdb_data = await ctx.full_db.resolve(
            cn_name=cn,
            en_name=en,
            year=meta.year,
            media_type=meta.type.value if hasattr(meta.type, "value") else None,
            anime_priority=ctx.anime_priority,
            logs=ctx
        )
        
        if ctx.tmdb_data:
            ctx.log(f"┣ [AI 智能体] ✅ 本地数据中心命中!")
            break
    
    if not ctx.tmdb_data:
        for title in search_titles:
            if ctx.tmdb_data:
                break
            
            cn = title if _is_chinese(title) else None
            en = title if not _is_chinese(title) else None
            
            is_auto_type = meta.type == MediaType.AUTO
            m_type_str = None if is_auto_type else ("movie" if meta.type == MediaType.MOVIE else "tv")
            
            if is_auto_type:
                ctx.tmdb_data = await ctx.tmdb_client.smart_search_multi(
                    cn, en, meta.year, ctx, ctx.anime_priority
                )
            else:
                ctx.tmdb_data = await ctx.tmdb_client.smart_search(
                    cn, en, meta.year, m_type_str, ctx, ctx.anime_priority
                )
            
            if ctx.tmdb_data:
                ctx.log(f"┣ [AI 智能体] ✅ 云端搜索命中!")
                break
    
    if ctx.tmdb_data:
        ctx.log(f"┗ [AI 智能体] 🎉 AI 介入成功!")
        return True
    else:
        ctx.log(f"┗ [AI 智能体] 😔 AI 介入未能找到匹配")
        return False

class MatcherStage:
    @staticmethod
    async def run(ctx: RecognitionContext):
        start = time.time()
        meta = ctx.meta
        
        # 0. 确定搜索用的标题 (优先使用特权标题)
        privileged_title = getattr(meta, 'privileged_title', None)
        privileged_titles = _split_title(privileged_title) if privileged_title else []
        
        if privileged_titles:
            ctx.log(f"[匹配] 🎯 使用特权标题优先搜索: {' | '.join(privileged_titles)}")
        
        # 1. 只有在指纹未命中且当前数据仍为空时，才进行深度搜索
        if not ctx.tmdb_data:
            # 2.1 强制 TMDB ID 锁定模式
            if meta.forced_tmdbid:
                if meta.type == MediaType.AUTO:
                    ctx.log(f"[匹配] 🚀 发现锁定 ID: {meta.forced_tmdbid} (类型: AUTO)，尝试 TV 和 Movie...")
                    for try_type in ["tv", "movie"]:
                        details = await ctx.tmdb_client.get_details(meta.forced_tmdbid, try_type, ctx.logs)
                        if details:
                            ctx.tmdb_data = details
                            ctx.log(f"[匹配] ✅ 类型自动判定为: {try_type.upper()}")
                            break
                else:
                    m_type_str = "movie" if meta.type == MediaType.MOVIE else "tv"
                    ctx.log(f"[匹配] 🚀 发现锁定 ID: {meta.forced_tmdbid}，正在联网获取...")
                    details = await ctx.tmdb_client.get_details(meta.forced_tmdbid, m_type_str, ctx.logs)
                    if details: ctx.tmdb_data = details

            # 2.2 定义搜索策略
            async def search_offline(use_privileged: bool = False, title_index: int = 0):
                if ctx.tmdb_data: return
                # 根据是否使用特权标题决定搜索词
                if use_privileged and privileged_titles:
                    title = privileged_titles[title_index] if title_index < len(privileged_titles) else privileged_titles[0]
                    cn = title if _is_chinese(title) else None
                    en = title if not _is_chinese(title) else None
                else:
                    cn = meta.cn_name
                    en = meta.en_name
                
                ctx.tmdb_data = await ctx.full_db.resolve(
                    cn_name=cn,
                    en_name=en,
                    year=meta.year,
                    media_type=meta.type.value if hasattr(meta.type, "value") else None,
                    anime_priority=ctx.anime_priority,
                    logs=ctx
                )

            async def search_cloud(use_privileged: bool = False, title_index: int = 0, clean_privileged: bool = False):
                if ctx.tmdb_data: return
                bgm_prio = ctx.bangumi_priority
                bgm_failover = ctx.bangumi_failover
                
                if bgm_prio:
                    search_order = ["bangumi", "tmdb"]
                else:
                    search_order = ["tmdb", "bangumi"] if bgm_failover else ["tmdb"]
                
                ctx.log(f"[匹配] ☁️ 云端搜索顺序: {search_order} (优先级: {bgm_prio}, 故障转移: {bgm_failover})")
                
                is_auto_type = meta.type == MediaType.AUTO
                if is_auto_type:
                    ctx.log(f"[匹配] 🔍 类型为 AUTO，将同时搜索 TV 和 Movie")
                    m_type_str = None
                else:
                    m_type_str = "movie" if meta.type == MediaType.MOVIE else "tv"
                
                if use_privileged and privileged_titles:
                    title = privileged_titles[title_index] if title_index < len(privileged_titles) else privileged_titles[0]
                    if clean_privileged:
                        title = _clean_privileged_title(title)
                        ctx.log(f"[匹配] 🧹 使用清洗后的特权标题: {title}")
                    cn = title if _is_chinese(title) else None
                    en = title if not _is_chinese(title) else None
                    original_cn = None
                else:
                    cn = meta.cn_name
                    en = meta.en_name
                    original_cn = meta.original_cn_name
                
                for source in search_order:
                    if ctx.tmdb_data: break
                    if source == "tmdb":
                        if is_auto_type:
                            ctx.tmdb_data = await ctx.tmdb_client.smart_search_multi(
                                cn, en, meta.year, ctx, ctx.anime_priority,
                                original_cn_name=original_cn
                            )
                        else:
                            ctx.tmdb_data = await ctx.tmdb_client.smart_search(
                                cn, en, meta.year, m_type_str, ctx, ctx.anime_priority,
                                original_cn_name=original_cn
                            )
                    elif source == "bangumi":
                        queries = [q for q in [en, cn] if q]
                        if not queries and meta.processed_name:
                            queries = [meta.processed_name]
                            
                        for q in queries:
                            if ctx.tmdb_data: break
                            bgm_subject = await ctx.bangumi_client.search_subject(
                                q, ctx, current_episode=meta.begin_episode, expected_type=m_type_str
                            )
                            if bgm_subject:
                                ctx.log(f"[匹配] 🪄 Bangumi 命中，尝试映射...")
                                ctx.tmdb_data = await ctx.bangumi_client.map_to_tmdb(
                                    bgm_subject, ctx.api_key, ctx
                                )

            # 2.3 执行搜索 (优先特权标题，失败后用正常标题)
            if ctx.offline_priority:
                # 先用特权标题逐个搜索
                for i in range(len(privileged_titles)):
                    if ctx.tmdb_data: break
                    await search_offline(use_privileged=True, title_index=i)
                # 再用正常标题搜索
                if not ctx.tmdb_data:
                    await search_offline(use_privileged=False)
                # 云端搜索 (特权标题逐个尝试)
                for i in range(len(privileged_titles)):
                    if ctx.tmdb_data: break
                    await search_cloud(use_privileged=True, title_index=i, clean_privileged=False)
                # 特权标题清洗后搜索
                for i in range(len(privileged_titles)):
                    if ctx.tmdb_data: break
                    await search_cloud(use_privileged=True, title_index=i, clean_privileged=True)
                # 最后用正常标题搜索
                if not ctx.tmdb_data:
                    if privileged_titles:
                        ctx.log(f"[匹配] 🔄 特权标题搜索失败，使用清洗后的标题继续搜索: {meta.cn_name or meta.en_name}")
                    await search_cloud(use_privileged=False)
            else:
                ctx.log(f"[匹配] ☁️ 本地数据中心已关闭，直接启动云端深度搜索")
                for i in range(len(privileged_titles)):
                    if ctx.tmdb_data: break
                    await search_cloud(use_privileged=True, title_index=i, clean_privileged=False)
                # 特权标题清洗后搜索
                for i in range(len(privileged_titles)):
                    if ctx.tmdb_data: break
                    await search_cloud(use_privileged=True, title_index=i, clean_privileged=True)
                # 最后用正常标题搜索
                if not ctx.tmdb_data:
                    if privileged_titles:
                        ctx.log(f"[匹配] 🔄 特权标题搜索失败，使用清洗后的标题继续搜索: {meta.cn_name or meta.en_name}")
                    await search_cloud(use_privileged=False)
            
            if not ctx.tmdb_data and ctx.ai_fallback_enabled:
                await _ai_fallback_search(ctx, meta)
        
        if ctx.tmdb_data and meta.type == MediaType.AUTO:
            matched_type = ctx.tmdb_data.get("type", "tv")
            if matched_type == "movie":
                meta.type = MediaType.MOVIE
                ctx.log(f"[匹配] 🎬 AUTO 类型已自动判定为: MOVIE")
            else:
                meta.type = MediaType.TV
                ctx.log(f"[匹配] 📺 AUTO 类型已自动判定为: TV")
        
        ctx.add_perf("元数据匹配", start)
