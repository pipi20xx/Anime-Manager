"""字体导入记录的长期台账（PostgreSQL）。

职责边界：
- 工作目录 `data/fonts/import/<job_id>/` 只保留原始压缩包（incoming/），
  origin / 分析报告 / 入库结果全部落在这张表里，不再写 meta.json / report.json / commit.json；
- 这张表是「最近导入任务」与报告详情的唯一事实来源，从而支持分页查询、下载压缩包、
  以及按保留策略清理原始压缩包。

不抛异常：数据库不可用/表不存在时返回空结果，页面退回空列表。
"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _paths(cfg: Optional[Dict[str, Any]], job_id: str) -> Dict[str, Path]:
    from font_core import importer
    return importer.job_paths(cfg, job_id)


def _parse_dt(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _archive_info(cfg: Optional[Dict[str, Any]], job_id: str,
                  report: Optional[Dict[str, Any]]) -> tuple[List[str], List[str]]:
    """压缩包名 + 绝对路径（下载与清理要用）。

    分析失败时 report['archives'] 可能为空，退回 incoming/ 目录里的实际文件名。
    """
    paths = _paths(cfg, job_id)
    archives = (report or {}).get("archives") or []
    names = [str(a.get("name") or "") for a in archives if a.get("name")]
    if not names:
        incoming = paths["incoming"]
        try:
            names = [p.name for p in incoming.iterdir() if p.is_file()]
        except OSError:
            names = []
    return names, [str(paths["incoming"] / n) for n in names]


def _counts(report: Optional[Dict[str, Any]]) -> Dict[str, int]:
    counts = (report or {}).get("counts") or {}
    return {str(k): int(v or 0) for k, v in counts.items()}


async def create(cfg: Optional[Dict[str, Any]], job_id: str, origin: str = "web") -> bool:
    """建任务时先落一条「created」记录（origin / created_at 的持久化，替代 meta.json）。"""
    try:
        from sqlmodel import select
        from database import db
        from models import FontImportJob

        async with db.session_scope() as session:
            row = (await session.execute(
                select(FontImportJob).where(FontImportJob.job_id == job_id)
            )).scalars().first()
            if row is None:
                row = FontImportJob(job_id=job_id, origin=origin or "web",
                                    status="created", created_at=datetime.now(),
                                    updated_at=datetime.now())
                session.add(row)
            else:
                row.origin = row.origin or (origin or "web")
                row.updated_at = datetime.now()
        return True
    except Exception as e:
        logger.debug(f"[字体导入记录] 建记录失败（忽略）: {type(e).__name__} {e}")
        return False


async def save_report(cfg: Optional[Dict[str, Any]], job_id: str,
                      report: Dict[str, Any]) -> bool:
    """分析完成后把完整报告 upsert 进表（替代 report.json）。"""
    names, paths = _archive_info(cfg, job_id, report)
    created_dt = _parse_dt(report.get("created_at"))
    status = "analyzed" if report.get("success") else "failed"
    try:
        from sqlmodel import select
        from database import db
        from models import FontImportJob

        async with db.session_scope() as session:
            row = (await session.execute(
                select(FontImportJob).where(FontImportJob.job_id == job_id)
            )).scalars().first()
            if row is None:
                row = FontImportJob(job_id=job_id, origin="web",
                                    created_at=created_dt or datetime.now(),
                                    updated_at=datetime.now())
                session.add(row)
            row.status = status
            row.report = report
            row.archive_names = names
            row.archive_paths = paths
            row.counts = _counts(report)
            row.target = str(report.get("target") or "")
            row.message = str(report.get("message") or "")
            row.updated_at = datetime.now()
        return True
    except Exception as e:
        logger.debug(f"[字体导入记录] 写报告失败（忽略）: {type(e).__name__} {e}")
        return False


async def save_commit(cfg: Optional[Dict[str, Any]], job_id: str,
                      result: Dict[str, Any], report: Dict[str, Any]) -> bool:
    """入库完成后把入库结果 + 更新过的报告 upsert 进表（替代 commit.json）。"""
    names, paths = _archive_info(cfg, job_id, report)
    # report 已单独存 report 列，这里去掉避免在 commit 列里重复存一份
    commit_payload = {k: v for k, v in result.items() if k != "report"}
    try:
        from sqlmodel import select
        from database import db
        from models import FontImportJob

        async with db.session_scope() as session:
            row = (await session.execute(
                select(FontImportJob).where(FontImportJob.job_id == job_id)
            )).scalars().first()
            if row is None:
                row = FontImportJob(job_id=job_id, origin="web",
                                    created_at=datetime.now(), updated_at=datetime.now())
                session.add(row)
            row.status = "committed"
            row.report = report
            row.commit_result = commit_payload
            row.archive_names = names
            row.archive_paths = paths
            row.counts = _counts(report)
            row.committed_count = int(result.get("count") or 0)
            row.target = str(result.get("target") or "")
            row.message = str(result.get("message") or "")
            row.updated_at = datetime.now()
        return True
    except Exception as e:
        logger.debug(f"[字体导入记录] 写入库结果失败（忽略）: {type(e).__name__} {e}")
        return False


async def get_report(job_id: str) -> Optional[Dict[str, Any]]:
    """读取完整分析报告（新记录都存这里；老记录没有报告则返回 None）。"""
    try:
        from sqlmodel import select
        from database import db
        from models import FontImportJob

        async with db.session_scope() as session:
            row = (await session.execute(
                select(FontImportJob).where(FontImportJob.job_id == job_id)
            )).scalars().first()
        return dict(row.report) if row and row.report else None
    except Exception as e:
        logger.debug(f"[字体导入记录] 读报告失败（忽略）: {type(e).__name__} {e}")
        return None


def _to_summary(row: Any) -> Dict[str, Any]:
    return {
        "job_id": row.job_id,
        "created_at": row.created_at.isoformat(timespec="seconds") if row.created_at else "",
        "origin": row.origin or "web",
        "status": row.status or "",
        "archives": list(row.archive_names or []),
        "counts": dict(row.counts or {}),
        # 新记录以 report 为准；老记录（无 report 列数据）按状态兜底，别把历史任务判成「未分析」
        "analyzed": bool(row.report) or row.status in ("analyzed", "committed"),
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
    调用方只有拿到 None 才考虑退回磁盘扫描。
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
