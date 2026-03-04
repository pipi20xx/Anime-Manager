import time
from ..context import RecognitionContext
from recognition_engine.constants import MediaType

def _is_chinese(text: str) -> bool:
    """判断文本是否包含中文"""
    if not text:
        return False
    for char in text:
        if '\u4e00' <= char <= '\u9fff':
            return True
    return False

def _split_title(title: str) -> list:
    """
    拆分标题 (针对包含 / 的多语言标题)
    返回: [中文标题, 英文标题] 或 [原标题]
    """
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

            async def search_cloud(use_privileged: bool = False, title_index: int = 0):
                if ctx.tmdb_data: return
                bgm_prio = ctx.bangumi_priority
                bgm_failover = ctx.bangumi_failover
                
                if bgm_prio:
                    search_order = ["bangumi", "tmdb"]
                else:
                    search_order = ["tmdb", "bangumi"] if bgm_failover else ["tmdb"]
                
                ctx.log(f"[匹配] ☁️ 云端搜索顺序: {search_order} (优先级: {bgm_prio}, 故障转移: {bgm_failover})")
                m_type_str = "movie" if meta.type == MediaType.MOVIE else "tv"
                
                # 根据是否使用特权标题决定搜索词
                if use_privileged and privileged_titles:
                    title = privileged_titles[title_index] if title_index < len(privileged_titles) else privileged_titles[0]
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
                    await search_cloud(use_privileged=True, title_index=i)
                if not ctx.tmdb_data:
                    await search_cloud(use_privileged=False)
            else:
                ctx.log(f"[匹配] ☁️ 本地数据中心已关闭，直接启动云端深度搜索")
                for i in range(len(privileged_titles)):
                    if ctx.tmdb_data: break
                    await search_cloud(use_privileged=True, title_index=i)
                if not ctx.tmdb_data:
                    await search_cloud(use_privileged=False)
        
        ctx.add_perf("元数据匹配", start)
