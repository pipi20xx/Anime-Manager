# -*- coding: utf-8 -*-
"""番剧分季拆分 · 规则存储（PostgreSQL）与进程内编译缓存。

识别热路径（`recognition/context.py`）只调用 `as_render_words()`：同步、纯内存、零 I/O。
数据库只在三种时机访问：启动、保存规则、后台 30s 版本轮询。
"""

from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("SeasonSplit")

# 内存快照：[{"tmdb_id": 123, "render_words": "..."}]
_ROWS: List[Dict[str, Any]] = []
_VERSION: str = ""
_LOADED_AT: Optional[datetime] = None
_LOCK = threading.Lock()
_WATCHER: Optional[asyncio.Task] = None
REFRESH_INTERVAL = 30

# 运行时给分季规则打的来源标记（不落库）。RenderEngine 见到它会把日志来源标成 [分季]，
# 便于和用户自己的「自定义渲染词（私有）」区分开。
SPLIT_MARKER = "[SPLIT]"


def _config() -> Dict[str, Any]:
    try:
        from config_manager import ConfigManager
        return ConfigManager.get_config() or {}
    except Exception:
        return {}


def mode(config: Optional[dict] = None) -> str:
    """off / preview / on"""
    cfg = config if isinstance(config, dict) else _config()
    return str(cfg.get("season_split_mode") or "off").strip().lower()


def _blacklist(config: Optional[dict] = None) -> set:
    cfg = config if isinstance(config, dict) else _config()
    out = set()
    for item in cfg.get("season_split_blacklist") or []:
        try:
            out.add(int(item))
        except (TypeError, ValueError):
            continue
    return out


def as_render_words(config: Optional[dict] = None, entry: str = "organize") -> List[str]:
    """给识别链路取当前生效的分季规则（渲染词文本行）。

    - `mode != on` → 空（`preview` 只在页面/调试器里看效果，不注入识别）
    - 命中番剧黑名单 → 跳过
    - `season_split_scope` 控制哪些入口生效（organize / subscription / recognition_test）
    """
    try:
        cfg = config if isinstance(config, dict) else _config()
        if mode(cfg) != "on":
            return []
        scope = cfg.get("season_split_scope")
        if isinstance(scope, dict) and scope:
            if not scope.get(entry, True):
                return []
        if not _ROWS:
            return []
        blocked = _blacklist(cfg)
        lines: List[str] = []
        for row in _ROWS:
            if row["tmdb_id"] in blocked:
                continue
            text = row.get("render_words") or ""
            if not text:
                continue
            for line in text.splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                # 打标：让 RenderEngine 的日志把来源区分成 [分季] 而不是 [私有]
                lines.append(SPLIT_MARKER + stripped)
        return lines
    except Exception as e:  # 绝不允许分季功能影响识别主流程
        logger.warning(f"[分季] 取规则失败，按空处理: {e}")
        return []


def cache_stats() -> Dict[str, Any]:
    return {
        "count": len(_ROWS),
        "version": _VERSION,
        "loaded_at": _LOADED_AT.isoformat(sep=" ", timespec="seconds") if _LOADED_AT else None,
        "mode": mode(),
    }


# ---------------------------------------------------------------------------
# 加载 / 刷新
# ---------------------------------------------------------------------------

async def _fetch_version() -> str:
    from sqlalchemy import func, select

    from database import db
    from models import SeasonSplitRule

    async with db.session_scope(force_new=True):
        result = await db.session.execute(select(func.max(SeasonSplitRule.updated_at)))
        value = result.scalar()
    return value.isoformat() if isinstance(value, datetime) else ""


async def reload() -> int:
    """强制重载全部生效规则到内存。"""
    global _ROWS, _VERSION, _LOADED_AT
    from sqlalchemy import select

    from database import db
    from models import SeasonSplitRule

    async with db.session_scope(force_new=True):
        result = await db.session.execute(
            select(SeasonSplitRule).where(SeasonSplitRule.status == "active")
        )
        records = list(result.scalars().all())

    rows = [
        {
            "tmdb_id": int(r.tmdb_id),
            "title": r.title or "",
            "render_words": r.render_words or "",
            "updated_at": r.updated_at.isoformat() if r.updated_at else "",
        }
        for r in records
        if (r.render_words or "").strip()
    ]
    version = max([r["updated_at"] for r in rows], default="")
    with _LOCK:
        _ROWS = rows
        _VERSION = version
        _LOADED_AT = datetime.now()
    logger.info(f"[分季] 规则缓存已加载: {len(rows)} 条（version={version or '-'}）")
    return len(rows)


async def refresh_if_stale(force: bool = False) -> bool:
    """版本变了才重载。返回是否发生了重载。"""
    try:
        version = await _fetch_version()
        if not force and version and version == _VERSION:
            return False
        await reload()
        return True
    except Exception as e:
        logger.warning(f"[分季] 规则缓存刷新失败: {e}")
        return False


async def start_watcher() -> None:
    """后台轮询（多 worker / 多容器部署时保证 30s 内一致）。"""
    global _WATCHER
    if _WATCHER and not _WATCHER.done():
        return

    async def _loop():
        while True:
            await asyncio.sleep(REFRESH_INTERVAL)
            await refresh_if_stale()

    _WATCHER = asyncio.create_task(_loop())
    logger.info(f"[分季] 缓存轮询已启动（{REFRESH_INTERVAL}s）")


async def stop_watcher() -> None:
    global _WATCHER
    if _WATCHER and not _WATCHER.done():
        _WATCHER.cancel()
        try:
            await _WATCHER
        except (asyncio.CancelledError, Exception):
            pass
    _WATCHER = None


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

async def list_rules(status: Optional[str] = None, q: str = "") -> List[dict]:
    from sqlalchemy import or_, select

    from database import db
    from models import SeasonSplitRule

    stmt = select(SeasonSplitRule)
    if status:
        stmt = stmt.where(SeasonSplitRule.status == status)
    if q:
        keyword = f"%{q}%"
        cond = or_(SeasonSplitRule.title.ilike(keyword))
        if q.isdigit():
            cond = or_(cond, SeasonSplitRule.tmdb_id == int(q))
        stmt = stmt.where(cond)
    stmt = stmt.order_by(SeasonSplitRule.updated_at.desc())
    async with db.session_scope(force_new=True):
        result = await db.session.execute(stmt)
        records = list(result.scalars().all())
    return [_to_dict(r) for r in records]


async def get_rule(tmdb_id: int) -> Optional[dict]:
    from database import db
    from models import SeasonSplitRule

    async with db.session_scope(force_new=True):
        record = await db.session.get(SeasonSplitRule, int(tmdb_id))
        if record is None:
            return None
        data = _to_dict(record)
    return data


async def upsert_rule(payload: dict, reload_cache: bool = True) -> dict:
    """写入/更新一条规则。批量导入时传 reload_cache=False，最后统一 reload 一次。"""
    from database import db
    from models import SeasonSplitRule

    tmdb_id = int(payload["tmdb_id"])
    async with db.session_scope(force_new=True):
        record = await db.session.get(SeasonSplitRule, tmdb_id)
        if record is None:
            record = SeasonSplitRule(tmdb_id=tmdb_id)
            db.session.add(record)
        for field in ("title", "status", "reference", "render_words", "tmdb_hash"):
            if field in payload:
                setattr(record, field, payload[field])
        for field in ("groups_json", "overrides_json", "excluded_json", "names_json",
                      "mapping_json", "group_json"):
            if field in payload and payload[field] is not None:
                setattr(record, field, payload[field])
        if "episode_total" in payload:
            record.episode_total = int(payload.get("episode_total") or 0)
        record.updated_at = datetime.now()
        record.last_compiled_at = datetime.now()
        await db.session.commit()
        await db.session.refresh(record)
        data = _to_dict(record)

    if reload_cache:
        await reload()
    return data


async def delete_rule(tmdb_id: int) -> bool:
    from database import db
    from models import SeasonSplitRule

    async with db.session_scope(force_new=True):
        record = await db.session.get(SeasonSplitRule, int(tmdb_id))
        if record is None:
            return False
        await db.session.delete(record)
        await db.session.commit()
    await reload()
    return True


def _to_dict(record) -> dict:
    return {
        "tmdb_id": int(record.tmdb_id),
        "title": record.title or "",
        "status": record.status or "draft",
        "reference": record.reference or "",
        "groups": record.groups_json or [],
        "overrides": record.overrides_json or {},
        "excluded": record.excluded_json or [],
        "names": record.names_json or {},
        "mapping": record.mapping_json or {},
        "group_json": record.group_json or {},
        "render_words": record.render_words or "",
        "tmdb_hash": record.tmdb_hash or "",
        "episode_total": int(record.episode_total or 0),
        "created_at": record.created_at.isoformat(sep=" ", timespec="seconds") if record.created_at else None,
        "updated_at": record.updated_at.isoformat(sep=" ", timespec="seconds") if record.updated_at else None,
    }
