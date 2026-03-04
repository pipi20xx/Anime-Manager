import time
from ..context import RecognitionContext
from tmdbmatefull.manager import TmdbMateFullManager

class EnrichmentStage:
    @staticmethod
    async def run(ctx: RecognitionContext):
        """
        利用数据中心对匹配到的元数据进行深度补全。
        """
        if not ctx.tmdb_data: return
        start = time.time()
        m_id = str(ctx.tmdb_data.get("id", ""))
        m_type = ctx.tmdb_data.get("type", "tv")

        if not m_id: return

        ctx.log(f"┃ [数据中心] 🔍 正在调取深度档案 (ID: {m_type}:{m_id})...")
        
        try:
            archive = await ctx.full_db.get_deep_meta(m_id, m_type)
            
            # 判断资料完整性：只要缺流派 ID，就执行一次同步
            if (not archive or not archive.get("genre_ids")):
                ctx.log(f"┣ 🚀 [数据中心] 资料缺失(空壳记录)，正在自动固化档案...")
                await ctx.full_db.fetch_and_ingest(m_id, m_type, ctx.logs)
                archive = await ctx.full_db.get_deep_meta(m_id, m_type)

            if archive:
                # 日志记录
                if archive.get("is_custom"):
                    ctx.log(f"┣ 🛡️ [数据中心] 命中用户修正记录: {archive.get('title')}")
                else:
                    ctx.log(f"┣ 📖 [数据中心] 命中权威索引: {archive.get('title')}")
                
                # 统一字段流转 (强制映射)
                field_map = {
                    "origin_country": ["origin_country", "original_country"],
                    "genre_ids": ["genre_ids"],
                    "original_title": ["original_title"],
                    "title": ["title"],
                    "release_date": ["release_date", "first_air_date"],
                    "year": ["year"]
                }
                
                for target, sources in field_map.items():
                    for s in sources:
                        if archive.get(s):
                            ctx.tmdb_data[target] = archive[s]
                            break
                
                # 同步其他基础属性
                for f in ["poster_path", "backdrop_path", "overview", "release_date", "year", "genres", "original_language", "vote_average"]:
                    if archive.get(f): ctx.tmdb_data[f] = archive[f]
                
                # 3. 计算二级分类
                s_cat = await TmdbMateFullManager.calculate_secondary_categories_with_data(
                    m_id, m_type, await TmdbMateFullManager.load_secondary_rules(), archive
                )
                ctx.tmdb_data["secondary_category"] = s_cat
                
                ctx.log(f"┗ ✅ [二级分类] 档案同步完成 (分类结果: {s_cat or '未命中'})")
            else:
                ctx.log(f"┗ ⚠️ [警告] 无法获取到该条目的深度离线资料")

        except Exception as e:
            ctx.log(f"┗ ❌ [错误] 调取数据中心失败: {e}", "ERROR")

        # 4. 联网补全展示资料
        if not ctx.tmdb_data.get("poster_path") or not ctx.tmdb_data.get("overview"):
             try:
                 online_details = await ctx.tmdb_client.get_details(m_id, m_type, [])
                 if online_details:
                     for f in ["poster_path", "backdrop_path", "overview", "vote_average"]:
                         if not ctx.tmdb_data.get(f): ctx.tmdb_data[f] = online_details.get(f)
             except: pass
        
        ctx.add_perf("深度补全", start)