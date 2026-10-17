"""字体管家 API —— assfonts 的网页封装（全模式版）。

覆盖 assfonts 全部命令行能力：
    处理模式  default / subset_only(-s) / embed_only(-e) / clean_embedded(-e -s)
              / combined_subset(-c 两阶段合并)
    处理方式  -f 额外字体目录（可多个） / -o 输出目录 / -r 重命名字体
              / -l HDR 亮度 / -m 内部线程 / -v 日志级别
    字体库    可配置多个目录（多次 -f 叠加）

端点总览：
    GET    /status              内核/索引/字体库/任务/模式与选项 总状态
    GET    /config              读取配置
    PUT    /config              保存配置
    POST   /index/rebuild       重建字体索引
    GET    /fonts                读取索引中的字体列表
    POST   /jobs/upload         上传字幕（可多选）
    GET    /jobs                任务列表
    POST   /jobs/{id}/run       执行单个任务（可临时覆盖模式）
    POST   /jobs/run-all        批量执行（合并模式走两阶段）
    DELETE /jobs/{id}           删除任务
    POST   /jobs/clear          清理任务
    GET    /jobs/{id}/download  下载成品（.ass 或字体包 zip，按模式自动）
    GET    /jobs/download-all   打包下载全部成品
    GET    /update/check        检查 assfonts 上游更新
    POST   /update/apply        应用更新
"""
from __future__ import annotations

import asyncio
import hashlib
import io
import time
import logging
import os
import re
import shutil
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from urllib.parse import quote
from pydantic import BaseModel, Field
from sqlmodel import desc, select

from config_manager import ConfigManager
from database import db
from event_broadcaster import EventBroadcaster
from font_core import ass_parser, index_store, runner
from font_core import binary as af_binary
from logger import log_audit
from models import FontSubtitleJob

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/font_manager", tags=["字体管家"])

DEFAULT_WORKSPACE = "data/fonts/jobs"
MAX_UPLOAD_BYTES = 64 * 1024 * 1024
_UNSAFE_RE = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
_RUN_LOCK = asyncio.Lock()


# ── 配置 / 选项 ──────────────────────────────────────────────

def _cfg() -> Dict[str, Any]:
    return ConfigManager.get_config() or {}


def _fm(cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return (cfg or _cfg()).get("font_manager", {}) or {}


def _workspace(cfg: Optional[Dict[str, Any]] = None) -> Path:
    return Path(str(_fm(cfg).get("workspace_dir") or DEFAULT_WORKSPACE))


def _library_dirs(cfg: Optional[Dict[str, Any]] = None) -> List[str]:
    fm = _fm(cfg)
    dirs: List[str] = []
    main = str(fm.get("library_dir") or "").strip()
    if main:
        dirs.append(main)
    extra = fm.get("extra_library_dirs") or []
    if isinstance(extra, str):
        extra = [x.strip() for x in extra.split(",")]
    for d in extra:
        d = str(d or "").strip()
        if d and d not in dirs:
            dirs.append(d)
    return dirs


def _options(cfg: Optional[Dict[str, Any]] = None, *,
             mode_override: Optional[str] = None,
             overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """合并配置与临时覆盖，得到本次处理的完整参数。"""
    fm = _fm(cfg)
    ov = overrides or {}

    def _pick(key: str, default: Any) -> Any:
        if key in ov and ov[key] is not None:
            return ov[key]
        v = fm.get(key)
        return default if v is None else v

    mode = runner.normalize_mode(mode_override or str(_pick("mode", runner.MODE_DEFAULT)))
    extra_font = str(_pick("extra_font_dir", "") or "").strip()
    output_dir = str(_pick("output_dir", "") or "").strip()
    verbose = int(_pick("verbose_level", 3) or 0)
    return {
        "mode": mode,
        "mode_label": runner.MODE_LABELS.get(mode, mode),
        "output_kind": runner.MODE_OUTPUT_KIND.get(mode, "ass"),
        "extra_font_dirs": _extra_font_dirs_for_run(cfg, extra_font),
        "extra_font_dir": extra_font,
        "output_dir": output_dir or None,
        "rename": bool(_pick("rename_fonts", False)),
        "hdr_luminance": int(_pick("hdr_luminance", 0) or 0),
        "threads": int(_pick("internal_threads", 0) or 0),
        "verbose": max(0, min(3, verbose)),
        "keep_subset_dir": bool(_pick("keep_subset_dir", True)),
        "delete_source": bool(_pick("delete_source", False)),
    }


class FontManagerConfig(BaseModel):
    # 字体来源
    library_dir: Optional[str] = Field(None, description="字体库目录（用户自选）")
    extra_library_dirs: Optional[List[str]] = Field(None, description="额外字体库目录（可多个）")
    index_dir: Optional[str] = None
    workspace_dir: Optional[str] = None
    # 处理模式与方式
    mode: Optional[str] = Field(None, description="处理模式")
    extra_font_dir: Optional[str] = Field(None, description="本次处理的额外字体目录（-f）")
    output_dir: Optional[str] = Field(None, description="输出目录（-o），留空=任务目录")
    rename_fonts: Optional[bool] = Field(None, description="重命名子集化字体（-r）")
    hdr_luminance: Optional[int] = Field(None, ge=0, le=1000, description="HDR 亮度（-l，0=不处理）")
    internal_threads: Optional[int] = Field(None, ge=0, le=128, description="内核内部线程数（-m，0=默认）")
    verbose_level: Optional[int] = Field(None, ge=0, le=3, description="内核日志级别（-v，0-3）")
    keep_subset_dir: Optional[bool] = Field(None, description="保留 _subsetted 子集字体文件夹")
    delete_source: Optional[bool] = Field(None, description="成功后删除上传的源字幕副本")
    # 内核
    binary_path: Optional[str] = Field(None, description="自定义 assfonts 路径")
    proxy_for_update: Optional[bool] = Field(None, description="更新时走系统代理")


@router.get("/config", summary="读取字体管家配置")
async def get_font_manager_config():
    return {"status": "success", "data": _fm()}


@router.put("/config", summary="保存字体管家配置")
async def update_font_manager_config(payload: FontManagerConfig):
    patch = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    if "mode" in patch:
        patch["mode"] = runner.normalize_mode(str(patch["mode"]))
    if "library_dir" in patch:
        patch["library_dir"] = str(patch["library_dir"]).strip()
        # 字体库变化 → 旧索引立即失效，避免用错口径检查/子集化
        old_main = str(_fm().get("library_dir") or "").strip()
        if old_main and old_main != patch["library_dir"]:
            _drop_index()
    if "extra_library_dirs" in patch:
        dirs = [str(d).strip() for d in (patch["extra_library_dirs"] or []) if str(d or "").strip()]
        patch["extra_library_dirs"] = dirs
        if dirs != [str(d) for d in (_fm().get("extra_library_dirs") or [])]:
            _drop_index()
    ConfigManager.update_config({"font_manager": patch})
    log_audit("字体管家", "配置更新", f"配置已更新：{', '.join(patch.keys())}")
    return {"status": "success", "data": _fm()}


def _drop_index() -> None:
    try:
        f = index_store.index_file()
        if f.is_file():
            f.unlink()
    except Exception:
        pass


# ── 通用工具 ─────────────────────────────────────────────────

def _sanitize_filename(name: str) -> str:
    base = (name or "").replace("\\", "/").split("/")[-1]
    base = _UNSAFE_RE.sub("_", base).strip().strip(".")
    return base or "subtitle.ass"


def _assert_within(path: Path, roots: Sequence[Path]) -> Path:
    """校验 path 位于任一根目录之内（防目录穿越），返回 resolve 结果。"""
    try:
        rp = path.resolve()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"路径解析失败：{e}")
    for root in roots:
        try:
            rr = root.resolve()
        except Exception:
            continue
        if rp == rr or rr in rp.parents:
            return rp
    raise HTTPException(status_code=403, detail="非法路径")


def _job_to_dict(job: FontSubtitleJob) -> Dict[str, Any]:
    mode = job.mode or runner.MODE_DEFAULT
    return {
        "job_id": job.job_id,
        "filename": job.filename,
        "status": job.status,
        "mode": mode,
        "mode_label": runner.MODE_LABELS.get(mode, mode),
        "output_kind": job.output_kind or runner.MODE_OUTPUT_KIND.get(mode, "ass"),
        "referenced_fonts": list(job.referenced_fonts or []),
        "missing_fonts": list(job.missing_fonts or []),
        "has_embedded": bool(job.has_embedded),
        "output_name": job.output_name or "",
        "output_size": int(job.output_size or 0),
        "has_subset_dir": bool(job.subset_dir),
        "cleaned_name": (Path(job.cleaned_path).name if job.cleaned_path else ""),
        "duration_ms": int(job.duration_ms or 0),
        "error": job.error or "",
        "created_at": job.created_at.isoformat(timespec="seconds") if job.created_at else "",
        "updated_at": job.updated_at.isoformat(timespec="seconds") if job.updated_at else "",
    }


async def _broadcast(event: str, payload: Any) -> None:
    try:
        await EventBroadcaster.broadcast(event, payload)
    except Exception:
        pass


def _require_binary(cfg: Dict[str, Any]) -> Path:
    path, source = af_binary.resolve_binary(cfg)
    if not path:
        raise HTTPException(status_code=400, detail="未找到可执行的 assfonts 二进制，请在设置中检查或尝试一键更新")
    if not os.access(str(path), os.X_OK):
        try:
            os.chmod(str(path), 0o755)
        except Exception:
            pass
    return path


async def _resolve_index(binary: Path, cfg: Dict[str, Any]) -> Tuple[Path, Dict[str, Any], Set[str]]:
    """确保索引可用，返回 (索引目录, 索引信息, 索引字体名集合)。"""
    libs = _library_dirs(cfg)
    if not libs:
        raise HTTPException(status_code=400, detail="请先选择字体库文件夹")
    bad = [d for d in libs if not Path(d).is_dir()]
    if bad:
        raise HTTPException(status_code=400, detail=f"字体库目录不可用：{bad[0]}")
    info = await index_store.ensure_index(binary, cfg, libs)
    if not info.get("exists") or not info.get("count"):
        raise HTTPException(status_code=400, detail=info.get("error") or "字体索引不可用，请重建索引")
    db_dir = Path(info.get("path", "")).parent
    known = _merged_known_fonts(info.get("fonts", []), cfg)
    return db_dir, info, known


# ── 字体上传：临时字体池 ─────────────────────────────────────

def _temp_font_dir(cfg: Optional[Dict[str, Any]] = None) -> Path:
    """临时字体池目录（仅作为处理时的 -f 补充字体源，不进字体库）。"""
    return Path(str(_fm(cfg).get("temp_font_dir") or "data/fonts/temp_fonts"))


def _temp_index_dir(cfg: Optional[Dict[str, Any]] = None) -> Path:
    """临时字体池的独立索引目录（用于缺字体判定，避免和主库索引混淆）。"""
    return _temp_font_dir(cfg).parent / "temp_index"


def _list_temp_fonts(cfg: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    d = _temp_font_dir(cfg)
    out: List[Dict[str, Any]] = []
    try:
        for e in os.scandir(d):
            if e.is_file() and ass_parser.is_font_file(e.name):
                try:
                    st = e.stat()
                except OSError:
                    continue
                out.append({"filename": e.name, "size": st.st_size,
                            "mtime": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds")})
    except OSError:
        pass
    out.sort(key=lambda x: x["filename"].lower())
    return out


def _extra_font_dirs_for_run(cfg: Dict[str, Any], extra_font: str = "") -> List[str]:
    """实际下发的 -f 目录：配置的额外字体目录 + 临时字体池（池里有字体时才带）。

    实测：`-f` 与 `-d` 索引是叠加关系 —— 字体只在临时池、不在索引里也能被找到并内嵌。
    """
    dirs = [extra_font] if extra_font else []
    if _list_temp_fonts(cfg):
        pool = str(_temp_font_dir(cfg))
        if pool not in dirs:
            dirs.append(pool)
    return dirs


def _merged_known_fonts(main_faces: Any, cfg: Dict[str, Any]) -> Set[str]:
    """主库索引 + 临时字体索引 的字体名合集（缺字体判定要算上临时字体）。"""
    names = index_store.font_name_set(main_faces or [])
    try:
        tinfo = index_store.read_index(_temp_index_dir(cfg))
        names |= index_store.font_name_set(tinfo.get("fonts") or [])
    except Exception:
        pass
    return names


async def _recheck_missing_after_temp_change(cfg: Dict[str, Any]) -> int:
    """临时字体池变化后，重算 pending / missing 任务的缺失字体。

    任务记录里的 missing_fonts 是预检快照：先传字幕、后补临时字体时，
    旧记录仍显示缺字体。这里用「主库索引 + 临时字体索引」重新比对，
    临时字体已覆盖的字体从缺失清单里去掉（status 同步在 missing→pending 间流转）。
    返回更新的任务数。
    """
    try:
        idx_now = await asyncio.to_thread(index_store.read_index, None, cfg)
        if not idx_now.get("exists"):
            return 0
        known_now = _merged_known_fonts(idx_now.get("fonts", []), cfg)
        if not known_now:
            return 0
        updated = 0
        async with db.session_scope() as session:
            rows = (await session.execute(
                select(FontSubtitleJob).where(
                    FontSubtitleJob.status.in_(["pending", "missing"])
                )
            )).scalars().all()
            for job in rows:
                refs = list(job.referenced_fonts or [])
                if not refs:
                    continue
                miss = runner.missing_by_index(refs, known_now)
                new_missing = list(miss)
                if set(new_missing) == set(job.missing_fonts or []):
                    continue
                job.missing_fonts = new_missing
                # 之前因缺字体被标 missing 的任务，字体补齐后回到 pending 可重试
                if job.status == "missing" and not new_missing:
                    job.status = "pending"
                    job.error = ""
                elif job.status == "pending" and new_missing:
                    job.status = "missing"
                    job.error = "缺失字体：" + "、".join(new_missing)
                job.updated_at = datetime.now()
                session.add(job)
                updated += 1
            await session.commit()
        if updated:
            logger.info(f"[字体管家] 临时字体变化，已重算 {updated} 个任务的缺失字体")
        return updated
    except Exception as e:
        logger.debug(f"[字体管家] 临时字体变化重算缺失字体失败（忽略）: {e}")
        return 0


async def _refresh_temp_index(binary: Path, cfg: Dict[str, Any]) -> Dict[str, Any]:
    """临时字体池变化后重建其索引；池子为空时清掉索引目录。"""
    idx_dir = _temp_index_dir(cfg)
    files = _list_temp_fonts(cfg)
    if not files:
        shutil.rmtree(idx_dir, ignore_errors=True)
        return {"exists": False, "count": 0, "file_count": 0}
    opts = _options(cfg)
    r = await index_store.build_index(binary, [str(_temp_font_dir(cfg))], idx_dir,
                                      threads=opts["threads"], verbose=opts["verbose"])
    if not r.get("success"):
        return {"exists": False, "count": 0, "file_count": 0, "error": r.get("message", "")}
    info = await asyncio.to_thread(index_store.read_index, idx_dir)
    return {"exists": info.get("exists", False), "count": info.get("count", 0),
            "file_count": info.get("file_count", 0)}


def _save_font_blob(target_dir: Path, filename: str, blob: bytes) -> Tuple[str, str, str]:
    """把字体字节落盘（同名同内容跳过、同名不同内容加序号）。

    :return: (动作 added/renamed/duplicate/failed, 落盘文件名, 说明)
    """
    sha = hashlib.sha256(blob).hexdigest()
    stem, ext = os.path.splitext(filename)
    candidate = target_dir / filename
    if candidate.exists():
        try:
            if hashlib.sha256(candidate.read_bytes()).hexdigest() == sha:
                return "duplicate", filename, "字体库/临时池中已存在完全相同的文件"
        except OSError:
            pass
        for i in range(1, 1000):
            alt = target_dir / f"{stem}_{i}{ext}"
            if not alt.exists():
                candidate = alt
                return ("renamed", candidate.name, f"同名文件已存在且内容不同，另存为 {candidate.name}") \
                    if _write(candidate, blob) else ("failed", filename, "写入失败")
        return "failed", filename, "同名冲突过多，未能保存"
    ok = _write(candidate, blob)
    return ("added", candidate.name, "") if ok else ("failed", filename, "写入失败")


def _write(path: Path, blob: bytes) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(blob)
        return True
    except Exception as e:
        logger.warning(f"[字体管家] 字体写入失败 {path}: {e}")
        return False


def _download_roots(cfg: Dict[str, Any]) -> List[Path]:
    roots = [_workspace(cfg)]
    od = str(_fm(cfg).get("output_dir") or "").strip()
    if od:
        roots.append(Path(od))
    return roots


# ── 状态 ─────────────────────────────────────────────────────

@router.get("/status", summary="字体管家总状态")
async def get_status():
    cfg = _cfg()
    binfo = await asyncio.to_thread(af_binary.binary_info, cfg)
    idx = await asyncio.to_thread(index_store.read_index, None, cfg)
    libs = _library_dirs(cfg)
    lib_stats = index_store.library_stats(idx.get("fonts", []) or [], libs)

    library_state = {
        "path": libs[0] if libs else "",
        "paths": libs,
        "exists": bool(libs) and all(Path(d).is_dir() for d in libs),
        "writable": bool(libs) and all(Path(d).is_dir() and os.access(d, os.W_OK) for d in libs),
        "message": "" if libs else "尚未选择字体库文件夹",
    }
    if libs and not library_state["exists"]:
        library_state["message"] = "存在不可访问的字体库目录"

    temp_files = _list_temp_fonts(cfg)
    temp_idx = await asyncio.to_thread(index_store.read_index, _temp_index_dir(cfg))
    opts = _options(cfg)
    od = opts.get("output_dir")
    if od and not Path(od).is_dir():
        library_state.setdefault("warnings", []).append(f"输出目录不存在，将在首次处理时自动创建：{od}")
    if opts["verbose"] < 2:
        library_state.setdefault("warnings", []).append(
            "内核日志级别低于 2 时 assfonts 不会输出缺字体提示，系统将改用索引比对来判定缺失字体。")

    counts = {"total": 0, "pending": 0, "running": 0, "success": 0, "missing": 0, "failed": 0, "skipped": 0}
    try:
        async with db.session_scope() as session:
            rows = (await session.execute(select(FontSubtitleJob))).scalars().all()
        counts["total"] = len(rows)
        for r in rows:
            key = r.status if r.status in counts else "failed"
            counts[key] = counts.get(key, 0) + 1
    except Exception as e:
        logger.warning(f"[字体管家] 统计任务数失败: {e}")

    return {
        "status": "success",
        "binary": binfo,
        "index": {
            "exists": idx.get("exists", False),
            "count": idx.get("count", 0),
            "file_count": idx.get("file_count", 0),
            "library_count": lib_stats.get("library_count", 0),
            "library_file_count": lib_stats.get("library_file_count", 0),
            "built_at": idx.get("built_at", ""),
            "path": idx.get("path", ""),
            "error": idx.get("error", ""),
        },
        "library": library_state,
        "temp_fonts": {
            "dir": str(_temp_font_dir(cfg)),
            "count": len(temp_files),
            "files": temp_files,
            "index": temp_idx,
            "active": bool(temp_files),
        },
        "jobs": counts,
        "options": opts,
        "modes": [
            {"value": m, "label": runner.MODE_LABELS[m],
             "description": runner.MODE_DESCRIPTIONS.get(m, ""),
             "output_kind": runner.MODE_OUTPUT_KIND.get(m, "ass")}
            for m in runner.ALL_MODES
        ],
        "config": _fm(cfg),
    }


@router.get("/binary/help", summary="内核参数帮助（assfonts -h 原始输出）")
async def binary_help():
    """直接问内核要 `-h` 输出，而不是把帮助文本写死在代码里。

    好处：网页更新内核后，页面上的参数说明会自动跟着新版内核变；
    也能让用户对照内核真实支持的参数，确认网页版没有漏掉能力。
    """
    cfg = _cfg()
    binary = _require_binary(cfg)
    info = await asyncio.to_thread(af_binary.binary_info, cfg)
    try:
        proc = await asyncio.create_subprocess_exec(
            str(binary), "-h",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        raw, _ = await asyncio.wait_for(proc.communicate(), timeout=20)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"无法获取内核帮助：{type(e).__name__} {e}")
    return {
        "status": "success",
        "version": info.get("version", ""),
        "source": info.get("source", ""),
        "source_label": info.get("source_label", ""),
        "path": info.get("path", ""),
        "help": (raw or b"").decode("utf-8", errors="replace").strip(),
    }


# ── 索引与字体库 ─────────────────────────────────────────────

@router.post("/index/rebuild", summary="重建字体索引")
async def rebuild_index():
    cfg = _cfg()
    binary = _require_binary(cfg)
    libs = _library_dirs(cfg)
    if not libs:
        raise HTTPException(status_code=400, detail="请先选择字体库文件夹")
    bad = [d for d in libs if not Path(d).is_dir()]
    if bad:
        raise HTTPException(status_code=400, detail=f"字体库目录不存在：{bad[0]}")
    await _broadcast("font_index", {"state": "running"})
    opts = _options(cfg)
    result = await index_store.build_index(
        binary, libs, index_store.index_dir(cfg),
        threads=opts["threads"], verbose=opts["verbose"])
    await _broadcast("font_index", {"state": "done" if result.get("success") else "failed",
                                    "message": result.get("message", "")})
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message") or "索引构建失败")
    log_audit("字体管家", "重建索引", result.get("message", ""))
    info = await asyncio.to_thread(index_store.read_index, None, cfg)
    stats = index_store.library_stats(info.get("fonts", []) or [], libs)
    return {"status": "success", "message": result.get("message", ""), "log": result.get("log", ""),
            "index": {"exists": info.get("exists"), "count": info.get("count"),
                      "file_count": info.get("file_count"),
                      "library_count": stats.get("library_count", 0),
                      "library_file_count": stats.get("library_file_count", 0),
                      "built_at": info.get("built_at")}}


@router.get("/fonts", summary="索引中的字体列表")
async def list_fonts(
    q: Optional[str] = Query(None),
    fmt: Optional[str] = Query(None),
    scope: str = Query("library", description="library=仅字体库目录内 / all=含系统字体"),
    limit: int = Query(200, ge=1, le=2000),
    offset: int = Query(0, ge=0),
):
    cfg = _cfg()
    libs = _library_dirs(cfg)
    idx = await asyncio.to_thread(index_store.read_index, None, cfg)

    fonts: List[Dict[str, Any]] = []
    for face in idx.get("fonts", []) or []:
        item = dict(face)
        item["in_library"] = index_store.under_library(face.get("path", ""), libs)
        fonts.append(item)
    if scope != "all":
        fonts = [f for f in fonts if f["in_library"]]

    formats: Dict[str, int] = {}
    for f in fonts:
        key = f.get("format") or "unknown"
        formats[key] = formats.get(key, 0) + 1

    if q:
        needle = q.strip().lower()
        fonts = [f for f in fonts
                 if needle in " ".join(f.get("families", []) + f.get("fullnames", []) + [f.get("filename", "")]).lower()]
    if fmt:
        want = fmt.strip().lstrip(".").lower()
        fonts = [f for f in fonts if f.get("format") == want]

    total = len(fonts)
    page = fonts[offset:offset + limit]
    stats = index_store.library_stats(idx.get("fonts", []) or [], libs)
    return {
        "status": "success",
        "index": {"exists": idx.get("exists", False), "count": idx.get("count", 0),
                  "file_count": idx.get("file_count", 0),
                  "library_count": stats.get("library_count", 0),
                  "library_file_count": stats.get("library_file_count", 0),
                  "built_at": idx.get("built_at", ""), "error": idx.get("error", "")},
        "scope": scope,
        "formats": formats,
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": page,
    }


@router.get("/fonts/download", summary="下载单个字体文件")
async def download_font(
    filename: str = Query(..., description="索引中的字体文件名"),
):
    """按索引里的字体文件名下载字体库中的单个字体文件。"""
    cfg = _cfg()
    libs = [Path(d) for d in _library_dirs(cfg)]
    if not libs:
        raise HTTPException(status_code=400, detail="未配置字体库目录")

    name = _sanitize_filename(filename)
    idx = await asyncio.to_thread(index_store.read_index, None, cfg)
    target: Optional[Path] = None
    for face in idx.get("fonts", []) or []:
        if face.get("filename") == name and face.get("path"):
            try:
                target = _assert_within(Path(face["path"]), libs)
            except HTTPException:
                continue
            break
    if target is None or not target.is_file():
        raise HTTPException(status_code=404, detail=f"字体文件不存在或不在字体库目录内：{name}")

    media = "font/ttf" if target.suffix.lower() == ".ttf" else "font/otf" if target.suffix.lower() == ".otf" else "application/octet-stream"
    ascii_name = name.encode("ascii", "ignore").decode() or "font" + target.suffix
    quoted = quote(name)
    return Response(
        content=target.read_bytes(),
        media_type=media,
        headers={"Content-Disposition": f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quoted}"},
    )


@router.get("/fonts/download-all", summary="打包下载字体库（支持筛选）")
async def download_fonts_all(
    q: Optional[str] = Query(None),
    fmt: Optional[str] = Query(None),
):
    """按 /fonts 相同的筛选条件打包下载字体库中的字体文件（zip）。"""
    cfg = _cfg()
    libs = [Path(d) for d in _library_dirs(cfg)]
    if not libs:
        raise HTTPException(status_code=400, detail="未配置字体库目录")

    idx = await asyncio.to_thread(index_store.read_index, None, cfg)
    fonts = [f for f in idx.get("fonts", []) or []
             if index_store.under_library(f.get("path", ""), libs)]

    if q:
        needle = q.strip().lower()
        fonts = [f for f in fonts
                 if needle in " ".join(f.get("families", []) + f.get("fullnames", []) + [f.get("filename", "")]).lower()]
    if fmt:
        want = fmt.strip().lstrip(".").lower()
        fonts = [f for f in fonts if f.get("format") == want]

    items: List[Tuple[str, Path, str]] = []
    for f in fonts:
        p_str = f.get("path") or ""
        if not p_str:
            continue
        try:
            p = _assert_within(Path(p_str), libs)
        except HTTPException:
            continue
        if p.is_file():
            items.append((f.get("filename") or p.name, p, "file"))
    if not items:
        raise HTTPException(status_code=400, detail="没有可下载的字体文件（检查筛选条件）")

    blob = await asyncio.to_thread(_zip_payloads, items)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Response(content=blob, media_type="application/zip",
                    headers={"Content-Disposition": f"attachment; filename=\"font_library_{stamp}.zip\""})


# ── 字体上传（永久入库 / 临时使用）────────────────────────────

MAX_FONT_BYTES = 256 * 1024 * 1024
_FONT_UPLOAD_HINT = "仅支持字体文件（.ttf/.otf/.ttc/.otc/.woff/.woff2）"


@router.post("/fonts/upload", summary="上传字体到字体库（永久）")
async def upload_fonts(files: List[UploadFile] = File(...)):
    """把字体文件存进字体库目录，并按配置自动重建索引。

    - 同名同内容：跳过（记为 duplicate），不重复占用空间
    - 同名不同内容：另存为 name_1.ext，绝不覆盖既有字体
    """
    cfg = _cfg()
    libs = _library_dirs(cfg)
    if not libs:
        raise HTTPException(status_code=400, detail="请先选择字体库文件夹")
    target = Path(libs[0])
    if not target.is_dir():
        raise HTTPException(status_code=400, detail=f"字体库目录不可用：{target}")

    saved: List[Dict[str, Any]] = []
    skipped: List[Dict[str, str]] = []
    for up in files:
        name = _sanitize_filename(up.filename or "")
        if not ass_parser.is_font_file(name):
            skipped.append({"filename": name or (up.filename or ""), "reason": _FONT_UPLOAD_HINT})
            continue
        try:
            blob = await up.read()
        except Exception as e:
            skipped.append({"filename": name, "reason": f"读取失败：{e}"})
            continue
        if not blob:
            skipped.append({"filename": name, "reason": "文件为空"})
            continue
        if len(blob) > MAX_FONT_BYTES:
            skipped.append({"filename": name, "reason": f"文件过大（>{MAX_FONT_BYTES // 1024 // 1024}MB）"})
            continue
        action, stored, note = _save_font_blob(target, name, blob)
        if action == "failed":
            skipped.append({"filename": name, "reason": note or "写入失败"})
            continue
        saved.append({"filename": name, "stored_name": stored, "action": action,
                      "note": note, "size": len(blob), "path": str(target / stored)})

    added = [x for x in saved if x["action"] in ("added", "renamed")]
    index_result: Dict[str, Any] = {}
    if added and bool(_fm(cfg).get("auto_rebuild_after_upload", True)):
        binary = _require_binary(cfg)
        opts = _options(cfg)   # 只算一次（内部会扫临时字体池）
        await _broadcast("font_index", {"state": "running"})
        index_result = await index_store.build_index(
            binary, libs, index_store.index_dir(cfg),
            threads=opts["threads"], verbose=opts["verbose"])
        await _broadcast("font_index", {"state": "done" if index_result.get("success") else "failed",
                                       "message": index_result.get("message", "")})

    if not saved and skipped:
        raise HTTPException(status_code=400, detail=skipped[0].get("reason") or "上传失败")
    if added:
        log_audit("字体管家", "上传字体",
                  f"入库 {len(added)} 个字体"
                  + (f"，索引：{index_result.get('message', '')}" if index_result else "（未自动重建索引）"))
    return {"status": "success", "data": saved, "skipped": skipped,
            "added": len(added), "index": index_result}


@router.post("/fonts/temp/upload", summary="上传临时字体（仅本次处理使用，不入库）")
async def upload_temp_fonts(files: List[UploadFile] = File(...)):
    """临时字体池：处理时通过内核 `-f` 作为补充字体源，**不写入字体库**。

    用途：某部字幕缺一两个字体，不想因此污染字体库，只想这次用它跑通。
    上传后立即重建临时索引，因此缺字体预检也会立刻把这些字体算作"已具备"。
    """
    cfg = _cfg()
    pool = _temp_font_dir(cfg)
    saved: List[Dict[str, Any]] = []
    skipped: List[Dict[str, str]] = []
    for up in files:
        name = _sanitize_filename(up.filename or "")
        if not ass_parser.is_font_file(name):
            skipped.append({"filename": name or (up.filename or ""), "reason": _FONT_UPLOAD_HINT})
            continue
        try:
            blob = await up.read()
        except Exception as e:
            skipped.append({"filename": name, "reason": f"读取失败：{e}"})
            continue
        if not blob:
            skipped.append({"filename": name, "reason": "文件为空"})
            continue
        if len(blob) > MAX_FONT_BYTES:
            skipped.append({"filename": name, "reason": f"文件过大（>{MAX_FONT_BYTES // 1024 // 1024}MB）"})
            continue
        action, stored, note = _save_font_blob(pool, name, blob)
        if action == "failed":
            skipped.append({"filename": name, "reason": note or "写入失败"})
            continue
        saved.append({"filename": name, "stored_name": stored, "action": action,
                      "note": note, "size": len(blob)})

    if not saved and skipped:
        raise HTTPException(status_code=400, detail=skipped[0].get("reason") or "上传失败")

    index_info: Dict[str, Any] = {}
    if saved:
        binary = _require_binary(cfg)
        index_info = await _refresh_temp_index(binary, cfg)
        await _recheck_missing_after_temp_change(cfg)
        log_audit("字体管家", "上传临时字体",
                  f"临时字体 {len(saved)} 个（当前池内 {len(_list_temp_fonts(cfg))} 个）")

    return {"status": "success", "data": saved, "skipped": skipped,
            "temp": {"dir": str(pool), "count": len(_list_temp_fonts(cfg)),
                     "files": _list_temp_fonts(cfg), "index": index_info, "active": True}}


@router.get("/fonts/temp", summary="临时字体列表")
async def list_temp_font_endpoint():
    cfg = _cfg()
    files = _list_temp_fonts(cfg)
    idx = await asyncio.to_thread(index_store.read_index, _temp_index_dir(cfg))
    return {"status": "success",
            "dir": str(_temp_font_dir(cfg)),
            "count": len(files),
            "active": bool(files),
            "files": files,
            "index": {"exists": idx.get("exists", False), "count": idx.get("count", 0)}}


@router.delete("/fonts/temp", summary="删除临时字体（单个或清空）")
async def delete_temp_fonts(
    filename: Optional[str] = Query(None, description="留空=全部清空"),
):
    cfg = _cfg()
    pool = _temp_font_dir(cfg)
    binary = _require_binary(cfg)
    removed: List[str] = []
    if filename:
        name = _sanitize_filename(filename)
        target = _assert_within(pool / name, [pool])
        if not target.is_file():
            raise HTTPException(status_code=404, detail="该临时字体不存在")
        try:
            target.unlink()
            removed.append(name)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"删除失败：{e}")
    else:
        try:
            for e in os.scandir(pool):
                if e.is_file():
                    os.unlink(e.path)
                    removed.append(e.name)
        except FileNotFoundError:
            pass
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"清空失败：{e}")
    index_info = await _refresh_temp_index(binary, cfg)
    await _recheck_missing_after_temp_change(cfg)
    return {"status": "success", "removed": removed, "count": len(_list_temp_fonts(cfg)),
            "index": index_info}


# ── 上传 ─────────────────────────────────────────────────────

@router.post("/jobs/upload", summary="上传字幕（支持多选）")
async def upload_subtitles(files: List[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="未选择文件")
    cfg = _cfg()
    ws = _workspace(cfg)
    created: List[Dict[str, Any]] = []
    skipped: List[Dict[str, str]] = []

    for up in files:
        raw_name = _sanitize_filename(up.filename or "")
        if not ass_parser.is_subtitle_file(raw_name):
            skipped.append({"filename": raw_name or (up.filename or ""), "reason": "仅支持 .ass / .ssa 字幕"})
            continue
        try:
            blob = await up.read()
        except Exception as e:
            skipped.append({"filename": raw_name, "reason": f"读取失败：{e}"})
            continue
        if not blob:
            skipped.append({"filename": raw_name, "reason": "文件为空"})
            continue
        if len(blob) > MAX_UPLOAD_BYTES:
            skipped.append({"filename": raw_name, "reason": f"文件过大（>{MAX_UPLOAD_BYTES // 1024 // 1024}MB）"})
            continue

        job_id = uuid.uuid4().hex[:12]
        job_dir = ws / job_id
        try:
            job_dir.mkdir(parents=True, exist_ok=True)
            (job_dir / raw_name).write_bytes(blob)
        except Exception as e:
            skipped.append({"filename": raw_name, "reason": f"写入失败：{e}"})
            continue

        summary = ass_parser.inspect_ass(blob)
        # 上传即预检：索引已建好时直接比对出缺失字体，用户不必等处理完才知道缺什么。
        # 注意只填 missing_fonts，status 仍为 pending（避免被 run-all 的 missing 目标误收）。
        pre_missing: List[str] = []
        try:
            idx_now = await asyncio.to_thread(index_store.read_index, None, cfg)
            if idx_now.get("exists"):
                known_now = _merged_known_fonts(idx_now.get("fonts", []), cfg)
                pre_missing = runner.missing_by_index(summary.get("fonts", []), known_now)
        except Exception as e:
            logger.debug(f"[字体管家] 上传预检缺失字体失败（忽略）: {e}")

        job = FontSubtitleJob(
            job_id=job_id,
            filename=raw_name,
            stored_path=str(job_dir / raw_name),
            status="pending",
            mode=runner.normalize_mode(str(_fm(cfg).get("mode") or "")),
            output_kind=runner.MODE_OUTPUT_KIND.get(runner.normalize_mode(str(_fm(cfg).get("mode") or "")), "ass"),
            referenced_fonts=summary.get("fonts", []),
            missing_fonts=pre_missing,
            has_embedded=bool(summary.get("has_embedded_fonts")),
        )
        try:
            async with db.session_scope() as session:
                session.add(job)
                await session.commit()
                await session.refresh(job)
        except Exception as e:
            shutil.rmtree(job_dir, ignore_errors=True)
            skipped.append({"filename": raw_name, "reason": f"入库失败：{e}"})
            continue
        created.append(_job_to_dict(job))

    if not created and skipped:
        raise HTTPException(status_code=400, detail=skipped[0].get("reason") or "上传失败")
    if created:
        log_audit("字体管家", "上传字幕", f"上传 {len(created)} 个字幕文件")
    return {"status": "success", "data": created, "skipped": skipped}


# ── 任务列表 ─────────────────────────────────────────────────

@router.get("/jobs", summary="任务列表")
async def list_jobs(
    status: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    async with db.session_scope() as session:
        rows = (await session.execute(
            select(FontSubtitleJob).order_by(desc(FontSubtitleJob.created_at))
        )).scalars().all()
    items = [_job_to_dict(r) for r in rows]
    if status:
        items = [i for i in items if i["status"] == status]
    if q:
        needle = q.strip().lower()
        items = [i for i in items if needle in i["filename"].lower()]
    total = len(items)
    return {"status": "success", "total": total, "limit": limit, "offset": offset,
            "data": items[offset:offset + limit]}


# ── 执行 ─────────────────────────────────────────────────────

async def _safe_output_dir(job_id: str, ass_path: Path, opts: Dict[str, Any]) -> Optional[str]:
    """输出目录冲突规避。

    `-o` 指向公共目录时，两个**同名**字幕（如不同文件夹下都叫 01.ass）会写同一个
    成品文件，后跑的覆盖先跑的 —— 用户下载时可能拿到别人的成品。
    检测到「同名产物已被别的任务占用」时，退化为 <output_dir>/<job_id>/ 隔离存放；
    无冲突时保持扁平输出（与桌面版行为一致）。
    """
    base = opts.get("output_dir")
    if not base:
        return None
    try:
        predicted = runner.predict_outputs(
            Path(ass_path), Path(base), mode=opts["mode"],
            rename=opts["rename"], hdr_luminance=opts["hdr_luminance"])["main"]
    except Exception:
        return base
    try:
        async with db.session_scope() as session:
            rows = (await session.execute(
                select(FontSubtitleJob).where(FontSubtitleJob.job_id != job_id)
            )).scalars().all()
        for r in rows:
            if r.output_path and Path(r.output_path) == predicted:
                logger.info(f"[字体管家] 输出目录存在同名产物冲突，任务 {job_id} 隔离到子目录")
                return str(Path(base) / job_id)
    except Exception as e:
        logger.debug(f"[字体管家] 冲突检测失败（按原目录处理）: {e}")
    return base


def _persist_result(job: FontSubtitleJob, res: Dict[str, Any], opts: Dict[str, Any]) -> None:
    job.status = res.get("status", "failed")
    job.mode = res.get("mode", opts["mode"])
    job.output_kind = res.get("output_kind", opts["output_kind"])
    job.missing_fonts = list(res.get("missing") or [])
    job.output_path = res.get("output") or ""
    job.output_name = res.get("output_name") or ""
    job.output_size = int(res.get("output_size") or 0)
    job.subset_dir = res.get("subset_dir") or ""
    job.cleaned_path = res.get("cleaned") or ""
    job.output_dir = opts.get("output_dir") or ""
    job.duration_ms = int(res.get("duration_ms") or 0)
    job.error = res.get("error") or ""
    job.log = res.get("log") or ""
    job.updated_at = datetime.now()


async def _load_job(session, job_id: str) -> FontSubtitleJob:
    job = (await session.execute(
        select(FontSubtitleJob).where(FontSubtitleJob.job_id == job_id)
    )).scalars().first()
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    return job


async def _run_one(job_id: str, *, mode_override: Optional[str] = None) -> Dict[str, Any]:
    """执行单个任务（全模式）。"""
    cfg = _cfg()
    binary = _require_binary(cfg)
    db_dir, _, known = await _resolve_index(binary, cfg)
    opts = _options(cfg, mode_override=mode_override)

    async with db.session_scope() as session:
        job = await _load_job(session, job_id)
        stored_path = job.stored_path
        referenced = list(job.referenced_fonts or [])

    # 冲突规避要在起跑前决定有效输出目录
    opts["output_dir"] = await _safe_output_dir(job_id, Path(stored_path), opts)

    async with db.session_scope() as session:
        job = await _load_job(session, job_id)
        job.status = "running"
        job.mode = opts["mode"]
        job.output_kind = opts["output_kind"]
        job.error = ""
        job.updated_at = datetime.now()
        session.add(job)
        await session.commit()
        await session.refresh(job)
        running = _job_to_dict(job)
    await _broadcast("font_job", running)

    ass_path = Path(stored_path)
    if opts["mode"] == runner.MODE_COMBINED_SUBSET:
        combined = await runner.run_combined(
            binary, [ass_path], db_dir,
            extra_font_dirs=opts["extra_font_dirs"], output_dir=opts["output_dir"],
            rename=opts["rename"], hdr_luminance=opts["hdr_luminance"],
            threads=opts["threads"], verbose=opts["verbose"],
            keep_subset_dir=opts["keep_subset_dir"],
        )
        results = combined.get("results") or []
        if results:
            res = results[0]
            res.setdefault("mode", opts["mode"])
            res["output_kind"] = "ass"
        else:
            res = {"status": combined.get("status", "failed"), "mode": opts["mode"],
                   "output_kind": "ass", "missing": combined.get("missing") or [],
                   "error": combined.get("error") or "合并处理失败",
                   "log": combined.get("log") or "", "duration_ms": combined.get("duration_ms") or 0}
    else:
        res = await runner.run_convert(
            binary, ass_path, db_dir,
            mode=opts["mode"], extra_font_dirs=opts["extra_font_dirs"],
            output_dir=opts["output_dir"], rename=opts["rename"],
            hdr_luminance=opts["hdr_luminance"], threads=opts["threads"],
            verbose=opts["verbose"], keep_subset_dir=opts["keep_subset_dir"],
            known_fonts=known, referenced_fonts=referenced,
        )

    async with db.session_scope() as session:
        job = await _load_job(session, job_id)
        _persist_result(job, res, opts)
        if opts["delete_source"] and job.status == "success":
            try:
                Path(stored_path).unlink(missing_ok=True)
                job.log = ((job.log or "") + "\n[字体管家] 已按设置删除上传的源字幕副本").strip()
            except Exception as e:
                logger.warning(f"[字体管家] 删除源字幕失败: {e}")
        session.add(job)
        await session.commit()
        await session.refresh(job)
        payload = _job_to_dict(job)
    await _broadcast("font_job", payload)
    return payload


@router.post("/jobs/{job_id}/run", summary="执行单个任务")
async def run_job(job_id: str, mode: Optional[str] = Query(None, description="临时覆盖处理模式")):
    async with _RUN_LOCK:
        payload = await _run_one(job_id, mode_override=mode)
    log_audit("字体管家", "处理字幕",
              f"{payload['filename']} [{payload['mode_label']}] → {payload['status']}"
              + (f"（{payload['error']}）" if payload.get("error") else ""),
              level="ERROR" if payload["status"] == "failed" else "INFO")
    return {"status": "success", "data": payload}


@router.post("/jobs/run-all", summary="批量执行待处理任务")
async def run_all_jobs(
    include_failed: bool = Query(True, description="是否一并重试失败/缺字体的任务"),
    mode: Optional[str] = Query(None, description="临时覆盖处理模式"),
):
    cfg = _cfg()
    opts = _options(cfg, mode_override=mode)
    targets = ["pending", "missing"] + (["failed"] if include_failed else [])
    async with db.session_scope() as session:
        rows = (await session.execute(
            select(FontSubtitleJob).order_by(FontSubtitleJob.created_at)
        )).scalars().all()
    job_ids = [r.job_id for r in rows if r.status in targets]
    if not job_ids:
        return {"status": "success", "message": "没有待处理的任务", "data": [],
                "summary": {"total": 0, "success": 0, "missing": 0, "failed": 0, "skipped": 0}}

    results: List[Dict[str, Any]] = []
    async with _RUN_LOCK:
        if opts["mode"] == runner.MODE_COMBINED_SUBSET and len(job_ids) > 0:
            results = await _run_all_combined(job_ids, cfg, opts)
        else:
            for jid in job_ids:
                try:
                    results.append(await _run_one(jid, mode_override=mode))
                except HTTPException as e:
                    results.append({"job_id": jid, "status": "failed", "error": str(e.detail)})
                except Exception as e:
                    logger.error(f"[字体管家] 批量执行 {jid} 异常: {e}")
                    results.append({"job_id": jid, "status": "failed", "error": str(e)})

    summary = {"total": len(results), "success": 0, "missing": 0, "failed": 0, "skipped": 0}
    for r in results:
        key = r.get("status")
        if key in summary:
            summary[key] += 1
        else:
            summary["failed"] += 1
    log_audit("字体管家", "批量处理",
              f"[{opts['mode_label']}] 共 {summary['total']} 个：成功 {summary['success']} / "
              f"缺字体 {summary['missing']} / 失败 {summary['failed']} / 跳过 {summary['skipped']}")
    return {"status": "success", "summary": summary, "mode": opts["mode"],
            "mode_label": opts["mode_label"], "data": results}


async def _run_all_combined(job_ids: List[str], cfg: Dict[str, Any],
                            opts: Dict[str, Any]) -> List[Dict[str, Any]]:
    """合并子集化：一次性对全部待处理字幕跑两阶段流程。

    注意：`-c` 是「一批文件一次调用」，只要其中一个文件缺字体，整个阶段一就失败、
    不产出任何 results。若直接把批次错误套给每个任务，字体齐全的字幕会被误标 missing。
    因此先用索引把「注定缺字体」的字幕预筛出来单独标记，其余才进入两阶段流程。
    """
    binary = _require_binary(cfg)
    db_dir, _, known = await _resolve_index(binary, cfg)

    entries: List[Tuple[str, Path, List[str]]] = []
    gone: List[str] = []
    async with db.session_scope() as session:
        for jid in job_ids:
            job = await _load_job(session, jid)
            # 必须 resolve：run_combined 内部会把输入解析为绝对路径并在 results 里回报，
            # 若这里用未解析的相对路径做 key，成品路径会匹配不上而丢失。
            p = Path(job.stored_path).resolve()
            if not p.is_file():
                gone.append(jid)
                continue
            entries.append((jid, p, list(job.referenced_fonts or [])))

    # 索引预筛：缺字体的单独判定，不拖累同批其它字幕
    pre_missing: Dict[str, List[str]] = {}
    to_process: List[Tuple[str, Path]] = []
    for jid, p, refs in entries:
        miss = runner.missing_by_index(refs, known) if known else []
        if miss:
            pre_missing[jid] = miss
        else:
            to_process.append((jid, p))

    paths = [p for _jid, p in to_process]
    id_by_path = {str(p): jid for jid, p in to_process}
    if paths:
        async with db.session_scope() as session:
            for jid in [jid for jid, _p in to_process]:
                job = await _load_job(session, jid)
                job.status = "running"
                job.mode = opts["mode"]
                job.output_kind = "ass"
                job.error = ""
                job.updated_at = datetime.now()
                session.add(job)
            await session.commit()

    combined: Dict[str, Any] = {}
    if paths:
        combined = await runner.run_combined(
            binary, paths, db_dir,
            extra_font_dirs=opts["extra_font_dirs"], output_dir=opts["output_dir"],
            rename=opts["rename"], hdr_luminance=opts["hdr_luminance"],
            threads=opts["threads"], verbose=opts["verbose"],
            keep_subset_dir=opts["keep_subset_dir"],
            known_fonts=known,
            referenced_map={str(p): refs for _jid, p, refs in entries},
        )

    by_path: Dict[str, Dict[str, Any]] = {}
    for r in combined.get("results") or []:
        by_path[str(r.get("path") or "")] = r

    out: List[Dict[str, Any]] = []
    async with db.session_scope() as session:
        for jid in gone:
            job = await _load_job(session, jid)
            job.status = "failed"
            job.mode = opts["mode"]
            job.error = "源字幕文件不存在"
            job.updated_at = datetime.now()
            session.add(job)

        for jid, misses in pre_missing.items():
            job = await _load_job(session, jid)
            job.status = "missing"
            job.mode = opts["mode"]
            job.output_kind = "ass"
            job.missing_fonts = list(misses)
            job.error = "缺失字体：" + "、".join(misses)
            job.updated_at = datetime.now()
            session.add(job)

        for jid, p in to_process:
            res = by_path.get(str(p)) or {
                "status": combined.get("status", "failed"),
                "missing": combined.get("missing") or [],
                "error": combined.get("error") or "合并阶段失败",
                "log": combined.get("log") or "",
                "duration_ms": combined.get("duration_ms") or 0,
            }
            res["mode"] = opts["mode"]
            res["output_kind"] = "ass"
            job = await _load_job(session, jid)
            _persist_result(job, res, opts)
            if res.get("status") == "success" and combined.get("combined_dir"):
                job.subset_dir = combined.get("combined_dir")
            session.add(job)

        await session.commit()
        for jid in [j for j, _p in to_process] + list(pre_missing.keys()) + gone:
            job = await _load_job(session, jid)
            out.append(_job_to_dict(job))

    for payload in out:
        await _broadcast("font_job", payload)
    return out


@router.delete("/jobs/{job_id}", summary="删除任务")
async def delete_job(job_id: str, remove_files: bool = Query(True, description="是否同时删除工作目录")):
    async with db.session_scope() as session:
        job = await _load_job(session, job_id)
        stored = job.stored_path
        await session.delete(job)
        await session.commit()
    if remove_files and stored:
        try:
            _assert_within(Path(stored).parent, [_workspace()])
            shutil.rmtree(Path(stored).parent, ignore_errors=True)
        except HTTPException:
            pass
        except Exception as e:
            logger.warning(f"[字体管家] 删除工作目录失败: {e}")
    return {"status": "success"}


@router.post("/jobs/clear", summary="清理任务")
async def clear_jobs(
    keep_failed: bool = Query(True, description="是否保留失败/缺字体任务"),
    include_pending: bool = Query(False, description="是否一并清理尚未处理的待处理任务"),
):
    """清理任务。

    默认只清「已完成」（success / skipped）—— 失败、缺字体、待处理都属于"还没了结"，
    保留下来便于补齐字体后重试。想一次清干净就带上 include_pending=true。
    running 状态的任务永不清理，避免把正在跑的记录删掉。
    """
    drop = ["success", "skipped"]
    if not keep_failed:
        drop += ["failed", "missing"]
    if include_pending:
        drop += ["pending"]
    async with db.session_scope() as session:
        rows = (await session.execute(select(FontSubtitleJob))).scalars().all()
        removed = 0
        for r in rows:
            if r.status in drop:
                try:
                    _assert_within(Path(r.stored_path).parent, [_workspace()])
                    shutil.rmtree(Path(r.stored_path).parent, ignore_errors=True)
                except Exception:
                    pass
                await session.delete(r)
                removed += 1
        await session.commit()
    return {"status": "success", "removed": removed}


# ── 下载 ─────────────────────────────────────────────────────

def _zip_payloads(items: List[Tuple[str, Path, str]]) -> bytes:
    """把若干 (归档内名字, 路径, 类型) 打包为 zip；类型 ass=单文件 / zip=目录 / file=单文件。"""
    buf = io.BytesIO()
    used: Dict[str, int] = {}

    def _safe_mtime(p: Path) -> Tuple[int, int, int, int, int, int]:
        """ZIP 要求 mtime >= 1980；NAS 挂载的文件可能时间戳异常，越界时钳制到 1980-01-01。"""
        try:
            st = p.stat()
            t = time.localtime(st.st_mtime)
            y, mo, d, h, mi, sec = t.tm_year, t.tm_mon, t.tm_mday, t.tm_hour, t.tm_min, min(t.tm_sec, 59)
            if y < 1980:
                return (1980, 1, 1, 0, 0, 0)
            return (y, mo, d, h, mi, sec)
        except Exception:
            return (1980, 1, 1, 0, 0, 0)

    def _unique(name: str) -> str:
        if name in used:
            used[name] += 1
            p = Path(name)
            return f"{p.stem}({used[name]}){p.suffix}"
        used[name] = 0
        return name

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for arc, path, kind in items:
            arc = _unique(arc)
            try:
                if kind == "zip" and path.is_dir():
                    base = Path(arc).stem
                    for cur, _dirs, files in os.walk(path):
                        for f in sorted(files):
                            full = Path(cur) / f
                            rel = full.relative_to(path)
                            zi = zipfile.ZipInfo(str(Path(base) / rel).replace("\\", "/"),
                                                 date_time=_safe_mtime(full))
                            zi.compress_type = zipfile.ZIP_DEFLATED
                            zi.external_attr = 0o644 << 16
                            zf.writestr(zi, full.read_bytes())
                elif path.is_file():
                    zi = zipfile.ZipInfo(arc, date_time=_safe_mtime(path))
                    zi.compress_type = zipfile.ZIP_DEFLATED
                    zi.external_attr = 0o644 << 16
                    with open(path, "rb") as fh:
                        zf.writestr(zi, fh.read())
            except Exception as e:
                logger.warning(f"[字体管家] 打包 {path} 失败: {e}")
    return buf.getvalue()


@router.get("/jobs/{job_id}/download", summary="下载处理交付物")
async def download_job(
    job_id: str,
    kind: str = Query("main", description="main=主成品 / cleaned=清理版字幕 / subset=子集字体包"),
):
    """按交付物类型下载。

    - main    : 主成品（按处理模式为 .ass 文件或字体包 zip）
    - cleaned : 附带的 .cleaned.ass（对已内嵌字幕处理时会额外生成）
    - subset  : _subsetted 子集字体文件夹，打包为 zip
    """
    cfg = _cfg()
    roots = _download_roots(cfg)
    async with db.session_scope() as session:
        job = await _load_job(session, job_id)
        status = job.status
        out_kind = job.output_kind or "ass"
        out_path, out_name = job.output_path, job.output_name
        cleaned, subset_dir = job.cleaned_path, job.subset_dir
        filename = job.filename

    if kind == "cleaned":
        if not cleaned:
            raise HTTPException(status_code=400, detail="该任务没有清理版字幕（.cleaned.ass）")
        target = _assert_within(Path(cleaned), roots)
        if not target.is_file():
            raise HTTPException(status_code=404, detail="清理版字幕已丢失")
        return FileResponse(str(target), media_type="application/octet-stream", filename=target.name)

    if kind == "subset":
        if not subset_dir:
            raise HTTPException(status_code=400, detail="该任务没有保留子集字体文件夹")
        target = _assert_within(Path(subset_dir), roots)
        if not target.is_dir():
            raise HTTPException(status_code=404, detail="子集字体文件夹已丢失")
        name = f"{Path(filename).stem}_subsetted.zip"
        blob = await asyncio.to_thread(_zip_payloads, [(name, target, "zip")])
        return Response(content=blob, media_type="application/zip",
                        headers={"Content-Disposition": f'attachment; filename="{name}"'})

    if status != "success" or not out_path:
        raise HTTPException(status_code=400, detail="该任务没有可下载的成品")
    target = _assert_within(Path(out_path), roots)
    if not target.exists():
        raise HTTPException(status_code=404, detail="成品文件已丢失，请重新执行")

    if out_kind == "zip":
        name = out_name or f"{Path(out_path).name}.zip"
        blob = await asyncio.to_thread(_zip_payloads, [(name, target, "zip")])
        return Response(content=blob, media_type="application/zip",
                        headers={"Content-Disposition": f'attachment; filename="{name}"'})
    return FileResponse(str(target), media_type="application/octet-stream",
                        filename=out_name or target.name)


@router.get("/jobs/download-all", summary="打包下载全部成品")
async def download_all_jobs():
    cfg = _cfg()
    roots = _download_roots(cfg)
    async with db.session_scope() as session:
        rows = (await session.execute(
            select(FontSubtitleJob).order_by(FontSubtitleJob.created_at)
        )).scalars().all()
    ready = [r for r in rows if r.status == "success" and r.output_path]
    if not ready:
        raise HTTPException(status_code=400, detail="暂无可下载的成品")

    items: List[Tuple[str, Path, str]] = []
    for r in ready:
        try:
            p = _assert_within(Path(r.output_path), roots)
        except HTTPException:
            continue
        if not p.exists():
            continue
        kind = r.output_kind or "ass"
        name = r.output_name or (f"{Path(r.output_path).name}.zip" if kind == "zip" else p.name)
        items.append((name, p, "zip" if kind == "zip" else "ass"))
    if not items:
        raise HTTPException(status_code=400, detail="暂无有效的成品文件")

    blob = await asyncio.to_thread(_zip_payloads, items)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Response(content=blob, media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="font_subset_{stamp}.zip"'})


# ── 内核更新 ─────────────────────────────────────────────────

@router.get("/update/check", summary="检查 assfonts 上游更新")
async def check_update():
    cfg = _cfg()
    info = await af_binary.check_update(cfg)
    return {"status": "success", "data": info}


@router.post("/update/apply", summary="应用 assfonts 更新")
async def apply_update(payload: Optional[Dict[str, Any]] = None):
    cfg = _cfg()
    body = payload or {}
    download_url = str(body.get("download_url") or "").strip()
    asset_name = str(body.get("asset_name") or "").strip()
    version = str(body.get("version") or "").strip()

    if not download_url:
        info = await af_binary.check_update(cfg)
        if info.get("error"):
            raise HTTPException(status_code=400, detail=info["error"])
        if not info.get("has_update"):
            return {"status": "success", "data": {"success": True, "version": info.get("current", ""),
                                                 "message": "当前已是最新版本"}}
        download_url = info.get("download_url", "")
        asset_name = info.get("asset_name", "")
        version = info.get("latest", "")
    if not download_url.startswith("https://github.com/") and "githubusercontent.com" not in download_url:
        raise HTTPException(status_code=400, detail="下载地址必须来自 GitHub 官方域名")

    result = await af_binary.apply_update(download_url, asset_name, version, cfg)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message") or "更新失败")
    log_audit("字体管家", "更新内核", result.get("message", ""))
    return {"status": "success", "data": result}
