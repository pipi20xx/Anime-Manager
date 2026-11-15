# -*- coding: utf-8 -*-
"""番剧分季拆分 · 规则与黑名单存储（PostgreSQL）与进程内编译缓存。

识别热路径（`recognition/context.py`）只调用 `as_render_words()`：同步、纯内存、零 I/O。
数据库只在三种时机访问：启动、保存规则 / 增删黑名单、后台 30s 版本轮询。

两张表各管一件事：
- `season_split_rules`：生效规则 → 编译好的渲染词文本；
- `season_split_blacklist`：永不套用分季的番（黑名单），快照按 tmdb_id 存整行（判定记录也在里面）。
两者的 `updated_at` 最大值 + 行数一起构成版本号，轮询时任一表变了就整体重载。
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
# 黑名单快照：{tmdb_id: 行数据}（与 _ROWS 同一次 reload 刷新）
# 存整行而不是只存 ID：识别链路判断「前提变了没」要读 reason / seasons_fp / use_absolute，
# 走内存就不必为每集识别多打一次库。
_BLOCKED: Dict[int, Dict[str, Any]] = {}
_VERSION: str = ""
_LOADED_AT: Optional[datetime] = None
_LOCK = threading.Lock()
_WATCHER: Optional[asyncio.Task] = None
REFRESH_INTERVAL = 30

# 运行时给分季规则打的来源标记（不落库）。RenderEngine 见到它会把日志来源标成 [分季]，
# 便于和用户自己的「自定义渲染词（私有）」区分开。
SPLIT_MARKER = "[SPLIT]"

# 规则「创建来源」（落库在 season_split_rules.origin），用于规则库卡片上区分：
# manual = 工作台手动生成并保存 / sytmdb = 「导入 SYTMDB」一键导入 / auto = 识别链路自动生成
ORIGIN_MANUAL = "manual"
ORIGIN_SYTMDB = "sytmdb"
ORIGIN_AUTO = "auto"
ORIGINS = (ORIGIN_MANUAL, ORIGIN_SYTMDB, ORIGIN_AUTO)
# 升级前保存的老规则没有来源列（NULL），查询/展示时用这个值代表「历史未知」
LEGACY_ORIGIN = "legacy"

# 黑名单的两种来源（season_split_blacklist.origin）：
# manual = 人加的（只有人能删）/ auto = 判定加的（前提变了会自动解除）
BLACKLIST_ORIGINS = (ORIGIN_MANUAL, ORIGIN_AUTO)


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


def blocked_ids() -> List[int]:
    """当前黑名单快照（排好序，给设置快照 / 页面用）。读内存，不碰数据库。"""
    with _LOCK:
        return sorted(_BLOCKED)


def blocked_rows() -> Dict[int, Dict[str, Any]]:
    """黑名单快照的浅拷贝（调试 / 页面用）。"""
    with _LOCK:
        return {key: dict(value) for key, value in _BLOCKED.items()}


def get_blocked_row(tmdb_id: Any) -> Optional[Dict[str, Any]]:
    """热路径用：黑名单里这一条的判定记录（没有这一条返回 None）。纯内存。"""
    try:
        row = _BLOCKED.get(int(tmdb_id))
    except (TypeError, ValueError):
        return None
    return dict(row) if row else None


def is_blocked(tmdb_id: Any) -> bool:
    """热路径用：这部番是不是在黑名单里（纯内存 dict 查询）。"""
    try:
        return int(tmdb_id) in _BLOCKED
    except (TypeError, ValueError):
        return False


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
        lines: List[str] = []
        for row in _ROWS:
            if row["tmdb_id"] in _BLOCKED:
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
        "blacklist_count": len(_BLOCKED),
        "version": _VERSION,
        "loaded_at": _LOADED_AT.isoformat(sep=" ", timespec="seconds") if _LOADED_AT else None,
        "mode": mode(),
    }


# ---------------------------------------------------------------------------
# 加载 / 刷新
# ---------------------------------------------------------------------------

async def _fetch_version() -> str:
    """两张表的「最大 updated_at + 行数」拼成版本号。

    行数也参与比较：删行不会改变 max(updated_at)，只看时间戳的话多 worker 部署里
    「删了一条规则 / 解除了一条黑名单」要等重启才会被别的进程看到。
    """
    from sqlalchemy import func, select

    from database import db
    from models import SeasonSplitBlacklist, SeasonSplitRule

    async with db.session_scope(force_new=True):
        rules = (await db.session.execute(
            select(func.max(SeasonSplitRule.updated_at), func.count())
        )).first()
        blocked = (await db.session.execute(
            select(func.max(SeasonSplitBlacklist.updated_at), func.count())
        )).first()

    def _part(row) -> str:
        stamp, count = (row if row else (None, 0))
        text = stamp.isoformat() if isinstance(stamp, datetime) else ""
        return f"{text}|{int(count or 0)}"

    return _part(rules) + "#" + _part(blocked)


async def reload() -> int:
    """强制重载全部生效规则 + 黑名单到内存。"""
    global _ROWS, _BLOCKED, _VERSION, _LOADED_AT
    from sqlalchemy import select

    from database import db
    from models import SeasonSplitBlacklist, SeasonSplitRule

    async with db.session_scope(force_new=True):
        result = await db.session.execute(
            select(SeasonSplitRule).where(SeasonSplitRule.status == "active")
        )
        records = list(result.scalars().all())
        blocked_res = await db.session.execute(select(SeasonSplitBlacklist))
        blocked = {int(r.tmdb_id): _blacklist_row(r) for r in blocked_res.scalars().all()}

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
        _BLOCKED = blocked
        _VERSION = version
        _LOADED_AT = datetime.now()
    logger.info(
        f"[分季] 缓存已加载: 规则 {len(rows)} 条 / 黑名单 {len(blocked)} 条（version={version or '-'}）"
    )
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

async def list_rules(status: Optional[str] = None, q: str = "",
                     origin: Optional[str] = None,
                     kind: Optional[str] = None) -> List[dict]:
    from sqlalchemy import or_, select

    from database import db
    from models import SeasonSplitRule

    stmt = select(SeasonSplitRule)
    if status:
        stmt = stmt.where(SeasonSplitRule.status == status)
    if kind == "absolute":
        # 连番号折算：只写渲染词、不写剧集组的那一类（reference 固定为 tmdb）
        stmt = stmt.where(SeasonSplitRule.reference == "tmdb")
    elif kind == "split":
        stmt = stmt.where(or_(SeasonSplitRule.reference.is_(None),
                              SeasonSplitRule.reference != "tmdb"))
    if origin:
        if origin == LEGACY_ORIGIN:
            stmt = stmt.where(SeasonSplitRule.origin.is_(None))
        else:
            stmt = stmt.where(SeasonSplitRule.origin == origin)
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
        for field in ("title", "status", "reference", "render_words", "tmdb_hash", "structure_fp"):
            if field in payload:
                setattr(record, field, payload[field])
        # 来源只在「新建 / 显式指定」时写入；留空 = 不动原值（启停、工作台编辑都不会改掉它）
        origin = (payload.get("origin") or "").strip().lower()
        if origin in ORIGINS:
            record.origin = origin
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
        "origin": record.origin or "",
        "groups": record.groups_json or [],
        "overrides": record.overrides_json or {},
        "excluded": record.excluded_json or [],
        "names": record.names_json or {},
        "mapping": record.mapping_json or {},
        "group_json": record.group_json or {},
        "render_words": record.render_words or "",
        "tmdb_hash": record.tmdb_hash or "",
        "structure_fp": record.structure_fp or "",
        "episode_total": int(record.episode_total or 0),
        "created_at": record.created_at.isoformat(sep=" ", timespec="seconds") if record.created_at else None,
        "updated_at": record.updated_at.isoformat(sep=" ", timespec="seconds") if record.updated_at else None,
    }


# ---------------------------------------------------------------------------
# CRUD · 黑名单（public.season_split_blacklist）
#
# 一部番一条，`origin` 区分「人加的」和「判定加的」；判定字段（reason /
# decided_at / seasons_fp / use_absolute）整体覆盖写入，手动条目写 None 即清空。
# 每条写完都 reload 一次内存快照，识别链路下一部番就能看到（不用等 30s 轮询）。
# ---------------------------------------------------------------------------

def _blacklist_row(record) -> Dict[str, Any]:
    return {
        "tmdb_id": int(record.tmdb_id),
        "origin": record.origin or ORIGIN_MANUAL,
        "reason": record.reason or "",
        "decided_at": record.decided_at.isoformat(sep=" ", timespec="seconds") if record.decided_at else None,
        "seasons_fp": record.seasons_fp or "",
        "use_absolute": record.use_absolute,
        "created_at": record.created_at.isoformat(sep=" ", timespec="seconds") if record.created_at else None,
        "updated_at": record.updated_at.isoformat(sep=" ", timespec="seconds") if record.updated_at else None,
    }


async def list_blacklist() -> List[dict]:
    """整份名单，按入榜时间排（页面展示顺序稳定）。"""
    from sqlalchemy import select

    from database import db
    from models import SeasonSplitBlacklist

    async with db.session_scope(force_new=True):
        result = await db.session.execute(
            select(SeasonSplitBlacklist).order_by(
                SeasonSplitBlacklist.created_at.asc(),
                SeasonSplitBlacklist.tmdb_id.asc(),
            )
        )
        records = list(result.scalars().all())
    return [_blacklist_row(r) for r in records]


async def get_blacklist_entry(tmdb_id: int) -> Optional[dict]:
    from database import db
    from models import SeasonSplitBlacklist

    async with db.session_scope(force_new=True):
        record = await db.session.get(SeasonSplitBlacklist, int(tmdb_id))
        if record is None:
            return None
        data = _blacklist_row(record)
    return data


async def upsert_blacklist(tmdb_id: int, origin: str = ORIGIN_MANUAL,
                           reason: Optional[str] = None,
                           decided_at: Optional[datetime] = None,
                           seasons_fp: Optional[str] = None,
                           use_absolute: Optional[bool] = None,
                           reload_cache: bool = True) -> dict:
    """写入/更新一条黑名单。批量导入时传 reload_cache=False，最后统一 reload 一次。"""
    from database import db
    from models import SeasonSplitBlacklist

    tmdb_id = int(tmdb_id)
    origin = str(origin or "").strip().lower()
    if origin not in BLACKLIST_ORIGINS:
        raise ValueError(f"origin 只能是 {' / '.join(BLACKLIST_ORIGINS)}")

    async with db.session_scope(force_new=True):
        record = await db.session.get(SeasonSplitBlacklist, tmdb_id)
        if record is None:
            record = SeasonSplitBlacklist(tmdb_id=tmdb_id)
            db.session.add(record)
        record.origin = origin
        # 判定字段整体覆盖：手动条目传 None 就等于「没有判定记录」
        record.reason = (reason or None)
        record.decided_at = decided_at
        record.seasons_fp = (seasons_fp or None)
        record.use_absolute = use_absolute
        record.updated_at = datetime.now()
        await db.session.commit()
        await db.session.refresh(record)
        data = _blacklist_row(record)

    if reload_cache:
        await reload()
    return data


async def delete_blacklist(tmdb_id: int) -> Optional[dict]:
    """把某条（手动 / 自动）移出黑名单；不在名单里返回 None。"""
    from database import db
    from models import SeasonSplitBlacklist

    tmdb_id = int(tmdb_id)
    async with db.session_scope(force_new=True):
        record = await db.session.get(SeasonSplitBlacklist, tmdb_id)
        if record is None:
            return None
        data = _blacklist_row(record)
        await db.session.delete(record)
        await db.session.commit()

    await reload()
    return data
