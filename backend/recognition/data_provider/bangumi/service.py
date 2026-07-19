import asyncio
import httpx
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List, Any
from sqlmodel import select
from sqlalchemy.dialects.postgresql import insert

from database import db
from models import BangumiDataItem, BangumiRawCache, DiscoverCache

logger = logging.getLogger("BangumiData")

BANGUMI_DATA_URL = "https://unpkg.com/bangumi-data@0.3/dist/data.json"
SYNC_CACHE_KEY = "bgm_mapping_sync"
SYNC_INTERVAL_DAYS = 7
# 完结超过该天数后，Subject/Episodes 原始响应视为稳定，可直接使用本地缓存
LONG_ENDED_DAYS = 30


class BangumiDataItemService:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @staticmethod
    async def get_sync_status() -> Dict[str, Any]:
        """
        从 bangumi_data_item 表本身获取同步状态（MAX(updated_at) + COUNT(*)）。
        不依赖 discover_cache，清理缓存不会影响同步判断。
        items_count 从 discover_cache 补充（仅用于显示）。
        """
        try:
            async with db.session_scope():
                from sqlalchemy import text
                result = await db.session.execute(
                    text("SELECT MAX(updated_at), COUNT(*) FROM public.bangumi_data_item")
                )
                row = result.fetchone()
                last_sync = row[0] if row else None
                mapping_count = row[1] if row else 0

                content: Dict[str, Any] = {
                    "last_sync_time": last_sync.isoformat() if last_sync else None,
                    "mapping_count": mapping_count,
                }

                # items_count 仅从 discover_cache 补充（远程条目数，仅显示用）
                try:
                    stmt = select(DiscoverCache).where(DiscoverCache.key == SYNC_CACHE_KEY)
                    cache_result = await db.session.execute(stmt)
                    cache = cache_result.scalars().first()
                    if cache and cache.content:
                        content["items_count"] = cache.content.get("items_count")
                        content["version"] = cache.content.get("version")
                except Exception:
                    pass

                return content
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
        with_tmdb_count = 0
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
                # bangumi-data 项目中 site 名大小写不统一（如 "aniList" 为驼峰），
                # 统一转小写比较，避免 anilist_id 永远提取不到的 bug。
                site_name = site.get("site", "").lower()
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
            
            # 只要有 BGM ID 就写入（不再强制要求 TMDB ID），
            # 无 TMDB 映射的条目也可用于每日放送、完结判断、播出星期等场景。
            # 缺失的 tmdb_id 为 None，map_to_tmdb 命中后会自动走兜底算法匹配。
            if bgm_id:
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
                
                # 媒体类型：有 TMDB 映射时以 TMDB 类型为准，无映射时用 bangumi-data 顶层 type 兜底
                if tmdb_id:
                    media_type = "movie" if tmdb_type == "movie" else "tv"
                    with_tmdb_count += 1
                else:
                    media_type = item.get("type", "tv")
                
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
                    "broadcast": item.get("broadcast", ""),
                    "begin": item.get("begin", ""),
                    "end": item.get("end", ""),
                    "raw_data": item
                })
            else:
                skipped_count += 1
        
        logger.info(f"[BangumiData] 📊 解析完成:")
        logger.info(f"[BangumiData]    ├─ TV 剧集: {tv_count} 条")
        logger.info(f"[BangumiData]    ├─ 电影: {movie_count} 条")
        logger.info(f"[BangumiData]    ├─ 含 TMDB 映射: {with_tmdb_count} 条")
        logger.info(f"[BangumiData]    ├─ 跳过 (无 BGM ID): {skipped_count} 条")
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
        
        logger.info(f"[BangumiData] 💾 正在写入数据库 (单事务清空重写)...")
        
        try:
            from sqlalchemy import text
            from sqlalchemy.dialects.postgresql import insert
            
            batch_size = 1000
            total_written = 0
            total_batches = (len(mappings) + batch_size - 1) // batch_size
            
            # 单事务：TRUNCATE + 全量 INSERT，任一批次失败自动 rollback，旧数据保留。
            # 注意：不要在 session_scope 内部中途 commit，否则 TRUNCATE 生效后失败会丢数据。
            async with db.session_scope():
                # 1. 清空旧数据（PG 的 TRUNCATE 是事务性的，rollback 后不生效）
                await db.session.execute(
                    text("TRUNCATE TABLE public.bangumi_data_item")
                )
                logger.info(f"[BangumiData]    ✂️ 已清空旧数据")
                
                # 2. 分批 INSERT（无冲突，已清空）
                for i in range(0, len(mappings), batch_size):
                    batch = mappings[i:i + batch_size]
                    batch_num = i // batch_size + 1
                    logger.info(f"[BangumiData]    批次 {batch_num}/{total_batches}: 写入 {len(batch)} 条")
                    stmt = insert(BangumiDataItem.__table__).values(batch)
                    await db.session.execute(stmt)
                    total_written += len(batch)
                # session_scope 正常退出 → commit；异常 → rollback，TRUNCATE 失效，旧数据保留
            
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

    @staticmethod
    async def is_long_ended(bgm_id: int, days: int = LONG_ENDED_DAYS) -> bool:
        """
        判断指定 Bangumi ID 对应的番剧是否已完结超过指定天数。
        依据 bangumi_data_item.end 列与当前时间比较。
        无 end 或 end 在未来/近期 → 返回 False（数据可能仍在变化）。
        """
        try:
            async with db.session_scope():
                stmt = select(BangumiDataItem.end).where(BangumiDataItem.bgm_id == bgm_id)
                result = await db.session.execute(stmt)
                end_str = result.scalar()
        except Exception as e:
            logger.warning(f"[BangumiData] ⚠️ 查询 end 列异常: {e}")
            return False

        if not end_str:
            return False

        try:
            # 兼容 "2024-03-28T00:00:00.000Z" / "2024-03-28" 等格式
            from datetime import timezone
            end_str = str(end_str).strip()
            # 末尾带 Z 表示 UTC，转成 +00:00 以便 fromisoformat 解析
            if end_str.endswith("Z"):
                end_str = end_str[:-1] + "+00:00"
            end_dt = datetime.fromisoformat(end_str)
            if end_dt.tzinfo is None:
                # 视为 UTC
                end_dt = end_dt.replace(tzinfo=timezone.utc)
            now_utc = datetime.now(timezone.utc)
            return now_utc >= end_dt + timedelta(days=days)
        except Exception as e:
            logger.warning(f"[BangumiData] ⚠️ 解析 end 时间失败 ({end_str}): {e}")
            return False

    @staticmethod
    async def get_broadcast_times(bgm_ids: List[int]) -> Dict[int, Optional[str]]:
        """
        批量查询番剧播出时间（基于 broadcast / begin 字段）。
        返回 {bgm_id: "HH:MM" | "END" | None}；None 表示无数据。
        时间根据 TZ 环境变量转换为本地时区；已完结显示 "END"。
        """
        if not bgm_ids:
            return {}
        try:
            async with db.session_scope():
                stmt = select(
                    BangumiDataItem.bgm_id,
                    BangumiDataItem.broadcast,
                    BangumiDataItem.begin,
                    BangumiDataItem.end,
                ).where(BangumiDataItem.bgm_id.in_(bgm_ids))
                result = await db.session.execute(stmt)
                rows = result.all()
        except Exception as e:
            logger.warning(f"[BangumiData] ⚠️ 批量查询播出时间异常: {e}")
            return {}
        return {row[0]: BangumiDataItemService._parse_broadcast_time(row[1], row[2], row[3]) for row in rows}

    @staticmethod
    async def get_broadcast_weekday_map(bgm_ids: List[int]) -> Dict[int, Optional[int]]:
        """
        批量查询番剧播出星期（基于 broadcast / begin 字段）。
        返回 {bgm_id: 1~7}，其中 1=周一 ... 7=周日。
        - 优先 broadcast，回退 begin
        - 时间按 TZ 环境变量转换为本地时区后取星期
        - 已完结（end 早于今天）仍返回其播出星期，便于在每日放送里显示 END 标签
        - 无数据 → 不包含在返回字典里
        """
        if not bgm_ids:
            return {}
        try:
            async with db.session_scope():
                stmt = select(
                    BangumiDataItem.bgm_id,
                    BangumiDataItem.broadcast,
                    BangumiDataItem.begin,
                ).where(BangumiDataItem.bgm_id.in_(bgm_ids))
                result = await db.session.execute(stmt)
                rows = result.all()
        except Exception as e:
            logger.warning(f"[BangumiData] ⚠️ 批量查询播出星期异常: {e}")
            return {}

        out: Dict[int, Optional[int]] = {}
        for bgm_id, broadcast, begin in rows:
            raw = broadcast or begin
            if not raw:
                continue
            try:
                dt_str = raw
                if raw.startswith("R/"):
                    parts = raw[2:].split("/")
                    if len(parts) >= 1:
                        dt_str = parts[0]
                if dt_str.endswith("Z"):
                    dt_str = dt_str[:-1] + "+00:00"
                dt = datetime.fromisoformat(dt_str)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                try:
                    from zoneinfo import ZoneInfo
                    tz_name = os.environ.get("TZ", "Asia/Shanghai")
                    tz = ZoneInfo(tz_name)
                except ImportError:
                    tz = timezone(timedelta(hours=8))
                local_dt = dt.astimezone(tz)
                # isoweekday: 1=Mon ... 7=Sun
                out[bgm_id] = local_dt.isoweekday()
            except Exception as e:
                logger.warning(f"[BangumiData] ⚠️ 解析播出星期失败 (bgm_id={bgm_id}, raw={raw}): {e}")
                continue
        return out

    @staticmethod
    def _parse_broadcast_time(
        broadcast: Optional[str], begin: Optional[str], end: Optional[str]
    ) -> Optional[str]:
        """
        解析播出时间为 "周X HH:MM"（本地时区）。
        - 优先 broadcast，回退 begin
        - end 已过当天 → 返回 "END"
        - 无数据 → 返回 None
        - 输入格式: "R/1967-04-01T16:00:00.000Z/P7D" 或 "1967-03-31T16:00:00.000Z"
        - 星期以本地时区换算后的日期为准（UTC+8 可能跨天）
        """
        import os
        from datetime import timezone
        try:
            from zoneinfo import ZoneInfo
        except ImportError:
            ZoneInfo = None

        # 已完结检查：end 时间已过当天
        if end:
            try:
                end_str = str(end).strip()
                if end_str.endswith("Z"):
                    end_str = end_str[:-1] + "+00:00"
                end_dt = datetime.fromisoformat(end_str)
                if end_dt.tzinfo is None:
                    end_dt = end_dt.replace(tzinfo=timezone.utc)
                now_utc = datetime.now(timezone.utc)
                if now_utc.date() > end_dt.date():
                    return "END"
            except Exception:
                pass

        # 优先 broadcast，回退 begin
        raw = broadcast or begin
        if not raw:
            return None

        try:
            # 提取 datetime 部分: "R/1967-04-01T16:00:00.000Z/P7D" → "1967-04-01T16:00:00.000Z"
            dt_str = raw
            if raw.startswith("R/"):
                parts = raw[2:].split("/")
                if len(parts) >= 1:
                    dt_str = parts[0]

            # 解析 datetime（UTC，末尾 Z）
            if dt_str.endswith("Z"):
                dt_str = dt_str[:-1] + "+00:00"
            dt = datetime.fromisoformat(dt_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)

            # 转换为 TZ 环境变量指定的本地时区
            tz_name = os.environ.get("TZ", "Asia/Shanghai")
            tz = ZoneInfo(tz_name) if ZoneInfo else timezone(timedelta(hours=8))
            local_dt = dt.astimezone(tz)
            weekday_cn = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'][local_dt.weekday()]
            return f"{weekday_cn} {local_dt.strftime('%H:%M')}"
        except Exception as e:
            logger.warning(f"[BangumiData] ⚠️ 解析播出时间失败 ({raw}): {e}")
            return None

    @staticmethod
    def _parse_broadcast_info(
        broadcast: Optional[str], begin: Optional[str], end: Optional[str]
    ) -> Dict[str, Any]:
        """
        综合解析播出信息，返回:
        - weekday: 1~7 (本地时区)，None 表示无 broadcast/begin 数据
        - time_str: "周X HH:MM" 或 "END" 或 None
        - is_ended: bool，end < 今天
        """
        import os as _os
        try:
            from zoneinfo import ZoneInfo as _ZI
        except ImportError:
            _ZI = None

        # 已完结检查
        is_ended = False
        if end:
            try:
                end_str = str(end).strip()
                if end_str.endswith("Z"):
                    end_str = end_str[:-1] + "+00:00"
                end_dt = datetime.fromisoformat(end_str)
                if end_dt.tzinfo is None:
                    end_dt = end_dt.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc).date() > end_dt.date():
                    is_ended = True
            except Exception:
                pass

        if is_ended:
            return {"weekday": None, "time_str": "END", "is_ended": True}

        raw = broadcast or begin
        if not raw:
            return {"weekday": None, "time_str": None, "is_ended": False}

        try:
            dt_str = raw
            if raw.startswith("R/"):
                parts = raw[2:].split("/")
                if len(parts) >= 1:
                    dt_str = parts[0]
            if dt_str.endswith("Z"):
                dt_str = dt_str[:-1] + "+00:00"
            dt = datetime.fromisoformat(dt_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            tz_name = _os.environ.get("TZ", "Asia/Shanghai")
            tz = _ZI(tz_name) if _ZI else timezone(timedelta(hours=8))
            local_dt = dt.astimezone(tz)
            weekday = local_dt.isoweekday()  # 1=Mon ... 7=Sun
            weekday_cn = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'][weekday - 1]
            return {
                "weekday": weekday,
                "time_str": f"{weekday_cn} {local_dt.strftime('%H:%M')}",
                "is_ended": False
            }
        except Exception as e:
            logger.warning(f"[BangumiData] ⚠️ 解析播出信息失败 ({raw}): {e}")
            return {"weekday": None, "time_str": None, "is_ended": False}

    @staticmethod
    async def get_raw_cache(bgm_id: int) -> Optional[BangumiRawCache]:
        """
        读取本地缓存的 Bangumi 原始 API 响应（Subject / Episodes）。
        """
        try:
            async with db.session_scope():
                stmt = select(BangumiRawCache).where(BangumiRawCache.bgm_id == bgm_id)
                result = await db.session.execute(stmt)
                return result.scalars().first()
        except Exception as e:
            logger.warning(f"[BangumiData] ⚠️ 读取原始缓存异常: {e}")
            return None

    @staticmethod
    async def save_raw_cache(
        bgm_id: int,
        subject_data: Optional[Dict[str, Any]] = None,
        episodes_data: Optional[Dict[str, Any]] = None,
        characters_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        保存/更新 Bangumi 原始 API 响应缓存。
        传入 None 的字段不会覆盖已有值。
        """
        try:
            async with db.session_scope():
                stmt = select(BangumiRawCache).where(BangumiRawCache.bgm_id == bgm_id)
                result = await db.session.execute(stmt)
                existing = result.scalars().first()

                now = datetime.now()
                if existing:
                    if subject_data is not None:
                        existing.subject_data = subject_data
                    if episodes_data is not None:
                        existing.episodes_data = episodes_data
                    if characters_data is not None:
                        existing.characters_data = characters_data
                    existing.fetched_at = now
                    db.session.add(existing)
                else:
                    db.session.add(BangumiRawCache(
                        bgm_id=bgm_id,
                        subject_data=subject_data,
                        episodes_data=episodes_data,
                        characters_data=characters_data,
                        fetched_at=now,
                    ))
                await db.session.commit()
        except Exception as e:
            logger.warning(f"[BangumiData] ⚠️ 保存原始缓存异常: {e}")

    # ===== 缓存预热状态（模块级，跨请求保持） =====
    _warmup_running: bool = False
    _warmup_progress: Dict[str, Any] = {}

    @staticmethod
    async def warmup_raw_cache(force: bool = False) -> Dict[str, Any]:
        """
        预热 Bangumi 详情缓存：遍历 bangumi_data_item 表所有 bgm_id，
        调用 get_subject_details 一次性填充两层缓存：
          - bangumi_raw_cache（永久，仅完结番剧，由内部 _fetch_subject_raw 写入）
          - discover_cache:detail（7天，加工后展示数据，所有番剧）

        预热后访问季度番剧表/详情页时可直接命中 discover_cache:detail，连加工都省了。
        内部带并发限制（5）和已缓存跳过逻辑（force=False 时跳过 7 天内已缓存的 ID）。

        :param force: True 时强制重新拉取（忽略已有缓存）
        :return: 任务状态
        """
        if BangumiDataItemService._warmup_running:
            return {"success": False, "message": "预热任务正在运行中，请等待完成"}

        BangumiDataItemService._warmup_running = True
        BangumiDataItemService._warmup_progress = {
            "total": 0, "done": 0, "success": 0, "skipped": 0, "failed": 0,
            "current_id": None, "started_at": datetime.now().isoformat()
        }

        try:
            # 1. 取出所有 bgm_id
            async with db.session_scope():
                from sqlalchemy import text
                result = await db.session.execute(
                    text("SELECT bgm_id FROM public.bangumi_data_item ORDER BY bgm_id")
                )
                all_ids: List[int] = [row[0] for row in result.fetchall() if row[0]]

            total = len(all_ids)
            BangumiDataItemService._warmup_progress["total"] = total
            logger.info(f"[BangumiData] 🔥 开始预热 Subject 缓存，共 {total} 个 ID (force={force})")

            if total == 0:
                BangumiDataItemService._warmup_progress["done"] = 0
                return {"success": True, "message": "bangumi_data_item 表为空，无需预热", "count": 0}

            # 2. 延迟导入，避免循环依赖
            from .client import BangumiProvider

            # 3. 并发拉取（信号量限制为 5，与现有代码一致）
            semaphore = asyncio.Semaphore(5)

            async def _warmup_one(bgm_id: int):
                async with semaphore:
                    # 非强制模式：7天内已有 detail 缓存的跳过
                    if not force:
                        from metadata.meta_cache import MetaCacheManager
                        existing = await MetaCacheManager.get_discover_cache(f"bangumi:detail:{bgm_id}")
                        if existing:
                            BangumiDataItemService._warmup_progress["skipped"] += 1
                            BangumiDataItemService._warmup_progress["done"] += 1
                            return

                    BangumiDataItemService._warmup_progress["current_id"] = bgm_id
                    try:
                        # 调用统一入口 get_subject_details：
                        #   完结番剧 → _fetch_subject_raw 写 bangumi_raw_cache(永久) → 加工写 discover_cache:detail(7天)
                        #   未完结番剧 → _fetch_subject_raw 打API → 加工写 discover_cache:detail(7天)
                        data = await BangumiProvider.get_subject_details(bgm_id)
                        if data:
                            BangumiDataItemService._warmup_progress["success"] += 1
                        else:
                            BangumiDataItemService._warmup_progress["failed"] += 1
                    except Exception as e:
                        logger.warning(f"[BangumiData] ⚠️ 预热 ID:{bgm_id} 失败: {e}")
                        BangumiDataItemService._warmup_progress["failed"] += 1
                    finally:
                        BangumiDataItemService._warmup_progress["done"] += 1

            # 分批处理，避免一次性创建过多协程（每批 50 个）
            batch_size = 50
            for i in range(0, total, batch_size):
                batch = all_ids[i:i + batch_size]
                await asyncio.gather(*[_warmup_one(bid) for bid in batch])
                # 进度日志
                p = BangumiDataItemService._warmup_progress
                logger.info(
                    f"[BangumiData] 🔥 预热进度: {p['done']}/{p['total']} "
                    f"(成功 {p['success']} | 跳过 {p['skipped']} | 失败 {p['failed']})"
                )
                # WS 推送进度
                try:
                    from event_broadcaster import EventBroadcaster
                    await EventBroadcaster.broadcast_warmup_progress(
                        BangumiDataItemService.get_warmup_status()
                    )
                except Exception:
                    pass

            p = BangumiDataItemService._warmup_progress
            logger.info(
                f"[BangumiData] ✅ 预热完成: 共 {p['total']} 个 | "
                f"成功 {p['success']} | 跳过 {p['skipped']} | 失败 {p['failed']}"
            )
            return {
                "success": True,
                "message": f"预热完成: 成功 {p['success']} | 跳过 {p['skipped']} | 失败 {p['failed']}",
                "total": p["total"], "success_count": p["success"],
                "skipped": p["skipped"], "failed": p["failed"]
            }
        except Exception as e:
            logger.error(f"[BangumiData] ❌ 预热任务异常: {e}", exc_info=True)
            return {"success": False, "message": f"预热任务异常: {e}"}
        finally:
            BangumiDataItemService._warmup_running = False
            BangumiDataItemService._warmup_progress["finished_at"] = datetime.now().isoformat()
            # WS 推送最终状态
            try:
                from event_broadcaster import EventBroadcaster
                await EventBroadcaster.broadcast_warmup_progress(
                    BangumiDataItemService.get_warmup_status()
                )
            except Exception:
                pass

    @staticmethod
    def get_warmup_status() -> Dict[str, Any]:
        """获取预热任务状态"""
        return {
            "running": BangumiDataItemService._warmup_running,
            "progress": dict(BangumiDataItemService._warmup_progress),
        }


bangumi_data_service = BangumiDataItemService()
