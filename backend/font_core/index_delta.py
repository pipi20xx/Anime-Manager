"""主库索引的「增量 face 缓存」（解决连续导入时的索引滞后）。

问题：assfonts 只能整份重建索引（38k face 要几分钟）。连续导入多个字体包时：
- 每个包入库后都全量重建 → 12 个包 = 12 次几分钟的重建，队列被拖死；
- 完全不重建 → 下一个包分析时读到的还是旧索引，刚入库的字体「看不见」，
  会被判成新增 → 同一字体被重复入库（存成 xxx_1.ttf）。

做法：入库后只对**本批新增的那几个字体文件**跑一次小探测（`assfonts -b -f <本批临时目录>`），
把得到的 face 按真实路径记到 `data/fonts/index/.delta_faces.json`；比对时把
「主索引 face + delta face」合并成基线。主索引真正重建完成（debounce 或手动）后 delta 作废清空。

这样：
- 每个包只多花几秒（探测本批几十个字体），不重建全库；
- 下一个包分析时能看见上一个包的字体 → 判 duplicate/conflict，不会重复入库；
- 全库重建仍然走 debounce，一批导入只在最后重建一次。
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from font_core import ass_parser, font_probe, index_store

logger = logging.getLogger(__name__)

DELTA_FILE = ".delta_faces.json"


def delta_path(cfg: Optional[Dict[str, Any]] = None) -> Path:
    return index_store.index_dir(cfg) / DELTA_FILE


# ── 读写 ────────────────────────────────────────────────────

def load(cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """读取 delta：{generation, files: {path: {size, mtime}}, faces: [...], updated}。"""
    empty: Dict[str, Any] = {"generation": "", "files": {}, "faces": [], "updated": ""}
    fp = delta_path(cfg)
    try:
        with open(fp, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return empty
    if not isinstance(data, dict):
        return empty
    # 主索引重建过（built_at 变了）→ delta 已过期，直接丢掉
    try:
        built_at = index_store.read_index(None, cfg).get("built_at", "")
    except Exception:
        built_at = ""
    if data.get("generation") and built_at and data["generation"] != built_at:
        return empty
    data.setdefault("files", {})
    data.setdefault("faces", [])
    return data


def save(cfg: Optional[Dict[str, Any]], data: Dict[str, Any]) -> None:
    fp = delta_path(cfg)
    try:
        fp.parent.mkdir(parents=True, exist_ok=True)
        tmp = fp.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False)
        os.replace(tmp, fp)
    except OSError as e:
        logger.debug(f"[字体索引增量] 落盘失败: {e}")


def clear(cfg: Optional[Dict[str, Any]] = None) -> None:
    """主索引重建完成后调用：delta 里的 face 已经进主索引，清掉。"""
    try:
        delta_path(cfg).unlink(missing_ok=True)
    except OSError:
        pass


def _load_raw(cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """不校验 generation 的原始读取（裁剪时用）。"""
    try:
        with open(delta_path(cfg), "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {"generation": "", "files": {}, "faces": [], "updated": ""}
    if not isinstance(data, dict):
        return {"generation": "", "files": {}, "faces": [], "updated": ""}
    data.setdefault("files", {})
    data.setdefault("faces", [])
    return data


def prune(cfg: Optional[Dict[str, Any]], cutoff_mtime: float) -> None:
    """重建完成后按时间裁剪 delta：只保留「重建开始之后才入库」的条目。

    为什么不能直接 clear：重建要跑几分钟，期间又入库的字体可能没被这次扫描收进去，
    直接清空会让它们既不在索引、也不在 delta → 下一个包分析时看不见 → 重复入库。
    所以把「文件 mtime <= 重建开始时间」的条目删掉（已进索引），更晚的留下继续兜底。
    """
    data = _load_raw(cfg)
    files = data.get("files") or {}
    if not files:
        clear(cfg)
        return
    keep_files: Dict[str, Any] = {}
    for path, info in files.items():
        try:
            mtime = float(info.get("mtime") or 0)
        except (TypeError, ValueError):
            mtime = 0.0
        if mtime > float(cutoff_mtime):
            keep_files[path] = info
    if not keep_files:
        clear(cfg)
        return
    keep_faces = [f for f in (data.get("faces") or []) if str(f.get("path") or "") in keep_files]
    data["files"] = keep_files
    data["faces"] = keep_faces
    data["generation"] = ""
    save(cfg, data)


# ── 合并与新鲜度 ────────────────────────────────────────────

def _valid_faces(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """只保留文件还在、且 size/mtime 没变的 delta face。"""
    files = data.get("files") or {}
    out: List[Dict[str, Any]] = []
    for face in data.get("faces") or []:
        path = str(face.get("path") or "")
        info = files.get(path)
        if not path or not isinstance(info, dict):
            continue
        try:
            st = os.stat(path)
        except OSError:
            continue
        if int(info.get("size") or -1) != int(st.st_size):
            continue
        if int(info.get("mtime") or -1) != int(st.st_mtime):
            continue
        out.append(face)
    return out


def merged_faces(lib_faces: List[Dict[str, Any]],
                 cfg: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """主索引 face + delta face 合并，按 (path, face_index) 去重。

    主索引里已有的路径优先（说明重建已经覆盖到它）。
    """
    data = load(cfg)
    extra = _valid_faces(data)
    if not extra:
        return lib_faces
    seen = {(str(f.get("path") or ""), int(f.get("face_index") or 0)) for f in lib_faces}
    merged = list(lib_faces)
    for face in extra:
        key = (str(face.get("path") or ""), int(face.get("face_index") or 0))
        if key in seen:
            continue
        seen.add(key)
        merged.append(face)
    return merged


def covers(cfg: Optional[Dict[str, Any]], newest_mtime: float) -> bool:
    """delta 是否已经覆盖到「库内最新文件」这个时间点。

    用途：判断「索引看起来过期」到底是"我们刚导入还没重建"（delta 已覆盖，正常）
    还是"别的原因导致过期"（需要先重建）。
    """
    if not newest_mtime:
        return False
    data = load(cfg)
    for info in (data.get("files") or {}).values():
        try:
            if float(info.get("mtime") or 0) >= float(newest_mtime) - 1:
                return True
        except (TypeError, ValueError):
            continue
    return False


# ── 入库后刷新 ──────────────────────────────────────────────

async def refresh(cfg: Optional[Dict[str, Any]], binary: Path,
                  file_paths: List[Path], *, threads: int = 0,
                  verbose: Optional[int] = None) -> Dict[str, Any]:
    """把刚入库的字体文件探测一遍，face 追加进 delta。

    只探测「新增/变化」的文件：把它们硬链（跨盘退回复制）到一个临时目录，
    用 assfonts 建一个迷你索引，再把 face 的 path 改回真实路径。
    """
    out: Dict[str, Any] = {"added": 0, "faces": 0, "skipped": 0, "error": ""}
    if not file_paths:
        return out
    if not Path(str(binary)).is_file():
        out["error"] = "assfonts 内核不可用，跳过增量探测"
        return out

    data = load(cfg)
    if not data.get("generation"):
        try:
            data["generation"] = index_store.read_index(None, cfg).get("built_at", "")
        except Exception:
            data["generation"] = ""

    candidates: List[Path] = []
    for path in file_paths:
        path = Path(path)
        if not path.is_file() or not ass_parser.is_font_file(path.name):
            continue
        try:
            st = path.stat()
        except OSError:
            continue
        known = (data.get("files") or {}).get(str(path))
        if known and int(known.get("size") or -1) == int(st.st_size) \
                and int(known.get("mtime") or -1) == int(st.st_mtime):
            out["skipped"] += 1
            continue
        candidates.append(path)

    if not candidates:
        return out

    staging = delta_path(cfg).parent / ".delta_probe"
    try:
        import shutil
        shutil.rmtree(staging, ignore_errors=True)
        staging.mkdir(parents=True, exist_ok=True)
        mapping: Dict[str, Path] = {}
        for idx, src in enumerate(candidates):
            alias = f"f{idx}_{src.name}"          # 加前缀避免同名互撞
            alias_path = staging / alias
            try:
                os.link(src, alias_path)
            except OSError:
                shutil.copy2(str(src), str(alias_path))
            mapping[alias] = src

        probe = await font_probe.probe_directory(binary, staging, staging / "_index",
                                                 threads=threads, verbose=verbose)
        if not probe.get("success"):
            out["error"] = probe.get("message") or "增量探测失败"
            return out

        added_faces = 0
        for face in probe.get("faces") or []:
            alias = Path(str(face.get("path") or "")).name
            real = mapping.get(alias)
            if real is None:
                continue
            face = dict(face)
            face["path"] = str(real)
            face["filename"] = real.name
            data.setdefault("faces", []).append(face)
            added_faces += 1
        for real in candidates:
            try:
                st = real.stat()
            except OSError:
                continue
            data.setdefault("files", {})[str(real)] = {"size": int(st.st_size),
                                                       "mtime": int(st.st_mtime)}
        data["updated"] = datetime.now().isoformat(timespec="seconds")
        save(cfg, data)
        out.update({"added": len(candidates), "faces": added_faces})
        logger.info(f"[字体索引增量] {len(candidates)} 个新字体 / {added_faces} 个 face 已并入比对基线")
        return out
    except Exception as e:
        out["error"] = f"增量探测异常：{type(e).__name__} {e}"
        logger.warning(f"[字体索引增量] {out['error']}")
        return out
    finally:
        try:
            import shutil
            shutil.rmtree(staging, ignore_errors=True)
        except Exception:
            pass
