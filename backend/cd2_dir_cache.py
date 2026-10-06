"""
CD2 目录快照缓存（方案B）
- 锁定的目录：所有读路径走本地快照，0 API
- 未锁定的目录：实时查询，无任何副作用（不写缓存）
- 快照只产生于：lock_dir / lock_subtree / refresh_dir / webhook 事件喂快照（删除事件会清除对应子树快照）
- 缓存键 = CD2 内部云路径，全局共享（不绑定单个任务）
- 删除/删除校验等需要新鲜数据的路径不经过本模块（保持直连 GetSubFiles）
"""
import asyncio
import logging
import posixpath
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from database import db
from models import Cd2DirCache
from logger import log_audit
from task_history import start_task, log_task, finish_task

logger = logging.getLogger(__name__)


async def _record_task(action: str, lines: List[str], processed: int = 0, status: str = "completed"):
    """把目录缓存操作记入任务中心（独立分类：CD2目录缓存），失败不影响主流程"""
    task_id = f"cd2cache_{uuid.uuid4().hex[:8]}"
    try:
        await start_task(task_id, "CD2目录缓存", action)
        for line in lines:
            if line:
                await log_task(task_id, line)
        await finish_task(task_id, status, processed)
    except Exception as e:
        logger.warning(f"[CD2目录缓存] 任务中心记录失败: {e}")

_BULK_CHUNK = 500


def _normalize_path(path: str) -> str:
    """统一为无尾斜杠的绝对云路径（根为 /）"""
    p = '/' + (path or '').lstrip('/')
    return p.rstrip('/') or '/'


async def get_snapshot(path: str) -> Optional[Dict[str, Any]]:
    """读取快照行，返回 {entries, locked, fetched_at}；无行返回 None"""
    p = _normalize_path(path)
    async with db.session_scope():
        row = await db.first(Cd2DirCache, select(Cd2DirCache).where(Cd2DirCache.path == p))
        if not row:
            return None
        return {
            "entries": list(row.entries or []),
            "locked": bool(row.locked),
            "fetched_at": row.fetched_at,
        }


async def get_snapshot_entries(path: str) -> Optional[List[Dict[str, Any]]]:
    """锁定目录返回快照条目列表；未锁定/不存在返回 None（供扫描器判断）"""
    snap = await get_snapshot(path)
    if snap and snap["locked"]:
        return snap["entries"]
    return None


async def is_locked(path: str) -> bool:
    snap = await get_snapshot(path)
    return bool(snap and snap["locked"])


async def get_locked_flags(paths: List[str]) -> Set[str]:
    """批量查哪些路径已锁定（供前端目录徽标），返回锁定的路径集合"""
    normalized = [_normalize_path(p) for p in (paths or []) if p]
    if not normalized:
        return set()
    async with db.session_scope():
        result = await db.session.execute(
            select(Cd2DirCache.path).where(Cd2DirCache.path.in_(normalized), Cd2DirCache.locked == True)  # noqa: E712
        )
        return {r for (r,) in result.all()}


async def list_dir_via_cache(client, path: str, refresh: bool = False) -> Dict[str, Any]:
    """
    CD2 目录列表统一读入口。
    - 锁定：返回快照（refresh=True 时先重取快照，失败回退旧快照）
    - 未锁定：实时查询（不写缓存）
    返回 browse_files 同款结构，附加 locked / from_cache 标记。
    """
    p = _normalize_path(path)
    snap = await get_snapshot(p)
    if snap and snap["locked"]:
        from_cache = True
        if refresh:
            try:
                snap = await refresh_dir(client, p)
                from_cache = False  # 刚重取过的就是新鲜数据
                counts = {k: snap.get(k, 0) for k in ("file_count", "dir_count")}
                asyncio.create_task(_record_task(
                    "手动刷新快照",
                    [f"路径: {p}", f"快照更新: {counts['file_count']} 文件 / {counts['dir_count']} 目录"],
                ))
            except Exception as e:
                logger.warning(f"[CD2目录缓存] 刷新快照失败 {p}: {e}，回退旧快照")
        entries = snap["entries"]
        return {
            "success": True,
            "path": p,
            "entries": entries,
            "total": len(entries),
            "can_offline": any(e.get("can_offline_download") for e in entries),
            "locked": True,
            "from_cache": from_cache,
            "fetched_at": snap["fetched_at"].isoformat() if snap.get("fetched_at") else None,
        }

    result = await asyncio.to_thread(client.browse_files, p, refresh)
    result.setdefault("locked", False)
    result["from_cache"] = False
    return result


def _counts(entries: List[Dict[str, Any]]) -> Dict[str, int]:
    dir_count = sum(1 for e in entries if e.get("is_dir"))
    return {"file_count": len(entries) - dir_count, "dir_count": dir_count}


async def _upsert_snapshot(path: str, entries: List[Dict[str, Any]], locked: bool = True):
    p = _normalize_path(path)
    counts = _counts(entries)
    async with db.session_scope():
        row = await db.first(Cd2DirCache, select(Cd2DirCache).where(Cd2DirCache.path == p))
        if row:
            row.entries = entries
            row.locked = locked
            row.file_count = counts["file_count"]
            row.dir_count = counts["dir_count"]
            row.fetched_at = datetime.now()
            await db.save(row)
        else:
            await db.save(Cd2DirCache(path=p, entries=entries, locked=locked,
                                      fetched_at=datetime.now(), **counts))
    return counts


async def lock_dir(client, path: str) -> Dict[str, Any]:
    """锁定目录：拉一次最新列表 → 存快照 → 置 locked。此后读路径 0 API。"""
    p = _normalize_path(path)
    result = await asyncio.to_thread(client.browse_files, p, False)
    if not result.get("success"):
        return {"success": False, "message": result.get("message", "列目录失败")}
    counts = await _upsert_snapshot(p, result.get("entries", []), locked=True)
    logger.info(f"[CD2目录缓存] 已锁定: {p} ({counts['file_count']} 文件 / {counts['dir_count']} 目录)")
    try:
        await _record_task("锁定目录", [
            f"路径: {p}",
            f"快照: {counts['file_count']} 文件 / {counts['dir_count']} 目录",
        ])
    except Exception as e:
        logger.warning(f"[CD2目录缓存] 记录任务失败: {e}")
    return {"success": True, "path": p, **counts}


async def refresh_dir(client, path: str) -> Dict[str, Any]:
    """重取快照并保持锁定（force_refresh 绕过 CD2 自身缓存，保证拿到的确实是新数据）"""
    p = _normalize_path(path)
    result = await asyncio.to_thread(client.browse_files, p, True)
    if not result.get("success"):
        raise RuntimeError(result.get("message", "列目录失败"))
    counts = await _upsert_snapshot(p, result.get("entries", []), locked=True)
    logger.debug(f"[CD2目录缓存] 快照已刷新: {p}")
    return {"entries": result.get("entries", []), "locked": True, "fetched_at": datetime.now(), **counts}


_bg_tasks: Set["asyncio.Task"] = set()
_lock_inflight: Set[str] = set()


def spawn_background(coro) -> "asyncio.Task":
    """后台任务启动器：持有引用防止长任务被 GC，完成自动清理"""
    task = asyncio.create_task(coro)
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)
    return task


async def lock_subtree(client, root: str) -> Dict[str, Any]:
    """
    递归锁定子树（由调用方以后台任务方式启动）：scan_path 遍历（本身吃缓存，
    未锁目录才付 API），把发现的全部目录连同各自快照批量置 locked。
    进度实时写入任务中心，关闭页面不影响执行。
    """
    from strm.cd2_indexer import CD2Indexer

    p = _normalize_path(root)
    if p in _lock_inflight:
        return {"success": False, "message": "该目录的递归锁定已在后台进行中，请勿重复触发"}
    _lock_inflight.add(p)

    task_id = f"cd2cache_{uuid.uuid4().hex[:8]}"
    try:
        if not client.logged_in or not client.token:
            if not await client.login_async():
                await start_task(task_id, "CD2目录缓存", f"递归锁定子树: {p}")
                await log_task(task_id, "❌ CD2 登录失败", "ERROR")
                await finish_task(task_id, "error", 0)
                return {"success": False, "message": "CD2 登录失败"}

        await start_task(task_id, "CD2目录缓存", f"递归锁定子树: {p}")
        await log_task(task_id, f"根目录: {p}（已锁定的目录走快照，0 API）")

        indexer = CD2Indexer(client, max_workers=4)
        scanned = 0

        async def on_progress(path: str):
            nonlocal scanned
            scanned += 1
            if scanned == 1 or scanned % 20 == 0:
                await log_task(task_id, f"[{scanned}] {path}")

        tree = await indexer.scan_path(p, force_refresh=False, on_progress=on_progress)
        failed_dirs = set(getattr(indexer, "failed_dirs", None) or [])
        if not isinstance(tree, dict) or not tree:
            await log_task(task_id, "❌ 子树扫描失败，未能获取云端数据", "ERROR")
            await finish_task(task_id, "error", 0)
            return {"success": False, "message": "子树扫描失败，未能获取云端数据"}

        now = datetime.now()
        values = []
        for dir_path, items in tree.items():
            entries = [
                {
                    "name": it.get("name"),
                    "path": it.get("path"),
                    "is_dir": bool(it.get("is_dir")),
                    "size": int(it.get("size") or 0),
                    "write_time": int(it.get("write_time") or 0),
                    "is_forbidden": bool(it.get("is_forbidden")),
                    "can_offline_download": bool(it.get("can_offline_download")),
                }
                for it in (items or [])
            ]
            counts = _counts(entries)
            values.append({"path": _normalize_path(dir_path), "entries": entries, "locked": True,
                           "fetched_at": now, **counts})

        async with db.session_scope():
            for i in range(0, len(values), _BULK_CHUNK):
                chunk = values[i:i + _BULK_CHUNK]
                stmt = pg_insert(Cd2DirCache.__table__).values(chunk)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["path"],
                    set_={
                        "entries": stmt.excluded.entries,
                        "locked": stmt.excluded.locked,
                        "file_count": stmt.excluded.file_count,
                        "dir_count": stmt.excluded.dir_count,
                        "fetched_at": stmt.excluded.fetched_at,
                    },
                )
                await db.session.execute(stmt)

        logger.info(f"[CD2目录缓存] 子树已锁定: {p}（共 {len(values)} 个目录，拉取失败 {len(failed_dirs)}）")
        await log_task(task_id, f"✅ 已锁定 {len(values)} 个目录")
        if failed_dirs:
            await log_task(task_id, f"⚠️ {len(failed_dirs)} 个目录拉取失败（未锁定，可稍后重试）", "ERROR")
        await finish_task(task_id, "completed", len(values))

        result = {"success": True, "path": p, "dir_count": len(values)}
        if failed_dirs:
            # 失败分支保持未锁定（不会缓存错误数据），如实上报供用户重试
            result["failed_count"] = len(failed_dirs)
            result["message"] = f"已锁定 {len(values)} 个目录，{len(failed_dirs)} 个目录拉取失败（未锁定，可稍后重试）"
        return result
    except Exception as e:
        logger.error(f"[CD2目录缓存] 递归锁定异常 {p}: {e}")
        try:
            await log_task(task_id, f"❌ 异常终止: {e}", "ERROR")
            await finish_task(task_id, "error", 0)
        except Exception:
            pass
        return {"success": False, "message": str(e)}
    finally:
        _lock_inflight.discard(p)


async def unlock_path(path: str) -> bool:
    """解锁目录：删除缓存行，恢复实时"""
    p = _normalize_path(path)
    async with db.session_scope():
        row = await db.first(Cd2DirCache, select(Cd2DirCache).where(Cd2DirCache.path == p))
        if not row:
            return False
        await db.delete(row)
    logger.info(f"[CD2目录缓存] 已解锁: {p}")
    try:
        await _record_task("解锁目录", [f"路径: {p}（快照已删除，恢复实时）"])
    except Exception as e:
        logger.warning(f"[CD2目录缓存] 记录任务失败: {e}")
    return True


def _subtree_cond(p: str):
    """目录自身及全部子孙的缓存行匹配条件"""
    return (Cd2DirCache.path == p) | Cd2DirCache.path.startswith(p.rstrip('/') + '/', autoescape=True)


async def unlock_subtree(path: str) -> int:
    """递归解锁：删除目录自身及全部子孙的缓存行"""
    p = _normalize_path(path)
    async with db.session_scope():
        result = await db.session.execute(delete(Cd2DirCache).where(_subtree_cond(p)))
    logger.info(f"[CD2目录缓存] 子树已解锁: {p}（{result.rowcount} 个目录）")
    if result.rowcount > 0:
        try:
            await _record_task("递归解锁子树", [f"根目录: {p}", f"清除 {result.rowcount} 个快照"],
                               processed=result.rowcount)
        except Exception as e:
            logger.warning(f"[CD2目录缓存] 记录任务失败: {e}")
    return result.rowcount


async def purge_subtree(path: str) -> int:
    """
    目录在云端被删除后清除其自身及全部子孙的快照行（webhook 删除事件触发）。
    残留的锁定行会污染缓存统计和前端锁定徽标；行数 0 时静默，不打扰任务中心。
    """
    p = _normalize_path(path)
    async with db.session_scope():
        result = await db.session.execute(delete(Cd2DirCache).where(_subtree_cond(p)))
    if result.rowcount > 0:
        logger.info(f"[CD2目录缓存] 目录已删除，清理其快照: {p}（{result.rowcount} 行）")
        log_audit("CD2目录缓存", "事件保鲜", f"目录已删除，清理其快照: {p}（{result.rowcount} 行）")
    return result.rowcount


async def stats() -> Dict[str, Any]:
    async with db.session_scope():
        result = await db.session.execute(
            select(Cd2DirCache.file_count, Cd2DirCache.dir_count, Cd2DirCache.fetched_at)
            .where(Cd2DirCache.locked == True)  # noqa: E712
        )
        rows = result.all()
    return {
        "locked_dirs": len(rows),
        "total_files": sum(r[0] or 0 for r in rows),
        "total_dirs": sum(r[1] or 0 for r in rows),
        "oldest_fetch": min((r[2] for r in rows), default=None).isoformat() if rows else None,
    }


# 事件保鲜防抖：同一目录的事件风暴合并为一次刷新，避免逐文件打 API
_REFRESH_DEBOUNCE_SECONDS = 5.0
_pending_refresh_tasks: Dict[str, "asyncio.Task"] = {}


def _schedule_refresh(target: str) -> None:
    existing = _pending_refresh_tasks.get(target)
    if existing and not existing.done():
        return
    _pending_refresh_tasks[target] = asyncio.create_task(_debounced_refresh(target))


async def _debounced_refresh(target: str) -> None:
    try:
        await asyncio.sleep(_REFRESH_DEBOUNCE_SECONDS)
        lines = await _refresh_locked_chain(target)
        if lines:
            await _record_task("事件保鲜", lines)
    except Exception as e:
        logger.warning(f"[CD2目录缓存] 事件刷新快照失败 ({target}): {e}")
        try:
            await _record_task("事件保鲜", [f"⚠️ 快照刷新失败: {target}", str(e)], status="error")
        except Exception:
            pass
    finally:
        _pending_refresh_tasks.pop(target, None)


async def _refresh_locked_chain(affected_dir: str) -> Optional[List[str]]:
    """
    事件保鲜核心逻辑：
    1) 受影响目录自身已锁定 → 重取快照（其内容发生了变化）
    2) 自身未锁定 → 向上找最近的锁定祖先，若其快照缺失通向本目录的下一级条目
       （新建目录尚未入快照），重取该祖先——覆盖"往锁定目录里复制新文件夹、
       CD2 只发文件事件"导致的快照失明；祖先快照已包含该条目则不打 API
    返回动作明细（未触发任何刷新时为 None）。
    """
    affected = _normalize_path(affected_dir)

    snap = await get_snapshot(affected)
    if snap and snap["locked"]:
        from routers.cd2 import _get_cd2_client
        counts = await refresh_dir(_get_cd2_client(), affected)
        log_audit("CD2目录缓存", "事件保鲜", f"内容变更，已重取快照: {affected}")
        logger.info(f"[CD2目录缓存] 事件触发快照刷新: {affected}")
        return [
            f"内容变更，重取快照: {affected}",
            f"快照更新: {counts.get('file_count', 0)} 文件 / {counts.get('dir_count', 0)} 目录",
        ]

    child = affected
    cur = posixpath.dirname(child) or '/'
    while True:
        anc_snap = await get_snapshot(cur)
        if anc_snap and anc_snap["locked"]:
            entries = {e.get("path") for e in (anc_snap.get("entries") or [])}
            if _normalize_path(child) not in entries:
                from routers.cd2 import _get_cd2_client
                counts = await refresh_dir(_get_cd2_client(), cur)
                log_audit("CD2目录缓存", "事件保鲜", f"发现新增子目录，已补录快照: {cur}（新增: {child}）")
                logger.info(f"[CD2目录缓存] 事件触发快照刷新（新增子目录补录）: {cur}")
                return [
                    f"发现新增子目录: {child}",
                    f"已补录祖先快照: {cur}",
                    f"快照更新: {counts.get('file_count', 0)} 文件 / {counts.get('dir_count', 0)} 目录",
                ]
            return None
        if cur == '/':
            return None
        child = cur
        cur = posixpath.dirname(cur) or '/'


async def feed_event(cloud_path: str, is_dir: bool):
    """
    webhook 事件喂快照：受影响目录已锁定时防抖刷新；自身未锁定时向上检查
    锁定祖先的快照是否需要补录新目录。绝不抛异常——联动主流程不受影响。
    """
    try:
        p = _normalize_path(cloud_path)
        target = p if is_dir else (posixpath.dirname(p) or '/')
        _schedule_refresh(target)
    except Exception as e:
        logger.warning(f"[CD2目录缓存] 事件刷新快照失败 ({cloud_path}): {e}")
