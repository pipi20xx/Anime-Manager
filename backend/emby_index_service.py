"""
Emby 库索引服务 — 提供索引表的异步 CRUD 操作和同步逻辑。
"""
import logging
from typing import List, Dict, Set, Optional, Any
from datetime import datetime, timedelta
from sqlmodel import select, delete

from database import DBService
from models import EmbyMediaIndex

logger = logging.getLogger(__name__)

# 同步间隔（秒）— 与 main.py 中的 _emby_index_sync_loop 保持一致
SYNC_INTERVAL_SECONDS = 86400  # 24 小时

# 模块级同步状态跟踪（进程内）
# None = 从未同步；-1 = 上次同步失败；>=0 = 上次同步的条目数
_last_sync_time: Optional[datetime] = None
_last_sync_count: Optional[int] = None
_sync_loop_running: bool = False


def mark_sync_loop_running(running: bool) -> None:
    """标记后台同步循环是否在运行（由 main.py 调用）。"""
    global _sync_loop_running
    _sync_loop_running = running


async def init_status_from_db() -> None:
    """
    从数据库索引表初始化同步状态（用于启动时索引非空的情况）。
    读取最新一条记录的 sync_at 作为上次同步时间，统计总条目数。
    """
    global _last_sync_time, _last_sync_count
    try:
        async with DBService().session_scope() as session:
            from sqlalchemy import func
            count_stmt = select(func.count(EmbyMediaIndex.id))
            total = (await session.execute(count_stmt)).scalar() or 0

            if total > 0:
                latest_stmt = select(func.max(EmbyMediaIndex.sync_at))
                latest = (await session.execute(latest_stmt)).scalar()
                _last_sync_time = latest
                _last_sync_count = total
                logger.info(f"[Emby索引] 从数据库恢复状态: {total} 条, 上次同步 {latest}")
    except Exception as e:
        logger.warning(f"[Emby索引] 从数据库初始化状态失败: {e}")


def get_emby_index_status() -> Dict[str, Any]:
    """
    返回 Emby 索引同步的当前状态，供服务状态展示使用。
    """
    next_run = None
    if _last_sync_time is not None:
        next_run = (_last_sync_time + timedelta(seconds=SYNC_INTERVAL_SECONDS)).isoformat()

    return {
        "last_sync_time": _last_sync_time.isoformat() if _last_sync_time else None,
        "next_sync_time": next_run,
        "last_sync_count": _last_sync_count,
        "loop_running": _sync_loop_running,
        "interval_seconds": SYNC_INTERVAL_SECONDS,
    }


async def get_index_titles(tmdb_id: str, media_type: str) -> List[str]:
    """
    从索引表中查找指定 TMDB ID + 类型的标题列表（去重）。
    media_type 为 Emby 内部类型: "Movie" 或 "Series"。
    """
    try:
        async with DBService().session_scope() as session:
            stmt = select(EmbyMediaIndex).where(
                EmbyMediaIndex.tmdb_id == str(tmdb_id),
                EmbyMediaIndex.media_type == media_type
            )
            result = await session.execute(stmt)
            entries = result.scalars().all()
            titles = list(set(e.title for e in entries))
            if titles:
                logger.debug(f"索引命中: tmdb_id={tmdb_id} type={media_type} titles={titles}")
            return titles
    except Exception as e:
        logger.warning(f"索引查询失败 tmdb_id={tmdb_id}: {e}")
        return []


def _media_type_tmdb_to_emby(tmdb_media_type: str) -> str:
    """将各种 media_type 映射为 Emby 内部类型 ('Movie'/'Series')。"""
    return 'Movie' if tmdb_media_type in ('movie', '电影') else 'Series'


async def wrap_emby_with_index(emby, tmdb_id: str, media_type: str):
    """
    为 EmbyClient 设置索引上下文并返回清理回调。
    media_type 接受: "Movie"/"Series"/"movie"/"tv"/"剧集"/"电影"
    
    用法:
        cleanup = await wrap_emby_with_index(emby, tmdb_id, media_type)
        try:
            result = emby.check_movie_exists(tmdb_id)
        finally:
            await cleanup()
    """
    emby_type = _media_type_tmdb_to_emby(media_type)
    titles = await get_index_titles(tmdb_id, emby_type)
    if titles:
        emby.set_index_context(titles)

    async def cleanup():
        wb = emby.clear_index_context()
        if wb:
            await writeback_entries(wb)

    return cleanup


async def writeback_entries(entries: List[Dict]):
    """
    将 EMBY 搜索发现的条目回写到索引表 (INSERT OR IGNORE)。
    entries: [{"tmdb_id": str, "media_type": str, "emby_item_id": str, "title": str}]
    """
    if not entries:
        return

    # 先去重
    keys: Set[str] = set()
    deduped = []
    for e in entries:
        key = f"{e['tmdb_id']}|{e['media_type']}|{e['emby_item_id']}"
        if key not in keys:
            keys.add(key)
            deduped.append(e)

    try:
        async with DBService().session_scope() as session:
            for e in deduped:
                stmt = select(EmbyMediaIndex).where(
                    EmbyMediaIndex.tmdb_id == str(e['tmdb_id']),
                    EmbyMediaIndex.media_type == e['media_type'],
                    EmbyMediaIndex.emby_item_id == e['emby_item_id']
                )
                r = await session.execute(stmt)
                if not r.scalars().first():
                    session.add(EmbyMediaIndex(
                        tmdb_id=str(e['tmdb_id']),
                        media_type=e['media_type'],
                        emby_item_id=e['emby_item_id'],
                        title=e['title'],
                        sync_at=datetime.now()
                    ))
            await session.commit()
            logger.info(f"回写索引: {len(deduped)} 条新记录")
    except Exception as e:
        logger.warning(f"回写索引失败: {e}")


async def is_index_empty() -> bool:
    """检查索引表是否为空。"""
    try:
        async with DBService().session_scope() as session:
            stmt = select(EmbyMediaIndex).limit(1)
            result = await session.execute(stmt)
            return result.scalars().first() is None
    except Exception:
        return True


async def sync_index() -> int:
    """
    从 Emby 库拉取所有带 TMDB ID 的媒体项，全量重建索引。
    返回同步的条目数，-1 表示失败。
    """
    global _last_sync_time, _last_sync_count
    import asyncio
    from emby_client import get_emby_client

    logger.info("开始同步 Emby 库索引...")

    def _fetch():
        emby = get_emby_client()
        return emby.fetch_all_items_brief()

    try:
        items = await asyncio.to_thread(_fetch)
    except Exception as e:
        logger.error(f"同步索引: Emby 请求失败: {e}")
        _last_sync_count = -1
        return -1

    if not items:
        logger.info("同步索引: Emby 库中没有带 TMDB ID 的条目")
        _last_sync_time = datetime.now()
        _last_sync_count = 0
        return 0

    try:
        async with DBService().session_scope() as session:
            await session.execute(delete(EmbyMediaIndex))
            now = datetime.now()
            for item in items:
                session.add(EmbyMediaIndex(
                    tmdb_id=item['tmdb_id'],
                    media_type=item['media_type'],
                    emby_item_id=item['emby_item_id'],
                    title=item['title'],
                    sync_at=now
                ))
            await session.commit()
        _last_sync_time = datetime.now()
        _last_sync_count = len(items)
        logger.info(f"同步索引完成: {len(items)} 条")
        return len(items)
    except Exception as e:
        logger.error(f"同步索引: 写入失败: {e}")
        _last_sync_count = -1
        return -1
