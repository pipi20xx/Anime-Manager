import time
from ..context import RecognitionContext

class MaintenanceStage:
    @staticmethod
    async def run(ctx: RecognitionContext):
        """识别完成后的后台维护逻辑"""
        if not ctx.tmdb_data: return
        start = time.time()
        
        m_id = str(ctx.tmdb_data.get("id", ""))
        m_type = ctx.tmdb_data.get("type", "tv")
        
        # 1. 自动维护指纹库
        existing_fp = await ctx.cache_dao.get_fingerprint_match(ctx.filename, [])
        if not existing_fp or str(existing_fp.get("id")) != m_id:
            await ctx.cache_dao.save_fingerprint(
                ctx.filename, ctx.tmdb_data, ctx.logs
            )
        
        # 2. 自动同步元数据到数据中心 (落库存档)
        # 逻辑：如果当前数据不是从存档中拿到的，或者虽然拿到了但需要补全
        if ctx.tmdb_data.get("source") not in ["archive_hit", "cache_hit_verified"]:
            # 只有当库里没有，或者没有手动修正标志时，才自动存档新抓取的数据
            existing_archive = await ctx.local_store.get_metadata(m_id, m_type, [])
            if not existing_archive or not existing_archive.get("is_custom"):
                # 将新抓取的数据全量固化到数据库
                await ctx.cache_dao.save_metadata(m_id, m_type, ctx.tmdb_data, ctx.logs)
            else:
                # 已经是固定记录了，只更新 source 标记供渲染使用
                ctx.tmdb_data["source"] = "archive_hit_locked"

        ctx.add_perf("维护同步", start)
