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
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from font_core import archive, ass_parser, font_probe, index_store, subset_service

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

async def analyze(cfg: Optional[Dict[str, Any]], binary: Path, job_id: str) -> Dict[str, Any]:
    """解压 + 探测 + 比对，产出 report.json（不动字体库）。"""
    paths = find_job(cfg, job_id)
    if not paths:
        return {"success": False, "message": "导入任务不存在或已过期"}
    lim = limits(cfg)
    extracted = paths["extracted"]
    extracted.mkdir(parents=True, exist_ok=True)

    archives_info: List[Dict[str, Any]] = []
    skipped: List[Dict[str, str]] = []
    incoming: List[Dict[str, Any]] = []
    used: set = set()

    # 1) 处理 incoming：压缩包解压，字体直接搬进 extracted
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

    # 2) 清点 extracted，算 sha256
    for f in sorted(extracted.iterdir()):
        if not f.is_file() or not ass_parser.is_font_file(f.name):
            continue
        try:
            size = f.stat().st_size
        except OSError:
            continue
        incoming.append({"name": f.name, "source": f.name, "size": size,
                         "sha256": _sha256(f), "path": str(f)})

    if not incoming:
        report = {"success": False, "job_id": job_id,
                  "message": "没有从上传内容里发现字体文件",
                  "archives": archives_info, "skipped": skipped[:500],
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
    fresh = await asyncio.to_thread(_library_freshness, libs, lib.get("built_at", ""))
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


def target_dir_label(cfg: Optional[Dict[str, Any]]) -> str:
    if import_target_mode(cfg) == "primary":
        libs = subset_service.library_dirs(cfg)
        return str((Path(libs[0]) / "imported") if libs else "（未配置字体库）")
    return str(imported_root(cfg))


# ── 入库 ────────────────────────────────────────────────────

def _target_dir(cfg: Optional[Dict[str, Any]], job_id: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    short = job_id.split("-")[-1][:6] or job_id[:6]
    folder = f"{stamp}-{short}"
    if import_target_mode(cfg) == "primary":
        libs = subset_service.library_dirs(cfg)
        base = (Path(libs[0]) / "imported") if libs else imported_root(cfg)
    else:
        base = imported_root(cfg)
    return base / folder


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
           policy: str = "keep") -> Dict[str, Any]:
    """把报告里选中的字体落库。

    :param select: 要入库的文件名（对应 report 里的 name）；None=全部 new
    :param policy: 冲突处理 keep（保留库内，默认）/ replace（备份旧文件后替换）/ skip
    """
    paths = find_job(cfg, job_id)
    if not paths:
        return {"success": False, "message": "导入任务不存在或已过期"}
    report = _read_json(paths["report"])
    if not report:
        return {"success": False, "message": "还没有分析报告，请先执行分析"}
    policy = str(policy or "keep").lower()
    if policy not in ("keep", "replace", "skip"):
        policy = "keep"

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
            skipped.append({"name": name, "reason": "源文件不存在或路径非法"})
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
        "skipped": skipped,
        "replaced_backup": str(replaced_dir) if backed_up else "",
        "message": f"入库 {len(committed)} 个字体"
                   + (f"，跳过 {len(skipped)} 个" if skipped else ""),
    }
    # 一个都没入库（全是冲突/失败）时保留 extracted，方便换策略重试；
    # 真入库了才清理，避免把还没搬走的字体删掉。
    if committed:
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
                    hours: int = JOB_TTL_HOURS) -> int:
    """清理过期的导入工作区（默认 24 小时）。"""
    root = import_root(cfg)
    cutoff = datetime.now() - timedelta(hours=max(1, int(hours)))
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
    try:
        result = await index_store.build_index(
            binary, libs, index_store.index_dir(cfg),
            threads=int(fm.get("internal_threads") or 0),
            verbose=int(fm.get("verbose_level", 3) or 3))
    except Exception as e:      # 对外不抛
        result = {"success": False, "message": f"索引重建异常：{type(e).__name__} {e}"}
    await _notify(on_state, "done" if result.get("success") else "failed", result)
    return result


async def rebuild_now(cfg: Optional[Dict[str, Any]], binary: Path,
                      on_state=None) -> Dict[str, Any]:
    """立刻重建索引（跳过 debounce；测试与「立即刷新」按钮用）。"""
    return await _do_rebuild(cfg, binary, on_state)
