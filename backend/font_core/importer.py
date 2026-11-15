"""字体压缩包导入 —— job 生命周期、比对编排、入库与索引重建节流。

目录约定（与方案一致）：

    data/fonts/import/<job_id>/            # 工作区，不属于字体库
        incoming/    压缩包 / 直接上传的字体（原始留存，便于重跑）
        extracted/   解压出来的字体（入库的唯一来源）
        probe_index/ assfonts 给这批字体建的临时索引（fonts.json）
        report.json  比对报告（new/duplicate/conflict/invalid + 丢弃清单）
        commit.json  入库结果（可选）

    data/fonts/imported/<时间戳>-<job>/     # 入库目标（独立目录，自动进 -f）
    data/fonts/replaced/<job>/             # 冲突替换时旧文件的备份（绝不直接删）

设计要点：
1. 分析（analyze）与入库（commit）分离：先出报告让人看，再落库；天然支持 dry-run。
2. 入库绝不覆盖：重名加序号（沿用路由层 _save_font_blob 的语义）。
3. 索引重建走 debounce：一个番剧季能连着导入几十个包，全量重建一次几分钟，
   合并到窗口结束跑一次。
4. 对外函数不抛异常，返回结构化结果。
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import shutil
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from font_core import archive, ass_parser, font_probe, index_delta, index_store, subset_service

logger = logging.getLogger(__name__)

DEFAULT_IMPORT_DIR = "data/fonts/import"
DEFAULT_IMPORTED_DIR = "data/fonts/imported"
DEFAULT_REPLACED_DIR = "data/fonts/replaced"
DEFAULT_DEBOUNCE = 120
JOB_TTL_HOURS = 24

_REBUILD_TASKS: Dict[str, asyncio.Task] = {}


# ── 配置读取 ────────────────────────────────────────────────

def _fm(cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return (cfg or {}).get("font_manager", {}) or {}


def import_root(cfg: Optional[Dict[str, Any]] = None) -> Path:
    return Path(str(_fm(cfg).get("import_dir") or DEFAULT_IMPORT_DIR))


def imported_root(cfg: Optional[Dict[str, Any]] = None) -> Path:
    return Path(str(_fm(cfg).get("imported_dir") or DEFAULT_IMPORTED_DIR))


def replaced_root(cfg: Optional[Dict[str, Any]] = None) -> Path:
    return Path(str(_fm(cfg).get("replaced_dir") or DEFAULT_REPLACED_DIR))


def import_target_mode(cfg: Optional[Dict[str, Any]] = None) -> str:
    mode = str(_fm(cfg).get("import_target") or "separate").strip().lower()
    return mode if mode in ("separate", "primary") else "separate"


def limits(cfg: Optional[Dict[str, Any]] = None) -> archive.Limits:
    fm = _fm(cfg)
    base = archive.Limits()
    try:
        return archive.Limits(
            max_archive_bytes=int(fm.get("import_max_archive_mb")
                                  or base.max_archive_bytes // 1024 // 1024) * 1024 * 1024,
            max_extract_bytes=int(fm.get("import_max_extract_mb")
                                  or base.max_extract_bytes // 1024 // 1024) * 1024 * 1024,
            max_entries=int(fm.get("import_max_entries") or base.max_entries),
            max_fonts=int(fm.get("import_max_fonts") or base.max_fonts),
            max_font_bytes=int(fm.get("import_max_font_mb")
                               or base.max_font_bytes // 1024 // 1024) * 1024 * 1024,
        )
    except (TypeError, ValueError):
        return base


def debounce_seconds(cfg: Optional[Dict[str, Any]] = None) -> int:
    try:
        v = int(_fm(cfg).get("import_rebuild_debounce") or DEFAULT_DEBOUNCE)
    except (TypeError, ValueError):
        v = DEFAULT_DEBOUNCE
    return max(0, min(3600, v))


def ttl_hours(cfg: Optional[Dict[str, Any]] = None) -> int:
    """导入工作区（最近导入任务）的保留时长，单位小时。

    计时基准是 job 根目录的 mtime —— 建 job、写 report.json（分析）、写 commit.json
    （入库）都会刷新它，所以「保留时长」是从**最后一次操作**算起，不是从上传时刻。
    清理是惰性的：只在下次上传压缩包时顺带执行，不会自己到点消失。
    """
    try:
        v = int(_fm(cfg).get("import_job_ttl_hours") or JOB_TTL_HOURS)
    except (TypeError, ValueError):
        v = JOB_TTL_HOURS
    return max(1, min(720, v))


def imported_dir_active(cfg: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """需要额外挂进 -f 的独立入库目录；未启用或目录还没建时返回 None。

    为什么只在目录存在时返回：assfonts 的 -f 遇到不存在的目录会直接报错，
    而「还没导入过任何字体」是常态。
    """
    if import_target_mode(cfg) != "separate":
        return None
    d = imported_root(cfg)
    try:
        return str(d) if d.is_dir() else None
    except OSError:
        return None


# ── job 工作区 ──────────────────────────────────────────────

def job_paths(cfg: Optional[Dict[str, Any]], job_id: str) -> Dict[str, Path]:
    root = import_root(cfg) / str(job_id)
    return {
        "root": root,
        "incoming": root / "incoming",
        "extracted": root / "extracted",
        "probe": root / "probe_index",
        "report": root / "report.json",
        "commit": root / "commit.json",
    }


def find_job(cfg: Optional[Dict[str, Any]], job_id: str) -> Optional[Dict[str, Path]]:
    """定位 job；job_id 只允许字母数字与短横线（防目录穿越）。"""
    jid = str(job_id or "").strip()
    if not jid or not all(ch.isalnum() or ch in "-_" for ch in jid):
        return None
    paths = job_paths(cfg, jid)
    return paths if paths["root"].is_dir() else None


def create_job(cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """新建一个导入 job（只建目录，不解析）。"""
    job_id = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
    paths = job_paths(cfg, job_id)
    for key in ("incoming", "extracted"):
        paths[key].mkdir(parents=True, exist_ok=True)
    logger.info(f"[字体导入] 新建 job {job_id} → {paths['root']}")
    return {"job_id": job_id, "dir": str(paths["root"]), "created_at": _now()}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _write_json(path: Path, data: Any) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
        return True
    except Exception as e:
        logger.warning(f"[字体导入] 写 JSON 失败 {path}: {type(e).__name__} {e}")
        return False


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with open(path, "rb") as fh:
            while True:
                chunk = fh.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
    except OSError:
        return ""
    return digest.hexdigest()


def _unique_name(dest: Path, name: str, used: set) -> str:
    stem, ext = os.path.splitext(name)
    candidate = name
    i = 1
    while candidate.lower() in used or (dest / candidate).exists():
        candidate = f"{stem}_{i}{ext}"
        i += 1
        if i > 9999:
            candidate = f"{stem}_{uuid.uuid4().hex[:6]}{ext}"
            break
    used.add(candidate.lower())
    return candidate


# ── 分析 ────────────────────────────────────────────────────

async def _prepare_extracted(cfg: Optional[Dict[str, Any]], paths: Dict[str, Path],
                             lim: archive.Limits, *, force: bool) -> tuple:
    """把 incoming/ 里的压缩包解压、字体复制进 extracted/，返回 (archives_info, skipped, incoming)。

    force=True 时先清空 extracted/（并清掉探测索引），保证重复调用不会产生 _1 副本。
    返回的 incoming 每项：{name, source, size, sha256, path}
    """
    extracted = paths["extracted"]
    if force:
        shutil.rmtree(extracted, ignore_errors=True)
        shutil.rmtree(paths["probe"], ignore_errors=True)
    extracted.mkdir(parents=True, exist_ok=True)

    archives_info: List[Dict[str, Any]] = []
    skipped: List[Dict[str, str]] = []
    used: set = set()

    try:
        entries = sorted(paths["incoming"].iterdir())
    except OSError:
        entries = []
    for entry in entries:
        if not entry.is_file():
            continue
        if archive.is_archive_name(entry.name):
            result = await archive.extract_archive(entry, extracted, limits=lim)
            archives_info.append({
                "name": entry.name,
                "format": archive.sniff_format(entry.name),
                "success": result.get("success", False),
                "message": result.get("message", ""),
                "extractor": result.get("extractor", ""),
                "fonts": len(result.get("fonts") or []),
                "skipped": result.get("skipped_count", 0),
            })
            for item in result.get("skipped") or []:
                skipped.append({"archive": entry.name, **item})
            continue
        if not ass_parser.is_font_file(entry.name):
            skipped.append({"archive": "", "name": entry.name,
                            "reason": "既不是压缩包也不是字体文件"})
            continue
        size = entry.stat().st_size
        if size <= 0:
            skipped.append({"archive": "", "name": entry.name, "reason": "空文件"})
            continue
        if size > lim.max_font_bytes:
            skipped.append({"archive": "", "name": entry.name,
                            "reason": f"单个字体过大（>{lim.max_font_bytes // 1024 // 1024}MB）"})
            continue
        stored = _unique_name(extracted, entry.name, used)
        try:
            shutil.copy2(str(entry), str(extracted / stored))
        except OSError as e:
            skipped.append({"archive": "", "name": entry.name, "reason": f"复制失败：{e}"})
            continue

    incoming: List[Dict[str, Any]] = []
    for f in sorted(extracted.iterdir()):
        if not f.is_file() or not ass_parser.is_font_file(f.name):
            continue
        try:
            size = f.stat().st_size
        except OSError:
            continue
        incoming.append({"name": f.name, "source": f.name, "size": size,
                         "sha256": _sha256(f), "path": str(f)})
    return archives_info, skipped, incoming


def report_file_names(report: Optional[Dict[str, Any]]) -> List[str]:
    """报告里「待入库」的文件名（new + conflict）。"""
    if not report:
        return []
    names: List[str] = []
    for key in ("new", "conflict"):
        for entry in report.get(key) or []:
            name = str(entry.get("name") or "")
            if name and name not in names:
                names.append(name)
    return names


async def ensure_extracted(cfg: Optional[Dict[str, Any]], job_id: str) -> Dict[str, Any]:
    """确保 report 里列出的字体仍在 extracted/ 里；不在就按需重新解压。

    背景：入库成功后我们会删掉 extracted/（字体已搬走、省空间），
    所以「从历史任务再次入库」必须先按需重放一遍解压，否则每个文件都会报
    「源文件不存在」。原始压缩包留在 incoming/ 里直到任务过期（TTL），够用。
    """
    paths = find_job(cfg, job_id)
    if not paths:
        return {"ok": False, "reextracted": False, "message": "导入任务不存在或已过期"}
    report = _read_json(paths["report"])
    if not report:
        return {"ok": False, "reextracted": False, "message": "该任务还没有分析报告，请先重新分析"}
    names = report_file_names(report)
    if not names:
        return {"ok": True, "reextracted": False, "missing": [], "message": ""}

    extracted = paths["extracted"]
    missing = [n for n in names if not (extracted / n).is_file()]
    if not missing:
        return {"ok": True, "reextracted": False, "missing": [], "message": ""}

    try:
        has_source = paths["incoming"].is_dir() and any(paths["incoming"].iterdir())
    except OSError:
        has_source = False
    if not has_source:
        return {"ok": False, "reextracted": False, "missing": missing,
                "message": "原始压缩包已随任务清理，无法重新解压；请重新上传该压缩包"}

    await _prepare_extracted(cfg, paths, limits(cfg), force=True)
    still = [n for n in names if not (extracted / n).is_file()]
    if still:
        return {"ok": False, "reextracted": True, "missing": still,
                "message": f"重新解压后仍缺少 {len(still)} 个文件（压缩包内容可能已变化），建议重新分析"}
    return {"ok": True, "reextracted": True, "missing": [],
            "message": f"已按需重新解压 {len(names)} 个字体"}


async def analyze(cfg: Optional[Dict[str, Any]], binary: Path, job_id: str) -> Dict[str, Any]:
    """解压 + 探测 + 比对，产出 report.json（不动字体库）。

    每次调用都会先清空 extracted/ 再重放解压，所以可以反复调用（「重新分析」）。
    """
    paths = find_job(cfg, job_id)
    if not paths:
        return {"success": False, "message": "导入任务不存在或已过期"}
    lim = limits(cfg)
    archives_info, skipped, incoming = await _prepare_extracted(cfg, paths, lim, force=True)
    extracted = paths["extracted"]

    if not incoming:
        report = {"success": False, "job_id": job_id,
                  "message": "没有从上传内容里发现字体文件",
                  "archives": archives_info, "skipped": skipped[:500],
                  "skipped_count": len(skipped),
                  "counts": {"new": 0, "duplicate": 0, "conflict": 0, "invalid": 0}}
        _write_json(paths["report"], {**report, "created_at": _now()})
        return report

    # 3) assfonts 探测（给这批字体建临时索引）
    probe = await font_probe.probe_directory(
        binary, extracted, paths["probe"],
        threads=int(_fm(cfg).get("internal_threads") or 0),
        verbose=int(_fm(cfg).get("verbose_level", 3) or 3))

    # 4) 与主库比对
    libs = subset_service.library_dirs(cfg)
    lib = await asyncio.to_thread(font_probe.library_faces, cfg, libs)
    # 连续导入时主索引还没重建：把「刚入库、还没进索引」的 face 从增量缓存并进来，
    # 否则上一个包刚入库的字体在这里「看不见」，会被判成新增 → 重复入库。
    lib = {**lib, "faces": index_delta.merged_faces(lib.get("faces") or [], cfg)}
    fresh = await asyncio.to_thread(_library_freshness, libs, lib.get("built_at", ""))
    # 如果「看起来过期」是因为我们自己刚导入还没重建（delta 已覆盖），那不算过期，不需要重建
    if fresh.get("stale") and index_delta.covers(cfg, fresh.get("newest_ts") or 0):
        fresh["stale"] = False
        fresh["covered_by_delta"] = True
    if probe.get("success"):
        compared = font_probe.compare(incoming, probe, lib)
    else:
        compared = _compare_hash_only(incoming, lib, libs)
        compared["probe_error"] = probe.get("message", "")

    report = {
        "success": True,
        "job_id": job_id,
        "created_at": _now(),
        "archives": archives_info,
        "skipped": skipped[:500],
        "skipped_count": len(skipped),
        "probe": {"success": bool(probe.get("success")),
                  "faces": probe.get("count", 0),
                  "message": probe.get("message", "")},
        "library": {"index_available": compared.get("library_index_available", False),
                    "faces": compared.get("compared_faces", 0),
                    "dirs": libs,
                    "error": compared.get("library_index_error", ""),
                    "built_at": lib.get("built_at", ""),
                    "stale": bool(fresh.get("stale")),
                    "covered_by_delta": bool(fresh.get("covered_by_delta")),
                    "newest": fresh.get("newest", ""),
                    "truncated": bool(fresh.get("truncated"))},
        "counts": compared.get("counts", {}),
        "new": compared.get("new", []),
        "duplicate": compared.get("duplicate", []),
        "conflict": compared.get("conflict", []),
        "invalid": compared.get("invalid", []),
        "probe_error": compared.get("probe_error", ""),
        "target": target_dir_label(cfg),
    }
    _write_json(paths["report"], report)
    logger.info(f"[字体导入] {job_id} 分析完成：新增 {report['counts'].get('new', 0)} / "
                f"重复 {report['counts'].get('duplicate', 0)} / "
                f"冲突 {report['counts'].get('conflict', 0)} / "
                f"无效 {report['counts'].get('invalid', 0)}")
    return report


def _compare_hash_only(incoming: List[Dict[str, Any]],
                       lib: Dict[str, Any],
                       library_dirs: Optional[List[str]] = None) -> Dict[str, Any]:
    """内核不可用时的降级比对：只按「同名 + 同大小 + 同 sha256」判重复。

    宁可少判重复（都当新增），也不要在没有 face 依据时误并/误删。
    索引不可用时直接扫库目录的文件名（只有同名候选才去算哈希，代价可控）。
    """
    by_name: Dict[str, List[str]] = {}
    for face in lib.get("faces") or []:
        p = str(face.get("path") or "")
        if p:
            by_name.setdefault(Path(p).name.lower(), []).append(p)
    if not by_name and library_dirs:
        by_name = _scan_library_names(library_dirs)
    out: Dict[str, List[Dict[str, Any]]] = {"new": [], "duplicate": [],
                                            "conflict": [], "invalid": []}
    for item in incoming:
        base = {"name": item["name"], "source": item.get("source", item["name"]),
                "size": item["size"]}
        dup = ""
        for cand in by_name.get(item["name"].lower(), []):
            p = Path(cand)
            try:
                if p.stat().st_size != item["size"]:
                    continue
            except OSError:
                continue
            if font_probe.sha256_file(p) == item.get("sha256"):
                dup = cand
                break
        if dup:
            out["duplicate"].append({**base, "reason": "逐字节相同（内核不可用，仅按哈希判定）",
                                     "existing": dup})
        else:
            out["new"].append({**base, "faces": [], "note": "内核不可用，未做 face 级比对"})
    counts = {k: len(v) for k, v in out.items()}
    return {**out, "counts": counts,
            "compared_faces": len(lib.get("faces") or []),
            "library_index_available": bool(lib.get("exists")),
            "library_index_error": lib.get("error", "")}


def _library_freshness(library_dirs: List[str], built_at: str,
                       max_entries: int = 20000) -> Dict[str, Any]:
    """主库索引是否比字体库里的文件更旧。

    索引过期时比对会把「其实已经在库里」的字体全判成新增，导入后就成了重复文件。
    这里只扫字体库目录（不含系统字体），entries 有上限，避免 NAS 上拖太久。
    """
    out: Dict[str, Any] = {"built_at": built_at, "newest": "", "stale": False,
                           "scanned": 0, "truncated": False}
    try:
        built_ts = datetime.fromisoformat(built_at).timestamp() if built_at else 0.0
    except (TypeError, ValueError):
        built_ts = 0.0
    newest = 0.0
    scanned = 0
    for d in library_dirs or []:
        root = Path(str(d or ""))
        try:
            if not root.is_dir():
                continue
        except OSError:
            continue
        stack = [root]
        while stack and scanned < max_entries:
            cur = stack.pop()
            try:
                it = os.scandir(cur)
            except OSError:
                continue
            with it:
                for entry in it:
                    scanned += 1
                    if scanned >= max_entries:
                        out["truncated"] = True
                        break
                    try:
                        if entry.is_dir():
                            stack.append(Path(entry.path))
                            continue
                        if not ass_parser.is_font_file(entry.name):
                            continue
                        mtime = entry.stat().st_mtime
                    except OSError:
                        continue
                    if mtime > newest:
                        newest = mtime
    out["scanned"] = scanned
    if newest:
        out["newest"] = datetime.fromtimestamp(newest).isoformat(timespec="seconds")
        out["newest_ts"] = newest
        out["stale"] = bool(built_ts and newest > built_ts + 1)
    return out


def _scan_library_names(library_dirs: List[str],
                        max_files: int = 200000) -> Dict[str, List[str]]:
    """扫字体库目录，建立「文件名 → 路径」映射（降级比对专用）。"""
    out: Dict[str, List[str]] = {}
    seen = 0
    for d in library_dirs:
        root_dir = Path(str(d or ""))
        if not root_dir.is_dir():
            continue
        for root, _dirs, files in os.walk(root_dir):
            for name in files:
                if not ass_parser.is_font_file(name):
                    continue
                out.setdefault(name.lower(), []).append(str(Path(root) / name))
                seen += 1
                if seen >= max_files:
                    return out
    return out


def get_report(cfg: Optional[Dict[str, Any]], job_id: str) -> Optional[Dict[str, Any]]:
    paths = find_job(cfg, job_id)
    if not paths:
        return None
    return _read_json(paths["report"])


def target_dir_base(cfg: Optional[Dict[str, Any]] = None) -> Path:
    """导入字体的落库根目录（每次导入在其下建一个 <时间戳>-<job> 子目录）。"""
    if import_target_mode(cfg) == "primary":
        libs = subset_service.library_dirs(cfg)
        return (Path(libs[0]) / "imported") if libs else imported_root(cfg)
    return imported_root(cfg)


def _configured_library_dirs(cfg: Optional[Dict[str, Any]] = None) -> List[str]:
    """用户配置的字体库目录（主库 + 额外库），不含导入目录。

    不能用 subset_service.library_dirs()：那个函数会把导入目录也算进去，
    拿来判断「导入目录是否在库内」会变成自己跟自己比。
    """
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


def target_in_library(cfg: Optional[Dict[str, Any]] = None) -> bool:
    """落库目录是否已被某个字体库目录覆盖。

    True 表示：assfonts 建索引时通过库目录的 -f 已经能扫到它，
    **不需要**再把它单独作为 -f 关联（否则同一批字体被扫两遍）。
    """
    base = str(target_dir_base(cfg))
    return any(subset_service.under_dir(base, d) for d in _configured_library_dirs(cfg))


POLICY_KEEP = "keep"
POLICY_REPLACE = "replace"
POLICY_SKIP = "skip"
POLICIES = (POLICY_KEEP, POLICY_REPLACE, POLICY_SKIP)


def normalize_policy(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text if text in POLICIES else POLICY_KEEP


def default_policy(cfg: Optional[Dict[str, Any]] = None) -> str:
    """设置里配置的默认冲突策略（导入页可以按单次覆盖）。

    keep    = 保留库内已有版本（默认，最安全）
    replace = 把旧文件移到 replaced/ 后替换
    skip    = 与 keep 同效，但语义上是「显式跳过」
    """
    return normalize_policy(_fm(cfg).get("import_default_policy"))


def subfolder_enabled(cfg: Optional[Dict[str, Any]] = None) -> bool:
    """每次导入是否在落库目录下建 `<时间戳>-<任务号>` 子目录。

    开启（默认）：每次导入一个独立子目录，便于按批次整体回滚/清理；
    关闭：字体直接放进落库目录，同名靠序号避让（`_unique_name`），
          适合「落库目录本身就是按番剧分好的目录」这种用法。
    """
    value = _fm(cfg).get("import_subfolder")
    return True if value is None else bool(value)


def target_dir_label(cfg: Optional[Dict[str, Any]]) -> str:
    if import_target_mode(cfg) == "primary":
        libs = subset_service.library_dirs(cfg)
        return str((Path(libs[0]) / "imported") if libs else "（未配置字体库）")
    return str(imported_root(cfg))


# ── 入库 ────────────────────────────────────────────────────

def _target_dir(cfg: Optional[Dict[str, Any]], job_id: str) -> Path:
    """本次入库的落盘目录：开子目录开关时按 <时间戳>-<任务号> 建，否则直接用落库根目录。"""
    base = target_dir_base(cfg)
    if not subfolder_enabled(cfg):
        return base
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    short = job_id.split("-")[-1][:6] or job_id[:6]
    return base / f"{stamp}-{short}"


def _move_into(src: Path, dest_dir: Path, name: str, used: set) -> Dict[str, Any]:
    """把字体搬进目标目录，绝不覆盖（重名加序号）。"""
    dest_dir.mkdir(parents=True, exist_ok=True)
    stored = _unique_name(dest_dir, name, used)
    target = dest_dir / stored
    try:
        shutil.move(str(src), str(target))
    except Exception as e:
        return {"action": "failed", "stored": name,
                "note": f"搬运失败：{type(e).__name__} {e}"}
    return {"action": "added", "stored": stored, "note": ""}


def commit(cfg: Optional[Dict[str, Any]], job_id: str, *,
           select: Optional[List[str]] = None,
           policy: Optional[str] = None) -> Dict[str, Any]:
    """把报告里选中的字体落库。

    :param select: 要入库的文件名（对应 report 里的 name）；None=全部 new
    :param policy: 冲突处理 keep/replace/skip；None=取设置里的默认策略
    """
    paths = find_job(cfg, job_id)
    if not paths:
        return {"success": False, "message": "导入任务不存在或已过期"}
    report = _read_json(paths["report"])
    if not report:
        return {"success": False, "message": "还没有分析报告，请先执行分析"}
    policy = normalize_policy(policy or default_policy(cfg))

    new_entries = list(report.get("new") or [])
    conflict_entries = list(report.get("conflict") or [])
    by_name: Dict[str, Dict[str, Any]] = {e["name"]: e for e in new_entries}
    conflict_by_name = {e["name"]: e for e in conflict_entries}

    if select is None:
        chosen: List[Dict[str, Any]] = list(new_entries)
    else:
        chosen = []
        for name in select:
            entry = by_name.get(name) or conflict_by_name.get(name)
            if entry and entry not in chosen:
                chosen.append(entry)
    if not chosen:
        return {"success": True, "message": "没有需要入库的字体", "committed": [],
                "skipped": [], "count": 0, "target": ""}

    extracted = paths["extracted"].resolve()
    target_dir = _target_dir(cfg, job_id)
    replaced_dir = replaced_root(cfg) / job_id
    used: set = set()
    committed: List[Dict[str, Any]] = []
    skipped: List[Dict[str, str]] = []
    backed_up = False

    for entry in chosen:
        name = str(entry.get("name") or "")
        try:
            src_resolved = (extracted / name).resolve()
        except OSError:
            skipped.append({"name": name, "reason": "路径解析失败"})
            continue
        if extracted not in src_resolved.parents or not src_resolved.is_file():
            skipped.append({"name": name,
                            "reason": "源文件不存在（原始压缩包已清理，无法重新解压；请重新上传）"})
            continue

        is_conflict = name in conflict_by_name
        if is_conflict and policy in ("keep", "skip"):
            skipped.append({"name": name, "reason": "与库内同 face 冲突，按策略保留库内版本"})
            continue
        if is_conflict and policy == "replace":
            for item in (conflict_by_name[name].get("conflicts") or []):
                for existing in item.get("existing") or []:
                    old = Path(str(existing.get("path") or ""))
                    if not old.is_file():
                        continue
                    try:
                        replaced_dir.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(old), str(replaced_dir / old.name))
                        backed_up = True
                    except Exception as e:
                        logger.warning(f"[字体导入] 备份旧字体失败 {old}: {e}")

        moved = _move_into(src_resolved, target_dir, name, used)
        if moved["action"] == "failed":
            skipped.append({"name": name, "reason": moved["note"]})
            continue
        committed.append({
            "name": name,
            "stored": moved["stored"],
            "size": int(entry.get("size") or 0),
            "faces": entry.get("faces") or [],
            "replaced": policy == "replace" and is_conflict,
            "source": entry.get("source") or name,
        })

    result = {
        "success": True,
        "job_id": job_id,
        "target": str(target_dir),
        "count": len(committed),
        "committed": committed,
        # 入库后的文件路径：调用方拿去做「增量索引探测」，避免全量重建
        "paths": [str(target_dir / str(c.get("stored") or "")) for c in committed],
        "skipped": skipped,
        "replaced_backup": str(replaced_dir) if backed_up else "",
        "message": f"入库 {len(committed)} 个字体"
                   + (f"，跳过 {len(skipped)} 个" if skipped else ""),
    }
    # 一个都没入库（全是冲突/失败）时保留 extracted，方便换策略重试；
    # 真入库了才清理，避免把还没搬走的字体删掉。
    if committed:
        # 报告里去掉已入库的条目：再点一次「入库」不会重复导入，
        # 「详情」也只显示还没入库的部分（报告因此可以安全地反复使用）。
        done = {str(c.get("name") or "") for c in committed}
        report["new"] = [e for e in (report.get("new") or []) if str(e.get("name") or "") not in done]
        report["conflict"] = [e for e in (report.get("conflict") or [])
                              if str(e.get("name") or "") not in done]
        report["counts"] = {
            "new": len(report["new"]),
            "duplicate": len(report.get("duplicate") or []),
            "conflict": len(report["conflict"]),
            "invalid": len(report.get("invalid") or []),
        }
        report["last_commit"] = {"at": _now(), "count": len(committed),
                                 "target": str(target_dir)}
        _write_json(paths["report"], report)
        _write_json(paths["commit"], {"committed_at": _now(), **result})
        shutil.rmtree(paths["extracted"], ignore_errors=True)
        shutil.rmtree(paths["probe"], ignore_errors=True)
    return result


# ── job 列表 / 清理 ─────────────────────────────────────────

def list_jobs(cfg: Optional[Dict[str, Any]] = None, limit: int = 20) -> List[Dict[str, Any]]:
    root = import_root(cfg)
    out: List[Dict[str, Any]] = []
    try:
        entries = [d for d in root.iterdir() if d.is_dir()]
    except OSError:
        return out
    entries.sort(key=lambda d: d.name, reverse=True)
    for d in entries[: max(1, int(limit))]:
        report = _read_json(d / "report.json") or {}
        commit_info = _read_json(d / "commit.json") or {}
        out.append({
            "job_id": d.name,
            "created_at": report.get("created_at", ""),
            "archives": [a.get("name") for a in (report.get("archives") or [])],
            "counts": report.get("counts") or {},
            "analyzed": bool(report),
            "committed": bool(commit_info),
            "committed_count": int(commit_info.get("count") or 0),
        })
    return out


def delete_job(cfg: Optional[Dict[str, Any]], job_id: str) -> Dict[str, Any]:
    paths = find_job(cfg, job_id)
    if not paths:
        return {"success": False, "message": "导入任务不存在"}
    shutil.rmtree(paths["root"], ignore_errors=True)
    return {"success": True, "message": f"已删除导入任务 {job_id}"}


def cleanup_expired(cfg: Optional[Dict[str, Any]] = None,
                    hours: Optional[int] = None) -> int:
    """清理过期的导入工作区（默认取配置 import_job_ttl_hours，24 小时）。

    返回删掉的 job 数。惰性调用点：每次上传压缩包时（见路由 /import/upload）。
    """
    root = import_root(cfg)
    cutoff = datetime.now() - timedelta(hours=int(hours if hours is not None else ttl_hours(cfg)))
    removed = 0
    try:
        for d in root.iterdir():
            if not d.is_dir():
                continue
            try:
                mtime = datetime.fromtimestamp(d.stat().st_mtime)
            except OSError:
                continue
            if mtime < cutoff:
                shutil.rmtree(d, ignore_errors=True)
                removed += 1
    except OSError:
        return removed
    return removed


# ── 压缩包 → 临时字体池 ─────────────────────────────────────
#
# 与「导入入库」完全分开：这里只解压、把字体丢进临时池（data/fonts/temp_fonts），
# 不比对、不写字体库 —— 对应页面上「拖进压缩包 = 先进临时池、能用但不入库」。

def temp_staging_root(cfg: Optional[Dict[str, Any]] = None) -> Path:
    """临时字体导入的解压暂存区（在 import/ 同级，随用随删）。"""
    return import_root(cfg).parent / "temp_archive"


def _duplicate_in_pool(dest: Path, name: str, sha256: str = "") -> bool:
    """目标池里是否已有同名同内容的字体。"""
    cand = dest / name
    if not cand.is_file():
        return False
    if sha256:
        return _sha256(cand) == sha256
    return False


def _move_font_into(src: Path, dest: Path, used: set) -> str:
    """把字体搬进池子里，重名加序号，绝不覆盖。"""
    dest.mkdir(parents=True, exist_ok=True)
    name = _unique_name(dest, src.name, used)
    try:
        shutil.move(str(src), str(dest / name))
    except Exception as e:
        raise OSError(f"搬运失败：{type(e).__name__} {e}") from e
    return name


async def add_archives_to_temp_pool(cfg: Optional[Dict[str, Any]], binary: Path,
                                    archive_paths: List[Path], *,
                                    limits_override: Optional[archive.Limits] = None) -> Dict[str, Any]:
    """解压一批压缩包，把里面的字体放进临时字体池，并刷新临时索引。

    返回 {"fonts": [{filename,size,action}], "skipped": [...], "archives": [...],
          "added": int, "temp": {dir,count,index}}
    """
    cfg = cfg or {}
    lim = limits_override or limits(cfg)
    pool = subset_service.temp_font_dir(cfg)
    pool.mkdir(parents=True, exist_ok=True)
    staging = temp_staging_root(cfg) / uuid.uuid4().hex[:12]

    fonts: List[Dict[str, Any]] = []
    skipped: List[Dict[str, str]] = []
    archives: List[Dict[str, Any]] = []
    used: set = set()

    try:
        for idx, path in enumerate(archive_paths):
            path = Path(path)
            if not archive.is_archive_name(path.name):
                skipped.append({"archive": path.name, "name": path.name,
                                "reason": "不是压缩包（临时字体池只接受压缩包或字体文件）"})
                continue
            out_dir = staging / f"x{idx}"
            result = await archive.extract_archive(path, out_dir, limits=lim)
            archives.append({
                "name": path.name,
                "format": archive.sniff_format(path.name),
                "success": bool(result.get("success")),
                "message": result.get("message", ""),
                "extractor": result.get("extractor", ""),
                "fonts": len(result.get("fonts") or []),
                "skipped": result.get("skipped_count", 0),
            })
            for item in result.get("skipped") or []:
                skipped.append({"archive": path.name, **item})
            for item in result.get("fonts") or []:
                src = out_dir / str(item.get("name") or "")
                if not src.is_file():
                    continue
                if _duplicate_in_pool(pool, src.name, str(item.get("sha256") or "")):
                    fonts.append({"filename": src.name, "size": int(item.get("size") or 0),
                                  "action": "duplicate", "archive": path.name})
                    continue
                try:
                    stored = _move_font_into(src, pool, used)
                except OSError as e:
                    skipped.append({"archive": path.name, "name": src.name, "reason": str(e)})
                    continue
                fonts.append({"filename": stored, "size": int(item.get("size") or 0),
                              "action": "added", "archive": path.name})
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    added = [f for f in fonts if f.get("action") == "added"]
    index_info: Dict[str, Any] = {}
    if added and Path(str(binary)).is_file():
        fm = _fm(cfg)
        built = await index_store.build_index(
            Path(binary), [str(pool)], subset_service.temp_index_dir(cfg),
            threads=int(fm.get("internal_threads") or 0),
            verbose=int(fm.get("verbose_level", 3) or 3))
        if built.get("success"):
            info = index_store.read_index(subset_service.temp_index_dir(cfg))
            index_info = {"exists": info.get("exists", False), "count": info.get("count", 0),
                          "file_count": info.get("file_count", 0)}
        else:
            index_info = {"exists": False, "count": 0, "error": built.get("message", "")}

    return {
        "fonts": fonts,
        "skipped": skipped,
        "archives": archives,
        "added": len(added),
        "temp": {"dir": str(pool),
                 "count": len([p for p in pool.glob("*")
                               if p.is_file() and ass_parser.is_font_file(p.name)]),
                 "index": index_info},
    }


# ── 索引重建（debounce）─────────────────────────────────────

def schedule_rebuild(cfg: Optional[Dict[str, Any]], binary: Path, *,
                     on_state=None, delay: Optional[int] = None) -> Dict[str, Any]:
    """入库后延迟合并重建索引；同一索引目录只保留最后一次计时。"""
    seconds = debounce_seconds(cfg) if delay is None else max(0, int(delay))
    key = str(index_store.index_dir(cfg))

    old = _REBUILD_TASKS.get(key)
    if old is not None and not old.done():
        old.cancel()

    async def _runner() -> None:
        try:
            await asyncio.sleep(seconds)
        except asyncio.CancelledError:
            return
        await _do_rebuild(cfg, binary, on_state)

    try:
        task = asyncio.get_running_loop().create_task(_runner())
    except RuntimeError:
        return {"scheduled": False, "message": "没有运行中的事件循环"}
    _REBUILD_TASKS[key] = task
    return {"scheduled": True, "delay": seconds}


async def _notify(on_state, state: str, payload: Optional[Dict[str, Any]] = None) -> None:
    """回调既支持同步函数也支持协程（路由层要塞 SSE 广播）。"""
    if on_state is None:
        return
    try:
        ret = on_state(state, payload or {})
        if asyncio.iscoroutine(ret):
            await ret
    except Exception:
        pass


async def _do_rebuild(cfg: Optional[Dict[str, Any]], binary: Path,
                      on_state=None) -> Dict[str, Any]:
    libs = subset_service.library_dirs(cfg)
    if not libs:
        await _notify(on_state, "skipped", {"message": "未配置字体库目录"})
        return {"success": False, "message": "未配置字体库目录"}
    fm = _fm(cfg)
    await _notify(on_state, "running", {})
    started = time.time()
    try:
        result = await index_store.build_index(
            binary, libs, index_store.index_dir(cfg),
            threads=int(fm.get("internal_threads") or 0),
            verbose=int(fm.get("verbose_level", 3) or 3))
    except Exception as e:      # 对外不抛
        result = {"success": False, "message": f"索引重建异常：{type(e).__name__} {e}"}
    await _notify(on_state, "done" if result.get("success") else "failed", result)
    if result.get("success"):
        # 重建开始后又有新字体的，保留在 delta 里继续当比对基线
        index_delta.prune(cfg, started)
    return result


async def rebuild_now(cfg: Optional[Dict[str, Any]], binary: Path,
                      on_state=None) -> Dict[str, Any]:
    """立刻重建索引（跳过 debounce；测试与「立即刷新」按钮用）。"""
    return await _do_rebuild(cfg, binary, on_state)
