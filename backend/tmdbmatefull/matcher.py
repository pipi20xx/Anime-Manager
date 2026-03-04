from typing import Optional, Dict, Any, List
import logging
from sqlmodel import select, col
from .models import TmdbDeepMeta, MediaTitleIndex
from .database import TmdbFullDB

logger = logging.getLogger(__name__)

class TmdbFullMatcher:
    """
    专门负责：本地离线识别与标题匹配
    """

    @staticmethod
    async def resolve(title: str, year: Optional[str] = None, 
                      media_type: Optional[str] = None, 
                      anime_priority: bool = True) -> Optional[Dict[str, Any]]:
        """
        [主入口] 尝试从本地离线库解析文件元数据
        """
        # 1. 寻找匹配的候选人
        match_info = await TmdbFullMatcher._fast_match(title, year, media_type, anime_priority)
        if not match_info:
            logger.debug(f"未找到匹配项: {title}")
            return None
            
        # 2. 补全深层数据并转换为标准识别格式
        async with await TmdbFullDB.get_session() as session:
            deep = await session.get(TmdbDeepMeta, (match_info["tmdb_id"], match_info["media_type"]))
            if not deep: 
                logger.warning(f"找到匹配项但在主表中缺失元数据: {match_info}")
                return None
            
            return {
                "id": int(deep.tmdb_id),
                "type": deep.media_type,
                "title": deep.custom_title or deep.title, # [PRIORITY] 固定名优先
                "original_title": deep.original_title,
                "original_language": deep.original_language,
                "origin_country": deep.origin_country.split(",") if deep.origin_country else [],
                "genre_ids": [int(i) for i in deep.genre_ids.split(",") if i] if deep.genre_ids else [],
                "release_date": deep.first_air_date,
                "category": "电影" if deep.media_type == "movie" else "剧集",
                "source": "offline_cache" # 标记来源
            }

    @staticmethod
    async def _fast_match(title: str, year: Optional[str] = None, 
                          media_type: Optional[str] = None, 
                          anime_priority: bool = True) -> Optional[Dict[str, str]]:
        """
        内部逻辑：执行数据库联合查询与评分算法
        """
        async with await TmdbFullDB.get_session() as session:
            # 1. 尝试精确匹配
            stmt = select(MediaTitleIndex, TmdbDeepMeta.genre_ids, TmdbDeepMeta.original_language).join(
                TmdbDeepMeta, 
                (MediaTitleIndex.tmdb_id == TmdbDeepMeta.tmdb_id) & (MediaTitleIndex.media_type == TmdbDeepMeta.media_type)
            ).where(MediaTitleIndex.title == title)
            
            if year: stmt = stmt.where(MediaTitleIndex.year == str(year))
            if media_type: stmt = stmt.where(MediaTitleIndex.media_type == media_type)
            
            res = await session.execute(stmt)
            candidates = res.all()

            # 2. 如果精确匹配失败，尝试基于 Trgm 的模糊匹配
            if not candidates and len(title) > 2:
                # 使用 pg_trgm 的 % 操作符进行模糊搜索，结合相似度排序
                from sqlalchemy import text
                fuzzy_stmt = select(
                    MediaTitleIndex, 
                    TmdbDeepMeta.genre_ids, 
                    TmdbDeepMeta.original_language
                ).join(
                    TmdbDeepMeta, 
                    (MediaTitleIndex.tmdb_id == TmdbDeepMeta.tmdb_id) & (MediaTitleIndex.media_type == TmdbDeepMeta.media_type)
                ).where(
                    text("metadata.media_title_index.title % :t").bindparams(t=title)
                )
                
                if year: fuzzy_stmt = fuzzy_stmt.where(MediaTitleIndex.year == str(year))
                if media_type: fuzzy_stmt = fuzzy_stmt.where(MediaTitleIndex.media_type == media_type)
                
                # 按相似度从高到低排序，限制候选人数防止性能抖动
                fuzzy_stmt = fuzzy_stmt.order_by(text("similarity(metadata.media_title_index.title, :t) DESC").bindparams(t=title)).limit(10)
                
                res = await session.execute(fuzzy_stmt)
                candidates = res.all()
            
            if not candidates: return None
            
            # 多重结果评分算法
            best = None
            max_score = -1
            for match, g_ids, o_lang in candidates:
                score = 0
                # A. 动漫优先权重
                if anime_priority and g_ids and "16" in g_ids.split(","):
                    score += 100
                    if o_lang == "ja": score += 50 # 日漫再加分
                
                # B. 来源可靠度权重
                # primary(主标题) > original(原名) > translation(翻译) > alias(别名)
                sw = {"primary": 30, "original": 25, "translation": 20, "alias": 10}
                score += sw.get(match.source, 0)
                
                if score > max_score:
                    max_score = score
                    best = match
            
            return {"tmdb_id": best.tmdb_id, "media_type": best.media_type}
