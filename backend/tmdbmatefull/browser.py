from typing import Dict, Any, List, Optional
import logging
from datetime import datetime
from sqlmodel import select, col, or_
from sqlalchemy import func
from .models import TmdbDeepMeta, RefGenre, RefCompany, RefKeyword
from .database import TmdbFullDB

logger = logging.getLogger("TmdbFullBrowser")

class TmdbFullBrowser:
    """
    专门负责从 PostgreSQL 超级表中检索和展示数据的处理器
    """

    @staticmethod
    async def browse(page: int = 1, page_size: int = 20, search: str = None) -> Dict[str, Any]:
        """分页浏览并支持全字段搜索"""
        try:
            async with await TmdbFullDB.get_session() as session:
                # 1. 字典预查 (找出匹配搜索词的 ID)
                matching_ids = {"genres": [], "companies": [], "keywords": []}
                if search:
                    g_res = await session.execute(select(RefGenre.id).where(or_(col(RefGenre.name_zh).contains(search), col(RefGenre.name_en).contains(search))))
                    matching_ids["genres"] = g_res.scalars().all()
                    
                    c_res = await session.execute(select(RefCompany.id).where(col(RefCompany.name).contains(search)))
                    matching_ids["companies"] = c_res.scalars().all()
                    
                    k_res = await session.execute(select(RefKeyword.id).where(col(RefKeyword.name_en).contains(search)))
                    matching_ids["keywords"] = k_res.scalars().all()

                # 2. 构建主表查询
                stmt = select(TmdbDeepMeta)
                if search:
                    # 针对 PGSQL 优化的 ilike
                    from config_manager import ConfigManager
                    is_pg = ConfigManager.get_config().get("database", {}).get("type") == "postgresql"
                    
                    if is_pg:
                        term = f"%{search}%"
                        conditions = [
                            TmdbDeepMeta.title.ilike(term),
                            TmdbDeepMeta.original_title.ilike(term),
                            TmdbDeepMeta.tmdb_id.like(term),
                            TmdbDeepMeta.original_language.ilike(term)
                        ]
                    else:
                        conditions = [
                            col(TmdbDeepMeta.title).contains(search),
                            col(TmdbDeepMeta.original_title).contains(search),
                            col(TmdbDeepMeta.tmdb_id).contains(search)
                        ]
                    
                    for gid in matching_ids["genres"]: conditions.append(col(TmdbDeepMeta.genre_ids).contains(str(gid)))
                    for cid in matching_ids["companies"]: conditions.append(col(TmdbDeepMeta.company_ids).contains(str(cid)))
                    for kid in matching_ids["keywords"]: conditions.append(col(TmdbDeepMeta.keyword_ids).contains(str(kid)))
                    stmt = stmt.where(or_(*conditions))

                # 3. 计算总数
                count_stmt = select(func.count()).select_from(stmt.subquery())
                total = (await session.execute(count_stmt)).scalar() or 0

                # 4. 分页获取记录
                stmt = stmt.order_by(TmdbDeepMeta.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
                records = (await session.execute(stmt)).scalars().all()

                # 5. 批量解析名称
                resolved_items = await TmdbFullBrowser._resolve_names(session, records)

                return {"total": total, "items": resolved_items}
        except Exception as e:
            logger.error(f"数据库浏览查询失败: {e}")
            return {"total": 0, "items": []}

    @staticmethod
    async def export_dictionary() -> Dict[str, List[str]]:
        """导出全量 ID 字典 (简化版)"""
        async with await TmdbFullDB.get_session() as session:
            # 1. 导出流派
            g_res = await session.execute(select(RefGenre).order_by(RefGenre.id))
            genres = [f"{x.id}:{x.name_zh or x.name_en}" for x in g_res.scalars().all()]
            
            # 2. 导出公司
            c_res = await session.execute(select(RefCompany).order_by(RefCompany.name))
            companies = [f"{x.id}:{x.name}" for x in c_res.scalars().all()]
            
            # 3. 导出关键词
            k_res = await session.execute(select(RefKeyword).order_by(RefKeyword.name_en))
            keywords = [f"{x.id}:{x.name_en}" for x in k_res.scalars().all()]

            # 4. 导出已有语言
            lang_res = await session.execute(select(TmdbDeepMeta.original_language).distinct())
            languages = sorted([x for x in lang_res.scalars().all() if x])

            # 5. 导出已有国家
            country_res = await session.execute(select(TmdbDeepMeta.origin_country))
            countries_all = set()
            for c_str in country_res.scalars().all():
                if c_str: countries_all.update(str(c_str).split(","))
            countries = sorted(list(countries_all))

            return {
                "genres": genres,
                "companies": companies,
                "keywords": keywords,
                "languages_in_db": languages,
                "countries_in_db": countries,
                "exported_at": str(datetime.now())
            }

    @staticmethod
    async def _resolve_names(session, records: List[TmdbDeepMeta]) -> List[Dict]:
        """内部方法：将记录中的 ID 集合转换为名称列表"""
        all_g = set(); all_c = set(); all_k = set()
        for r in records:
            if r.genre_ids: all_g.update(str(r.genre_ids).split(","))
            if r.company_ids: all_c.update(str(r.company_ids).split(","))
            if r.keyword_ids: all_k.update(str(r.keyword_ids).split(","))

        g_map = {}; c_map = {}; k_map = {}
        if all_g:
            res = await session.execute(select(RefGenre).where(col(RefGenre.id).in_([int(i) for i in all_g if i.isdigit()])))
            for x in res.scalars().all(): g_map[str(x.id)] = x.name_zh or x.name_en
        if all_c:
            res = await session.execute(select(RefCompany).where(col(RefCompany.id).in_([int(i) for i in all_c if i.isdigit()])))
            for x in res.scalars().all(): c_map[str(x.id)] = x.name
        if all_k:
            res = await session.execute(select(RefKeyword).where(col(RefKeyword.id).in_([int(i) for i in all_k if i.isdigit()])))
            for x in res.scalars().all(): k_map[str(x.id)] = x.name_en

        results = []
        for r in records:
            # 统一使用 model_dump 以匹配后端标准数据流
            item = r.model_dump()
            item["id"] = r.tmdb_id
            # 解析 ID 到名称
            item["genres"] = [g_map.get(str(i), str(i)) for i in str(r.genre_ids).split(",") if i]
            item["companies"] = [c_map.get(str(i), str(i)) for i in str(r.company_ids).split(",") if i]
            item["keywords"] = [k_map.get(str(i), str(i)) for i in str(r.keyword_ids).split(",") if i]
            
            # 合并锁定标题逻辑
            if r.custom_title:
                item["title"] = r.custom_title
                item["manual"] = True
            
            results.append(item)
        return results