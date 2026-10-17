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
import shutil
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

_BUILDING: set = set()


def _low_priority(cmd: List[str]) -> List[str]:
    """用 nice 降低内核子进程优先级，让 Web API / 调度器仍抢得到 CPU。

    索引构建会把所有核跑满（3.8 万字体要几分钟）。默认优先级下 Python 进程
    抢不过它，表现就是「重建索引时整个项目像卡死」。POSIX 上套一层 nice；
    没有 nice 或非 POSIX 平台原样返回（不影响功能，只是没那么丝滑）。
    """
    if os.name != "posix":
        return cmd
    try:
        nice = shutil.which("nice")
        level = int(str(os.environ.get("ASSFONTS_NICE") or "10"))
    except Exception:
        return cmd
    if not nice:
        return cmd
    return [nice, "-n", str(max(0, min(19, level))), *cmd]


async def build_index(binary: Path, library_dirs: Any, db_dir: Path, *,
                      threads: int = 0, verbose: Optional[int] = None,
                      timeout: int = 1800) -> Dict[str, Any]:
    """执行 `assfonts -b -f <dir> [-f <dir> ...] -d <db_dir>` 重建索引。

    支持多个字体库目录：实测 assfonts 的 -f 可重复且会叠加（单 -f 55 个 face、
    双 -f 56 个）。目录一律转成绝对路径 —— 索引里记录的是字体文件的绝对路径，
    若用相对路径建索引，后续在别的 cwd 下子集化会报 `is inaccessible`。

    可用性约束（很重要，别退化）：
    - 子进程降优先级执行，否则全核扫描会把事件循环饿死，整个项目跟着卡；
    - 同一索引目录同时只允许一个构建：手动「重建索引」与「上传后自动重建」
      撞在一起会起两个全核进程，整机更像死机；
    - 收尾解析 fonts.json 走线程（3.8 万 face 解析一次几百毫秒）。
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

    try:
        build_key = str(Path(db_dir).expanduser().resolve())
    except Exception:
        build_key = str(db_dir)
    if build_key in _BUILDING:
        result["message"] = "已有索引构建任务正在进行，请等它完成后再试"
        return result
    _BUILDING.add(build_key)
    proc: Optional[asyncio.subprocess.Process] = None
    try:
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
                *_low_priority(cmd), stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
        except Exception as e:
            result["message"] = f"无法启动 assfonts：{type(e).__name__} {e}"
            return result

        try:
            out, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            try:
                proc.kill()
                await proc.wait()
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
        info = await asyncio.to_thread(read_index, db_dir)
        result.update({"success": True, "count": info.get("file_count", 0),
                       "message": f"索引构建完成，共 {info.get('file_count', 0)} 个字体文件 / {info.get('count', 0)} 个 face"})
        logger.info(f"[字体管家] {result['message']}（字体库：{', '.join(str(x) for x in libs)}）")
        return result
    finally:
        # 先释放构建标记：即便下面回收子进程时又被取消，也不会把标记永久占住，
        # 否则之后每次重建都会提示「已有索引构建任务正在进行」。
        _BUILDING.discard(build_key)
        # 请求被取消（浏览器关页 / 反代超时 / 服务重启）时 asyncio 不会替我们收子进程，
        # 遗留的全核扫描进程会一直抢 CPU —— 那才是"整个项目像卡死"的真凶之一。
        if proc is not None and proc.returncode is None:
            try:
                proc.kill()
            except Exception:
                pass
            try:
                await proc.wait()
            except Exception:
                pass


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


_READ_CACHE: Dict[str, Tuple[Any, Dict[str, Any]]] = {}
_READ_CACHE_MAX = 8


def read_index(db_dir: Optional[Path] = None,
               config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """读取索引 → {exists, count(face 数), file_count(文件数), built_at, fonts, error}。

    带 mtime/size 缓存：字体管家页面在有任务跑时每 1.5s 轮询一次 /status，
    3.8 万 face 的 fonts.json 解析一次要 300~400ms，不缓存的话光是轮询就能把
    一个核吃满。返回的顶层 dict 与 fonts 列表每次都是新对象（face 字典共享，
    调用方只读，不要原地修改）。
    """
    d = Path(db_dir) if db_dir else index_dir(config)
    fp = d / INDEX_FILENAME
    empty = {"exists": False, "count": 0, "file_count": 0, "built_at": "", "size": 0,
             "path": str(fp), "fonts": [], "error": ""}
    try:
        st = fp.stat()
    except OSError:
        return empty
    if not fp.is_file():
        return empty

    key = (str(fp), st.st_mtime_ns, st.st_size)
    hit = _READ_CACHE.get(str(fp))
    if hit is not None and hit[0] == key:
        cached = hit[1]
        return {**cached, "fonts": list(cached.get("fonts") or [])}

    try:
        with open(fp, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        empty["error"] = f"索引文件解析失败：{e}"
        return empty

    faces = _normalize_faces(data)
    paths = {f["path"] for f in faces if f.get("path")}
    info = {
        "exists": True,
        "count": len(faces),
        "file_count": len(paths),
        "built_at": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
        "size": st.st_size,
        "path": str(fp),
        "fonts": faces,
        "error": "",
    }
    if len(_READ_CACHE) >= _READ_CACHE_MAX:
        _READ_CACHE.clear()
    _READ_CACHE[str(fp)] = (key, info)
    return {**info, "fonts": list(faces)}


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


_DIR_VARIANTS: Dict[Tuple[str, ...], Tuple[str, ...]] = {}


def _dir_variants(dirs: List[str]) -> Tuple[str, ...]:
    """字体库目录的规范化前缀（配置原样 + realpath），按目录列表缓存。

    旧实现对每个 face 都做一次 Path(path).resolve()（一次 realpath 系统调用）：
    3.8 万 face 时单次 /status 就要 1s+，事件循环直接被堵死（连带 APScheduler
    报 "Run time of job ... was missed"）。现在目录只解析一次，逐 face 只做
    字符串前缀比较，同样的遍历降到几十毫秒。
    """
    key = tuple(dirs)
    hit = _DIR_VARIANTS.get(key)
    if hit is not None:
        return hit
    out: List[str] = []
    seen = set()
    for d in dirs:
        try:
            forms = [os.path.normpath(d), os.path.realpath(d)]
        except Exception:
            forms = [str(d)]
        for form in forms:
            form = str(form or "").rstrip("/\\")
            if form and form not in seen:
                seen.add(form)
                out.append(form)
    if len(_DIR_VARIANTS) > 32:
        _DIR_VARIANTS.clear()
    _DIR_VARIANTS[key] = tuple(out)
    return _DIR_VARIANTS[key]


def under_library(path: str, library_dirs: Any) -> bool:
    """路径是否落在任一字幕/字体库目录内（支持多目录）。

    纯词法比较（不逐文件 realpath）：索引里的 path 是 assfonts 扫描时写下的
    绝对路径，目录侧同时接受「配置原样」与「realpath」两种写法，软链接场景
    依然判定正确。
    """
    dirs = _dir_list(library_dirs)
    if not dirs:
        return True
    if not path:
        return False
    try:
        p = os.path.normpath(str(path))
    except Exception:
        p = str(path)
    for d in _dir_variants(dirs):
        if p == d or p.startswith(d + "/") or p.startswith(d + "\\"):
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
