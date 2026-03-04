import logging
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from sqlmodel import select, func, or_, delete, text
from models import SeriesFingerprint, DiscoverCache
from tmdbmatefull.models import TmdbDeepMeta
from database import db
import json

logger = logging.getLogger("MetaCache")

# 二级缓存：内存中的短期热数据 (Key -> (data, expire_at))
_L1_CACHE: Dict[str, tuple] = {}

class MetaCacheManager:
    """
    统一元数据管理器。
    """

    @staticmethod
    async def get(key: str) -> Optional[Dict[str, Any]]:
        if ":" not in key: return None
        m_type, m_id = key.split(":", 1)
        m_type = m_type.lower()
        m_id = str(m_id)
        
        async with db.session_scope():
            stmt = select(TmdbDeepMeta).where(TmdbDeepMeta.tmdb_id == m_id, TmdbDeepMeta.media_type == m_type)
            deep = await db.first(TmdbDeepMeta, stmt)
            if not deep: return None
            
            result = deep.model_dump()
            result["id"] = deep.tmdb_id
            
            # [CORE] 日期与年份标准化逻辑
            # 统一将数据库的 first_air_date 映射为识别引擎通用的 release_date
            if deep.first_air_date:
                result["release_date"] = deep.first_air_date
                # 自动提取年份
                if not result.get("year"):
                    result["year"] = str(deep.first_air_date)[:4]
            
            # [CORE] 永久名称逻辑：如果设置了固定名，则覆盖官方名
            if deep.custom_title:
                result["title"] = deep.custom_title
                result["is_custom"] = True
            
            # 合并全量原始数据 (用于补全海报等)
            if deep.full_data:
                for k, v in deep.full_data.items():
                    if result.get(k) is None or result.get(k) == "":
                        result[k] = v
            return result

    @staticmethod
    async def update(key: str, info: Dict[str, Any]):
        m_type, m_id = key.split(":", 1) if ":" in key else (str(info.get("type", "unknown")), str(info.get("id", key)))
        m_type = m_type.lower()
        m_id = str(m_id)
        
        async with db.session_scope():
            stmt = select(TmdbDeepMeta).where(TmdbDeepMeta.tmdb_id == m_id, TmdbDeepMeta.media_type == m_type)
            existing = await db.first(TmdbDeepMeta, stmt)
            
            is_manual_edit = info.get("is_custom") or info.get("manual")
            
            if existing:
                if is_manual_edit:
                    # 手动更新：直接修改固定字段
                    existing.custom_title = info.get("title", existing.custom_title)
                    # 允许手动固定海报和简介
                    if info.get("poster_path"): existing.poster_path = info["poster_path"]
                    if info.get("overview"): existing.overview = info["overview"]
                    existing.is_custom = True
                else:
                    # 自动补全：绝不覆盖已有的 custom_title
                    field_map = {"release_date": "first_air_date", "origin_country": "origin_country"}
                    for k, v in info.items():
                        target = field_map.get(k, k)
                        if hasattr(existing, target) and target not in ["tmdb_id", "media_type", "custom_title"]:
                            setattr(existing, target, v)
                    existing.full_data = info
                
                existing.updated_at = datetime.now()
                await db.save(existing, audit=False)
            else:
                # 全新录入：首录即锁定
                fixed_title = info.get("title", "")
                new_item = TmdbDeepMeta(
                    tmdb_id=m_id, media_type=m_type,
                    title=fixed_title, # 存入官方名
                    custom_title=fixed_title, # 同时也存入固定名
                    original_title=info.get("original_title", ""),
                    origin_country=",".join(info["origin_country"]) if isinstance(info.get("origin_country"), list) else info.get("origin_country", ""),
                    first_air_date=info.get("release_date") or info.get("first_air_date", ""),
                    genre_ids=info.get("genre_ids", ""),
                    full_data=info,
                    is_custom=True,
                    updated_at=datetime.now()
                )
                await db.save(new_item, audit=False)

    # ... 其他方法保持原样 (get_discover_cache, set_discover_cache, get_fingerprint, save_fingerprint, clear_fingerprints, init_db, delete, clear_all, get_paginated) ...
    @staticmethod
    async def get_discover_cache(key: str) -> Optional[Dict[str, Any]]:
        # 1. 尝试从 L1 (内存) 获取
        now = datetime.now()
        if key in _L1_CACHE:
            data, expire_at = _L1_CACHE[key]
            if expire_at > now:
                return data
            else:
                del _L1_CACHE[key]

        # 2. 从数据库获取
        async with db.session_scope():
            stmt = select(DiscoverCache).where(DiscoverCache.key == key)
            item = await db.first(DiscoverCache, stmt)
            if item and item.expire_at > now:
                # 存入 L1 缓存 (5分钟)
                _L1_CACHE[key] = (item.content, now + timedelta(minutes=5))
                return item.content
            return None

    @staticmethod
    async def set_discover_cache(key: str, data: Dict[str, Any], expire_hours: int = 12):
        # 更新内存缓存 (5分钟)
        _L1_CACHE[key] = (data, datetime.now() + timedelta(minutes=5))
        
        async with db.session_scope():
            expire_at = datetime.now() + timedelta(hours=expire_hours)
            stmt = select(DiscoverCache).where(DiscoverCache.key == key)
            existing = await db.first(DiscoverCache, stmt)
            if existing:
                existing.content = data
                existing.expire_at = expire_at
                existing.updated_at = datetime.now()
                await db.save(existing, audit=False)
            else:
                new_item = DiscoverCache(key=key, content=data, expire_at=expire_at, updated_at=datetime.now())
                await db.save(new_item, audit=False)

    @staticmethod
    async def get_fingerprint(fingerprint: str) -> Optional[Dict[str, Any]]:
        async with db.session_scope():
            stmt = select(SeriesFingerprint).where(SeriesFingerprint.fingerprint == fingerprint)
            item = await db.first(SeriesFingerprint, stmt)
            return item.model_dump() if item else None

    @staticmethod
    async def save_fingerprint(fingerprint: str, info: Dict[str, Any]):
        async with db.session_scope():
            stmt = select(SeriesFingerprint).where(SeriesFingerprint.fingerprint == fingerprint)
            existing = await db.first(SeriesFingerprint, stmt)
            if existing:
                existing.tmdb_id = str(info.get("id") or info.get("tmdb_id"))
                existing.title = info.get("title")
                existing.updated_at = datetime.now()
                await db.save(existing, audit=False)
            else:
                new_item = SeriesFingerprint(
                    fingerprint=fingerprint,
                    tmdb_id=str(info.get("id") or info.get("tmdb_id")),
                    type=str(info.get("type", "tv")),
                    title=info.get("title"),
                    updated_at=datetime.now()
                )
                await db.save(new_item, audit=False)

    @staticmethod
    async def clear_system_logs(days: int = 30) -> int:
        from models import SystemLog
        async with db.session_scope() as session:
            cutoff = datetime.now() - timedelta(days=days)
            stmt = delete(SystemLog).where(SystemLog.timestamp < cutoff)
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount

    @staticmethod
    async def clear_fingerprints() -> int:
        async with db.session_scope() as session:
            stmt = delete(SeriesFingerprint)
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount

    @staticmethod
    async def clear_blacklist() -> int:
        from models import Blacklist
        async with db.session_scope() as session:
            stmt = delete(Blacklist)
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount

    @staticmethod
    async def init_db():
        from database import init_db as db_init
        await db_init()

    @staticmethod
    async def delete(key: str):
        if ":" not in key: return
        m_type, m_id = key.split(":", 1)
        async with db.session_scope():
            stmt = select(TmdbDeepMeta).where(TmdbDeepMeta.tmdb_id == m_id, TmdbDeepMeta.media_type == m_type)
            item = await db.first(TmdbDeepMeta, stmt)
            if item: await db.delete(item, audit=False)

    @staticmethod
    async def clear_all():
        async with db.session_scope() as session:
            await session.execute(delete(TmdbDeepMeta))
            await session.commit()

    @staticmethod
    async def get_paginated(page: int = 1, page_size: int = 50, search: str = "") -> Dict[str, Any]:
        async with db.session_scope():
            query = select(TmdbDeepMeta).order_by(TmdbDeepMeta.updated_at.desc())
            if search:
                term = f"%{search}%"
                query = query.where(or_(TmdbDeepMeta.title.ilike(term), TmdbDeepMeta.tmdb_id.like(term)))
            total_res = await db.execute(select(func.count()).select_from(query.subquery()))
            total = total_res.scalar_one()
            query = query.offset((page - 1) * page_size).limit(page_size)
            items = await db.all(TmdbDeepMeta, query)
            
            processed_items = []
            for item in items:
                d = item.model_dump()
                d["id"] = item.tmdb_id
                d["manual"] = item.is_custom
                
                # 合并逻辑与 get 方法对齐
                if item.custom_title:
                    d["title"] = item.custom_title
                
                if item.full_data:
                    for k, v in item.full_data.items():
                        if d.get(k) is None or d.get(k) == "":
                            d[k] = v
                processed_items.append(d)
                
            return {
                "items": processed_items,
                "total": total, "page": page, "page_size": page_size
            }
