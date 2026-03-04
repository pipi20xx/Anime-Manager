import json
import httpx
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from sqlmodel import select, delete
from sqlalchemy.exc import IntegrityError
from .models import TmdbDeepMeta, MediaTitleIndex, RefGenre, RefCompany, RefKeyword
from .database import TmdbFullDB

logger = logging.getLogger(__name__)

class TmdbFullIngestor:
    """
    专门负责 TMDB 全量数据的：抓取 -> 格式化(脱水) -> 写入数据库
    """

    @staticmethod
    async def process(tmdb_id: str, media_type: str, api_key: str, proxy: Optional[str] = None) -> bool:
        """核心入口：完成从抓取到入库的全过程"""
        raw_data = await TmdbFullIngestor.fetch_raw(tmdb_id, media_type, api_key, proxy)
        if not raw_data:
            return False
        return await TmdbFullIngestor.save_to_db(raw_data, media_type)

    @staticmethod
    async def fetch_raw(tmdb_id: str, media_type: str, api_key: str, proxy: Optional[str] = None) -> Optional[Dict]:
        """[第一步] 远程抓取满血版原始 JSON"""
        async with httpx.AsyncClient(timeout=20, proxy=proxy) as client:
            url = f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}"
            params = {
                "api_key": api_key,
                "language": "zh-CN",
                "append_to_response": "alternative_titles,keywords,translations,credits"
            }
            try:
                resp = await client.get(url, params=params)
                return resp.json() if resp.status_code == 200 else None
            except Exception as e:
                logger.error(f"抓取 {media_type}/{tmdb_id} 失败: {e}")
                return None

    @staticmethod
    async def save_to_db(tmdb_data: Dict[str, Any], media_type: str) -> bool:
        """[第二步] 格式化脱水并原子化入库"""
        tmdb_id = str(tmdb_data.get('id'))
        
        # 1. 深度属性提取 (华语优先逻辑)
        translations = tmdb_data.get('translations', {}).get('translations', [])
        title_dict = {}    # 暂存各地区标题
        overview_dict = {} # 暂存各地区简介
        
        for tr in translations:
            iso = tr.get('iso_3166_1')
            data = tr.get('data', {})
            t = data.get('title') or data.get('name')
            ov = data.get('overview')
            if t: title_dict[iso] = t
            if ov: overview_dict[iso] = ov
        
        # 优先级：简中 > 新加坡 > 香港 > 台湾 > 默认 > 原始
        main_title = title_dict.get('CN') or title_dict.get('SG') or \
                     title_dict.get('HK') or title_dict.get('TW') or \
                     tmdb_data.get('title') or tmdb_data.get('name')
                     
        main_overview = overview_dict.get('CN') or overview_dict.get('SG') or \
                        overview_dict.get('HK') or overview_dict.get('TW') or \
                        tmdb_data.get('overview')
        
        orig_title = tmdb_data.get('original_title') if media_type == 'movie' else tmdb_data.get('original_name')
        countries = tmdb_data.get('origin_country') or [c.get('iso_3166_1') for c in tmdb_data.get('production_countries', [])]
        country_str = ",".join(countries) if countries else ""
        orig_lang = tmdb_data.get('original_language', 'unknown')
        
        first_date = tmdb_data.get('release_date') if media_type == 'movie' else tmdb_data.get('first_air_date')
        last_date = tmdb_data.get('last_air_date') if media_type == 'tv' else None
        year = first_date[:4] if first_date and len(first_date) >= 4 else None
        
        genre_ids = ",".join([str(g.get('id')) for g in tmdb_data.get('genres', [])])
        company_ids = ",".join([str(c.get('id')) for c in tmdb_data.get('production_companies', [])])
        
        kw_raw = tmdb_data.get('keywords', {})
        kw_list = kw_raw.get('keywords') or kw_raw.get('results') or []
        keyword_ids = ",".join([str(k.get('id')) for k in kw_list])
        
        # 2. 标题索引脱水 (区分优先级)
        title_map = {}
        if main_title: title_map[main_title] = "primary"
        if orig_title: title_map[orig_title] = "original"
        
        for tr in tmdb_data.get('translations', {}).get('translations', []):
            t = tr.get('data', {}).get('title') or tr.get('data', {}).get('name')
            if t and t not in title_map: title_map[t] = "translation"
            
        alt_list = tmdb_data.get('alternative_titles', {}).get('titles') or tmdb_data.get('alternative_titles', {}).get('results') or []
        for a in alt_list:
            t = a.get('title') or a.get('name')
            if t and t not in title_map: title_map[t] = "alias"

        # 3. 物理入库事务
        async with await TmdbFullDB.get_session() as session:
            try:
                # 先查一下现存记录，主要为了检查 custom_title
                existing = await session.get(TmdbDeepMeta, (tmdb_id, media_type))
                
                # A. 准备主表数据
                deep_meta = TmdbDeepMeta(
                    tmdb_id=tmdb_id, media_type=media_type, title=main_title,
                    original_title=orig_title, origin_country=country_str,
                    original_language=orig_lang, 
                    first_air_date=str(first_date) if first_date else "",
                    last_air_date=str(last_date) if last_date else None, 
                    poster_path=tmdb_data.get('poster_path'),
                    overview=main_overview, # 使用处理后的最佳中文简介
                    genre_ids=genre_ids,
                    company_ids=company_ids, keyword_ids=keyword_ids,
                    alias_pool=alt_list,
                    title_pool=list(title_map.keys()),
                    full_data=tmdb_data,
                    is_custom=True, # 默认开启锁定
                    updated_at=datetime.now()
                )
                
                # [CORE LOGIC] 永久名称锁定
                if existing:
                    # 如果库里已经有“固定名”，则继承它，不准被覆盖
                    if existing.custom_title:
                        deep_meta.custom_title = existing.custom_title
                        deep_meta.is_custom = True
                    else:
                        # 还没固定，则用现在的
                        deep_meta.custom_title = main_title
                else:
                    # 全新记录，固化第一次见到的名字
                    deep_meta.custom_title = main_title
                
                await session.merge(deep_meta)
                
                # B. 索引表更新 (MediaTitleIndex)
                await session.execute(delete(MediaTitleIndex).where(
                    MediaTitleIndex.tmdb_id == tmdb_id, MediaTitleIndex.media_type == media_type
                ))
                for t, src in title_map.items():
                    session.add(MediaTitleIndex(title=t, year=year, tmdb_id=tmdb_id, media_type=media_type, source=src))
                
                # C. 参考表维护
                for g in tmdb_data.get('genres', []): 
                    await session.merge(RefGenre(id=g['id'], name_zh=g['name'], name_en=""))
                for c in tmdb_data.get('production_companies', []): 
                    await session.merge(RefCompany(id=c['id'], name=c['name'], country=c.get('origin_country', '')))
                for k in kw_list: 
                    await session.merge(RefKeyword(id=k['id'], name_en=k['name']))

                await session.commit()
                logger.info(f"成功保存 {media_type}/{tmdb_id} 到数据库。")
                return True
            except IntegrityError:
                await session.rollback()
                logger.warning(f"数据已存在 (并发冲突)，跳过保存: {media_type}/{tmdb_id}")
                return True
            except Exception as e:
                await session.rollback()
                logger.error(f"{media_type}/{tmdb_id} 数据库事务失败: {e}")
                return False
