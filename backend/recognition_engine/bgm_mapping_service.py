import asyncio
import httpx
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from sqlmodel import select
from sqlalchemy.dialects.postgresql import insert

from database import db
from models import BangumiDataItem, DiscoverCache

logger = logging.getLogger("BangumiData")

BANGUMI_DATA_URL = "https://unpkg.com/bangumi-data@0.3/dist/data.json"
SYNC_CACHE_KEY = "bgm_mapping_sync"
SYNC_INTERVAL_DAYS = 7


class BangumiDataItemService:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @staticmethod
    async def get_sync_status() -> Dict[str, Any]:
        try:
            async with db.session_scope():
                stmt = select(DiscoverCache).where(DiscoverCache.key == SYNC_CACHE_KEY)
                result = await db.session.execute(stmt)
                cache = result.scalars().first()
                
                if cache:
                    return cache.content or {}
        except Exception as e:
            logger.warning(f"[BangumiData] 获取同步状态失败: {e}")
        return {}
    
    @staticmethod
    async def save_sync_status(items_count: int, mapping_count: int) -> None:
        try:
            async with db.session_scope():
                stmt = select(DiscoverCache).where(DiscoverCache.key == SYNC_CACHE_KEY)
                result = await db.session.execute(stmt)
                cache = result.scalars().first()
                
                now = datetime.now()
                content = {
                    "last_sync_time": now.isoformat(),
                    "items_count": items_count,
                    "mapping_count": mapping_count,
                    "version": "0.3"
                }
                
                if cache:
                    cache.content = content
                    cache.updated_at = now
                    cache.expire_at = now + timedelta(days=SYNC_INTERVAL_DAYS + 1)
                else:
                    cache = DiscoverCache(
                        key=SYNC_CACHE_KEY,
                        content=content,
                        updated_at=now,
                        expire_at=now + timedelta(days=SYNC_INTERVAL_DAYS + 1)
                    )
                
                db.session.add(cache)
                await db.session.commit()
        except Exception as e:
            logger.warning(f"[BangumiData] 保存同步状态失败: {e}")
    
    @staticmethod
    async def should_sync() -> tuple[bool, str]:
        # 1. 表为空则必须同步（首次启动 / 数据被清空）
        try:
            async with db.session_scope():
                from sqlalchemy import text
                count_result = await db.session.execute(
                    text("SELECT COUNT(*) FROM public.bangumi_data_item")
                )
                row_count = count_result.scalar() or 0
            if row_count == 0:
                return True, "条目表为空，需要同步"
        except Exception as e:
            logger.warning(f"[BangumiData] 检查表数据失败，按缓存策略继续: {e}")
        
        # 2. 按缓存状态判断 7 天间隔
        status = await BangumiDataItemService.get_sync_status()
        
        if not status:
            return True, "首次启动，需要同步"
        
        last_sync = status.get("last_sync_time")
        if not last_sync:
            return True, "无同步记录，需要同步"
        
        try:
            last_sync_time = datetime.fromisoformat(last_sync)
            elapsed = datetime.now() - last_sync_time
            
            if elapsed.days >= SYNC_INTERVAL_DAYS:
                return True, f"距上次同步已 {elapsed.days} 天，需要更新"
            
            return False, f"数据有效，距上次同步 {elapsed.days} 天"
        except Exception:
            return True, "同步时间解析失败，需要同步"
    
    @staticmethod
    async def fetch_bangumi_data() -> Optional[Dict]:
        logger.info(f"[BangumiData] 📡 正在请求: {BANGUMI_DATA_URL}")
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            try:
                resp = await client.get(BANGUMI_DATA_URL)
                if resp.status_code == 200:
                    data = resp.json()
                    items_count = len(data.get("items", []))
                    logger.info(f"[BangumiData] ✅ 数据获取成功，共 {items_count} 个条目")
                    return data
                logger.error(f"[BangumiData] ❌ HTTP 错误: {resp.status_code}")
            except httpx.TimeoutException:
                logger.error(f"[BangumiData] ❌ 请求超时 (30s)")
            except Exception as e:
                logger.error(f"[BangumiData] ❌ 请求异常: {e}")
        return None
    
    @staticmethod
    def parse_mapping(data: Dict) -> List[Dict]:
        mappings = []
        items = data.get("items", [])
        
        tv_count = 0
        movie_count = 0
        skipped_count = 0
        duplicate_count = 0
        seen_bgm_ids = set()
        
        for item in items:
            sites = item.get("sites", [])
            bgm_id = None
            tmdb_id = None
            tmdb_type = "tv"
            mal_id = None
            anilist_id = None
            anidb_id = None
            
            for site in sites:
                site_name = site.get("site", "")
                site_id = site.get("id", "")
                
                if site_name == "bangumi":
                    try:
                        bgm_id = int(site_id)
                    except (ValueError, TypeError):
                        continue
                
                elif site_name == "tmdb":
                    if "/" in str(site_id):
                        parts = str(site_id).split("/")
                        tmdb_type = parts[0]
                        try:
                            tmdb_id = int(parts[1])
                        except (ValueError, TypeError):
                            continue
                    else:
                        try:
                            tmdb_id = int(site_id)
                        except (ValueError, TypeError):
                            continue
                
                elif site_name == "mal":
                    try:
                        mal_id = int(site_id)
                    except (ValueError, TypeError):
                        continue
                
                elif site_name == "anilist":
                    try:
                        anilist_id = int(site_id)
                    except (ValueError, TypeError):
                        continue
                
                elif site_name == "anidb":
                    try:
                        anidb_id = int(site_id)
                    except (ValueError, TypeError):
                        continue
            
            if bgm_id and tmdb_id:
                if bgm_id in seen_bgm_ids:
                    duplicate_count += 1
                    continue
                seen_bgm_ids.add(bgm_id)
                
                title = item.get("title", "")
                title_cn = ""
                title_translate = item.get("titleTranslate", {})
                if title_translate:
                    zh_hans = title_translate.get("zh-Hans", [])
                    if zh_hans:
                        title_cn = zh_hans[0]
                
                media_type = "movie" if tmdb_type == "movie" else "tv"
                
                if media_type == "tv":
                    tv_count += 1
                else:
                    movie_count += 1
                
                mappings.append({
                    "bgm_id": bgm_id,
                    "tmdb_id": tmdb_id,
                    "media_type": media_type,
                    "mal_id": mal_id,
                    "anilist_id": anilist_id,
                    "anidb_id": anidb_id,
                    "title": title,
                    "title_cn": title_cn,
                    "raw_data": item
                })
            else:
                skipped_count += 1
        
        logger.info(f"[BangumiData] 📊 解析完成:")
        logger.info(f"[BangumiData]    ├─ TV 剧集: {tv_count} 条")
        logger.info(f"[BangumiData]    ├─ 电影: {movie_count} 条")
        logger.info(f"[BangumiData]    ├─ 跳过 (无映射): {skipped_count} 条")
        logger.info(f"[BangumiData]    └─ 去重 (重复BGM ID): {duplicate_count} 条")
        
        return mappings
    
    @staticmethod
    async def sync_from_remote(force: bool = False) -> Dict[str, Any]:
        if not force:
            should, reason = await BangumiDataItemService.should_sync()
            if not should:
                logger.info(f"[BangumiData] ⏭️ 跳过同步: {reason}")
                status = await BangumiDataItemService.get_sync_status()
                return {
                    "success": True,
                    "message": reason,
                    "count": status.get("mapping_count", 0),
                    "skipped": True
                }
        
        logger.info("=" * 50)
        logger.info("[BangumiData] 🔄 开始同步 BangumiData 条目表")
        logger.info(f"[BangumiData] 📅 同步时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        data = await BangumiDataItemService.fetch_bangumi_data()
        if not data:
            logger.error("[BangumiData] ❌ 同步失败: 无法获取远程数据")
            return {"success": False, "message": "获取远程数据失败"}
        
        items_count = len(data.get("items", []))
        mappings = BangumiDataItemService.parse_mapping(data)
        if not mappings:
            logger.error("[BangumiData] ❌ 同步失败: 解析结果为空")
            return {"success": False, "message": "解析映射数据为空"}
        
        logger.info(f"[BangumiData] 💾 正在写入数据库 (分批处理)...")
        
        try:
            batch_size = 1000
            total_written = 0
            
            for i in range(0, len(mappings), batch_size):
                batch = mappings[i:i + batch_size]
                batch_num = i // batch_size + 1
                total_batches = (len(mappings) + batch_size - 1) // batch_size
                
                logger.info(f"[BangumiData]    批次 {batch_num}/{total_batches}: 写入 {len(batch)} 条")
                
                async with db.session_scope():
                    from sqlalchemy.dialects.postgresql import insert
                    
                    stmt = insert(BangumiDataItem.__table__).values(batch)
                    stmt = stmt.on_conflict_do_update(
                        index_elements=["bgm_id"],
                        set_={
                            "tmdb_id": stmt.excluded.tmdb_id,
                            "media_type": stmt.excluded.media_type,
                            "mal_id": stmt.excluded.mal_id,
                            "anilist_id": stmt.excluded.anilist_id,
                            "anidb_id": stmt.excluded.anidb_id,
                            "title": stmt.excluded.title,
                            "title_cn": stmt.excluded.title_cn,
                            "raw_data": stmt.excluded.raw_data
                        }
                    )
                    
                    await db.session.execute(stmt)
                    await db.session.commit()
                
                total_written += len(batch)
            
            await BangumiDataItemService.save_sync_status(items_count, total_written)
            
            logger.info(f"[BangumiData] ✅ 同步成功: {total_written} 条记录")
            logger.info("=" * 50)
            
            return {
                "success": True,
                "message": f"成功同步 {total_written} 条映射记录",
                "count": total_written
            }
        except Exception as e:
            logger.error(f"[BangumiData] ❌ 数据库写入失败: {e}")
            return {"success": False, "message": f"数据库写入失败: {e}"}
    
    @staticmethod
    async def lookup(bgm_id: int) -> Optional[Dict]:
        try:
            async with db.session_scope():
                stmt = select(BangumiDataItem).where(BangumiDataItem.bgm_id == bgm_id)
                result = await db.session.execute(stmt)
                mapping = result.scalars().first()
                
                if mapping:
                    logger.debug(f"[BangumiData] 📋 命中: BGM:{bgm_id} -> TMDB:{mapping.tmdb_id} ({mapping.media_type})")
                    return {
                        "bgm_id": mapping.bgm_id,
                        "tmdb_id": mapping.tmdb_id,
                        "media_type": mapping.media_type,
                        "mal_id": mapping.mal_id,
                        "anilist_id": mapping.anilist_id,
                        "anidb_id": mapping.anidb_id,
                        "title": mapping.title,
                        "title_cn": mapping.title_cn
                    }
                else:
                    logger.debug(f"[BangumiData] ❓ 未命中: BGM:{bgm_id}")
        except Exception as e:
            logger.warning(f"[BangumiData] ⚠️ 查询异常: {e}")
        return None
    
    @staticmethod
    async def get_stats() -> Dict[str, Any]:
        try:
            async with db.session_scope():
                from sqlalchemy import text
                
                total_result = await db.session.execute(
                    text("SELECT COUNT(*) FROM public.bangumi_data_item")
                )
                total = total_result.scalar() or 0
                
                type_result = await db.session.execute(
                    text("SELECT media_type, COUNT(*) as cnt FROM public.bangumi_data_item GROUP BY media_type")
                )
                by_type = {row[0]: row[1] for row in type_result.fetchall()}
            
            status = await BangumiDataItemService.get_sync_status()
                
            return {
                "total": total,
                "by_type": by_type,
                "last_sync": status.get("last_sync_time"),
                "items_count": status.get("items_count"),
                "mapping_count": status.get("mapping_count")
            }
        except Exception as e:
            logger.error(f"[BangumiData] ❌ 获取统计失败: {e}")
            return {"total": 0, "by_type": {}}


bgm_mapping_service = BangumiDataItemService()
