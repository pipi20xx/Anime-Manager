"""字体导入记录的长期台账（PostgreSQL）。

职责边界：
- 工作目录 `data/fonts/import/<job_id>/` 仍然是**唯一事实来源**：压缩包、report.json、
  commit.json 都在里面（压缩包放任务目录，天然没有同名冲突）；
- 这张表只记元信息与结果，用于「最近导入任务」的长期查询、分页、以及知道压缩包在哪，
  从而支持下载与按保留策略清理。

不抛异常：数据库不可用/表不存在时返回空结果，页面退回磁盘扫描。
"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def _paths(cfg: Optional[Dict[str, Any]], job_id: str) -> Dict[str, Path]:
    from font_core import importer
    return importer.job_paths(cfg, job_id)


def _read_json(path: Path) -> Dict[str, Any]:
    from font_core.importer import _read_json as read_json
    return read_json(path) or {}


def build_record(cfg: Optional[Dict[str, Any]], job_id: str) -> Optional[Dict[str, Any]]:
    """从磁盘读出一份可入库的记录（没有 report 就不算分析过，返回 None）。"""
    paths = _paths(cfg, job_id)
    if not paths["root"].is_dir():
        return None
    meta = _read_json(paths["root"] / "meta.json")
    report = _read_json(paths["report"])
    commit = _read_json(paths["commit"])
    if not report and not meta:
        return None
    archives = report.get("archives") or []
    names = [str(a.get("name") or "") for a in archives if a.get("name")]
    if not names:      # 分析失败时 archives 可能为空，退回归档目录里的实际文件名
        incoming = paths["incoming"]
        try:
            names = [p.name for p in incoming.iterdir() if p.is_file()]
        except OSError:
            names = []
    counts = report.get("counts") or {}
    status = "committed" if commit else ("analyzed" if report.get("success") else "failed")
    created = report.get("created_at") or meta.get("created_at") or ""
    try:
        created_dt = datetime.fromisoformat(created) if created else datetime.now()
    except ValueError:
        created_dt = datetime.now()
    return {
        "job_id": job_id,
        "origin": str(meta.get("origin") or "web"),
        "status": status,
        "archive_names": names,
        "archive_paths": [str(paths["incoming"] / n) for n in names],
        "counts": {
            "new": int(counts.get("new") or 0),
            "duplicate": int(counts.get("duplicate") or 0),
            "conflict": int(counts.get("conflict") or 0),
            "invalid": int(counts.get("invalid") or 0),
        },
        "committed_count": int(commit.get("count") or 0),
        "target": str(commit.get("target") or report.get("target") or ""),
        "message": str(commit.get("message") or report.get("message") or ""),
        "created_at": created_dt,
    }


async def save(cfg: Optional[Dict[str, Any]], job_id: str) -> bool:
    """把磁盘上的 job 元信息 upsert 进表（分析完成/入库完成时调用）。"""
    record = build_record(cfg, job_id)
    if not record:
        return False
    try:
        from sqlmodel import select
        from database import db
        from models import FontImportJob

        async with db.session_scope() as session:
            row = (await session.execute(
                select(FontImportJob).where(FontImportJob.job_id == job_id)
            )).scalars().first()
            if row is None:
                row = FontImportJob(job_id=job_id)
                session.add(row)
            row.origin = record["origin"]
            row.status = record["status"]
            row.archive_names = record["archive_names"]
            row.archive_paths = record["archive_paths"]
            row.counts = record["counts"]
            row.committed_count = record["committed_count"]
            row.target = record["target"]
            row.message = record["message"]
            row.created_at = record["created_at"]
            row.updated_at = datetime.now()
        return True
    except Exception as e:      # 数据库不可用时不影响导入流程
        logger.debug(f"[字体导入记录] 写入失败（忽略）: {type(e).__name__} {e}")
        return False


def _to_summary(row: Any) -> Dict[str, Any]:
    return {
        "job_id": row.job_id,
        "created_at": row.created_at.isoformat(timespec="seconds") if row.created_at else "",
        "origin": row.origin or "web",
        "status": row.status or "",
        "archives": list(row.archive_names or []),
        "counts": dict(row.counts or {}),
        "analyzed": True,
        "committed": (row.status == "committed"),
        "committed_count": int(row.committed_count or 0),
        "target": row.target or "",
        "message": row.message or "",
        "has_archive": any(Path(p).is_file() for p in (row.archive_paths or [])),
        "archive_paths": list(row.archive_paths or []),
    }


async def page(limit: int = 20, offset: int = 0):
    """分页读取（按创建时间倒序）。

    返回 (rows, total)：数据库不可用时 rows 为 None（与“表为空 = []”区分开），
    调用方只有拿到 None 才退回去扫磁盘，避免“清空表后旧任务又从磁盘冒出来”。
    """
    try:
        from sqlmodel import func, select
        from database import db
        from models import FontImportJob

        async with db.session_scope() as session:
            total = int((await session.execute(
                select(func.count()).select_from(FontImportJob)
            )).scalar() or 0)
            rows = (await session.execute(
                select(FontImportJob)
                .order_by(FontImportJob.created_at.desc())
                .offset(max(0, int(offset)))
                .limit(max(1, int(limit)))
            )).scalars().all()
        return [_to_summary(r) for r in rows], total
    except Exception as e:
        logger.debug(f"[字体导入记录] 分页读取失败（忽略）: {type(e).__name__} {e}")
        return None, 0


async def get(job_id: str) -> Optional[Dict[str, Any]]:
    try:
        from sqlmodel import select
        from database import db
        from models import FontImportJob

        async with db.session_scope() as session:
            row = (await session.execute(
                select(FontImportJob).where(FontImportJob.job_id == job_id)
            )).scalars().first()
        return _to_summary(row) if row else None
    except Exception as e:
        logger.debug(f"[字体导入记录] 读取单条失败（忽略）: {type(e).__name__} {e}")
        return None


async def delete(job_id: str) -> bool:
    try:
        from sqlmodel import select
        from database import db
        from models import FontImportJob

        async with db.session_scope() as session:
            row = (await session.execute(
                select(FontImportJob).where(FontImportJob.job_id == job_id)
            )).scalars().first()
            if row is None:
                return False
            await session.delete(row)
        return True
    except Exception as e:
        logger.debug(f"[字体导入记录] 删除失败（忽略）: {type(e).__name__} {e}")
        return False
