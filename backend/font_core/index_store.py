"""assfonts 字体索引（fonts.json）的构建与读取。

索引是「检查」与「子集化」的公共口径：assfonts 用它把字幕里引用的字体名
映射到字体库里的实际字体文件。

索引文件结构（assfonts v0.7.3 输出，顶层为扁平数组，每个元素是一个 face）：
    [{"families": [...], "fullnames": [...], "psnames": [...],
      "weight": 400, "slant": 0, "path": "/fonts/xxx.ttf", "index": 0,
      "last_write_time": "UTC ..."}, ...]
为兼容不同版本，读取侧同时支持「顶层 dict：字体路径 -> face 数组」的旧结构。
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

INDEX_FILENAME = "fonts.json"
_ERROR_RE = re.compile(r"\[error\]", re.I)


def index_dir(config: Optional[Dict[str, Any]] = None) -> Path:
    cfg = (config or {}).get("font_manager", {}) if config else {}
    return Path(str(cfg.get("index_dir") or "data/fonts/index"))


def index_file(config: Optional[Dict[str, Any]] = None) -> Path:
    return index_dir(config) / INDEX_FILENAME


# ── 构建 ─────────────────────────────────────────────────────

async def build_index(binary: Path, library_dirs: Any, db_dir: Path, *,
                      threads: int = 0, verbose: Optional[int] = None,
                      timeout: int = 1800) -> Dict[str, Any]:
    """执行 `assfonts -b -f <dir> [-f <dir> ...] -d <db_dir>` 重建索引。

    支持多个字体库目录：实测 assfonts 的 -f 可重复且会叠加（单 -f 55 个 face、
    双 -f 56 个）。目录一律转成绝对路径 —— 索引里记录的是字体文件的绝对路径，
    若用相对路径建索引，后续在别的 cwd 下子集化会报 `is inaccessible`。
    """
    result: Dict[str, Any] = {"success": False, "message": "", "log": "", "count": 0}
    dirs = [d for d in (library_dirs if isinstance(library_dirs, (list, tuple)) else [library_dirs])]
    libs: List[Path] = []
    for d in dirs:
        d = str(d or "").strip()
        if not d:
            continue
        p = Path(os.path.expanduser(d))
        if not p.is_dir():
            result["message"] = f"字体库目录不存在或不是目录：{d}"
            return result
        libs.append(p.resolve())
    if not libs:
        result["message"] = "尚未选择字体库目录"
        return result
    try:
        db_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        result["message"] = f"索引目录不可写：{e}"
        return result

    # 内核路径必须绝对：execve 对不含目录成分的名字按 PATH 查找，
    # 传 "assfonts" 这种相对名会直接 FileNotFoundError。
    cmd = [str(Path(binary).expanduser().resolve()), "-b"]
    for lib in libs:
        cmd += ["-f", str(lib)]
    cmd += ["-d", str(Path(db_dir).expanduser().resolve())]
    # 建索引同样支持 -m/-v：字体库很大时多线程能明显加速（与桌面版行为一致）
    if threads and int(threads) > 0:
        cmd += ["-m", str(int(threads))]
    if verbose is not None and int(verbose) != 3:
        cmd += ["-v", str(int(verbose))]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
        )
    except Exception as e:
        result["message"] = f"无法启动 assfonts：{type(e).__name__} {e}"
        return result

    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except Exception:
            pass
        result["message"] = f"索引构建超时（{timeout}s），字体库过大时可分批放入"
        return result

    text = (out or b"").decode("utf-8", errors="replace")
    result["log"] = text.strip()[-4000:]
    errors = [ln.strip() for ln in text.splitlines() if _ERROR_RE.search(ln)]
    if errors:
        result["message"] = "；".join(errors[:3])
        return result

    fp = db_dir / INDEX_FILENAME
    if not fp.is_file():
        result["message"] = "索引构建未生成 fonts.json（可能被中断或目录不可写）"
        return result
    info = read_index(db_dir)
    result.update({"success": True, "count": info.get("file_count", 0),
                   "message": f"索引构建完成，共 {info.get('file_count', 0)} 个字体文件 / {info.get('count', 0)} 个 face"})
    logger.info(f"[字体管家] {result['message']}（字体库：{', '.join(str(x) for x in libs)}）")
    return result


# ── 读取 ─────────────────────────────────────────────────────

def _as_list(val: Any) -> List[str]:
    if isinstance(val, list):
        return [str(v) for v in val if isinstance(v, str) and v.strip()]
    if isinstance(val, str) and val.strip():
        return [val]
    return []


def _normalize_faces(data: Any) -> List[Dict[str, Any]]:
    faces: List[Dict[str, Any]] = []

    def _push(entry: Dict[str, Any], fallback_path: str = "") -> None:
        families = _as_list(entry.get("families") or entry.get("family_names") or entry.get("family_name"))
        fullnames = _as_list(entry.get("fullnames") or entry.get("full_names") or entry.get("full_name"))
        psnames = _as_list(entry.get("psnames") or entry.get("ps_names") or entry.get("ps_name"))
        name_sub = entry.get("name")
        if isinstance(name_sub, dict):
            families = families or _as_list(name_sub.get("families"))
            fullnames = fullnames or _as_list(name_sub.get("fullnames"))
            psnames = psnames or _as_list(name_sub.get("psnames"))
        path = str(entry.get("path") or fallback_path or "")
        if isinstance(entry.get("source"), dict):
            path = str(entry["source"].get("path") or path)
        if not (families or fullnames or psnames):
            return
        faces.append({
            "family": families[0] if families else (fullnames[0] if fullnames else ""),
            "families": families,
            "fullname": fullnames[0] if fullnames else "",
            "fullnames": fullnames,
            "psname": psnames[0] if psnames else "",
            "psnames": psnames,
            "weight": entry.get("weight"),
            "slant": entry.get("slant"),
            "path": path,
            "filename": Path(path).name if path else "",
            "format": (Path(path).suffix.lstrip(".").lower() if path else ""),
            "face_index": entry.get("index", 0),
            "last_write_time": entry.get("last_write_time", ""),
        })

    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            if isinstance(item.get("faces"), list):
                for face in item["faces"]:
                    if isinstance(face, dict):
                        _push(face, str(item.get("path") or ""))
            else:
                _push(item)
    elif isinstance(data, dict):
        for path_key, val in data.items():
            if isinstance(val, list):
                for face in val:
                    if isinstance(face, dict):
                        _push(face, str(path_key))
            elif isinstance(val, dict):
                if isinstance(val.get("faces"), list):
                    for face in val["faces"]:
                        if isinstance(face, dict):
                            _push(face, str(path_key))
                else:
                    _push(val, str(path_key))
    return faces


def read_index(db_dir: Optional[Path] = None,
               config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """读取索引 → {exists, count(face 数), file_count(文件数), built_at, fonts, error}。"""
    d = Path(db_dir) if db_dir else index_dir(config)
    fp = d / INDEX_FILENAME
    empty = {"exists": False, "count": 0, "file_count": 0, "built_at": "", "size": 0,
             "path": str(fp), "fonts": [], "error": ""}
    if not fp.is_file():
        return empty
    try:
        with open(fp, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        empty["error"] = f"索引文件解析失败：{e}"
        return empty

    faces = _normalize_faces(data)
    try:
        st = fp.stat()
        built_at = datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds")
        size = st.st_size
    except OSError:
        built_at, size = "", 0

    paths = {f["path"] for f in faces if f.get("path")}
    return {
        "exists": True,
        "count": len(faces),
        "file_count": len(paths),
        "built_at": built_at,
        "size": size,
        "path": str(fp),
        "fonts": faces,
        "error": "",
    }


async def ensure_index(binary: Path, config: Optional[Dict[str, Any]],
                       library_dirs: Any) -> Dict[str, Any]:
    """索引不存在时自动构建；已存在则直接返回状态。"""
    info = await asyncio.to_thread(read_index, None, config)
    if info.get("exists") and info.get("count"):
        return info
    fm = (config or {}).get("font_manager", {}) or {}
    built = await build_index(binary, library_dirs, index_dir(config),
                              threads=int(fm.get("internal_threads") or 0),
                              verbose=int(fm.get("verbose_level", 3) or 0))
    if not built.get("success"):
        return {**info, "error": built.get("message", "索引构建失败")}
    return await asyncio.to_thread(read_index, None, config)


# ── 字体库范围过滤 ───────────────────────────────────────────
# assfonts 建索引时会连同系统字体目录（/usr/share/fonts 等）一起扫描，
# 展示侧需按字体库目录过滤，否则「字体库字体数」会把系统字体算进来。

def _dir_list(library_dirs: Any) -> List[str]:
    if not library_dirs:
        return []
    seq = library_dirs if isinstance(library_dirs, (list, tuple)) else [library_dirs]
    return [str(d).strip() for d in seq if str(d or "").strip()]


def under_library(path: str, library_dirs: Any) -> bool:
    """路径是否落在任一字幕/字体库目录内（支持多目录）。"""
    dirs = _dir_list(library_dirs)
    if not dirs:
        return True
    if not path:
        return False
    try:
        p = Path(path).resolve()
    except Exception:
        return any(str(path).startswith(d) for d in dirs)
    for d in dirs:
        try:
            lib = Path(d).resolve()
            if p == lib or lib in p.parents:
                return True
        except Exception:
            if str(path).startswith(d):
                return True
    return False


def library_stats(faces: List[Dict[str, Any]], library_dirs: Any) -> Dict[str, int]:
    """统计字体库目录内的 face 数与文件数（支持多目录）。"""
    inside = [f for f in faces if under_library(f.get("path", ""), library_dirs)]
    return {
        "library_count": len(inside),
        "library_file_count": len({f.get("path") for f in inside if f.get("path")}),
    }


def font_name_set(faces: List[Dict[str, Any]]) -> set:
    """索引里所有可用字体名（families + fullnames + psnames）的归一化集合。

    用途：当 assfonts 的日志被 -v 0/1 静默、拿不到 `Missing the font` 时，
    由我们自己比对字幕引用字体与索引，给出可行动的缺字体清单。
    """
    from font_core.runner import normalize_font_key

    names: set = set()
    for f in faces or []:
        for key in ("families", "fullnames", "psnames"):
            for v in f.get(key) or []:
                k = normalize_font_key(str(v))
                if k:
                    names.add(k)
        for key in ("family", "fullname", "psname"):
            k = normalize_font_key(str(f.get(key) or ""))
            if k:
                names.add(k)
    return names
