"""字体比对 —— 用 assfonts 自己的索引口径判断「库里有没有」。

为什么这么做：
1. **口径唯一**：库里显示的字体、内核子集化时找的字体、这里判重用的字体，
   三者必须来自同一份 `fonts.json`，否则会出现「页面说有、内核说缺」。
2. **不引第三方依赖**：fontTools 能给的 family/psname/weight/slant，assfonts
   索引里全都有；`.ttc` 的多 face 也由内核自己展开（face_index），不用手写
   numFonts 循环。
3. **顺手筛坏文件**：内核解析不出来的字体不会出现在探测索引里 → 直接判
   invalid，比事后子集化失败再排查省事。

三级判据（便宜→贵）：
    L1 逐字节（同名 + 同大小 + 同 sha256）  → 完全重复，零误判
    L2 face 强键 (family, psname) + weight/slant → 同 face 同版本，只是换了文件名
    L3 face 弱键 (family) + weight/slant    → 同 face 不同版本 → 报「冲突」，
                                             默认保留库内已有，由用户在页面上决定

对外接口：
    faces = await probe_directory(binary, font_dir, probe_dir)   # 建临时索引并读回
    report = compare(incoming, faces, library_faces)              # 三级判定
    lib = library_faces(cfg)                                      # 主库 face 快照
"""
from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from font_core import index_store, runner

logger = logging.getLogger(__name__)

_HASH_CACHE: Dict[Tuple[str, int, int], str] = {}
_HASH_CACHE_MAX = 4096


# ── face 归一化 ──────────────────────────────────────────────

def _key(name: str) -> str:
    return runner.normalize_font_key(str(name or ""))


def face_identity(face: Dict[str, Any]) -> Dict[str, Any]:
    """把索引里的一个 face 压成可比较的身份。

    强键 = (family 归一化, psname 归一化)：psname 通常带版本号（如
    SourceHanSansSC-Medium / ...Medium-Build1.005），所以它能区分「同名不同版本」。
    """
    families = [str(x) for x in (face.get("families") or []) if str(x).strip()]
    psnames = [str(x) for x in (face.get("psnames") or []) if str(x).strip()]
    if not families and face.get("family"):
        families = [str(face["family"])]
    if not psnames and face.get("psname"):
        psnames = [str(face["psname"])]
    family_keys = tuple(sorted({_key(x) for x in families if _key(x)}))
    psname_keys = tuple(sorted({_key(x) for x in psnames if _key(x)}))
    return {
        "families": families,
        "psnames": psnames,
        "family": families[0] if families else "",
        "psname": psnames[0] if psnames else "",
        "family_keys": family_keys,
        "psname_keys": psname_keys,
        "weight": face.get("weight"),
        "slant": face.get("slant"),
        "path": str(face.get("path") or ""),
        "filename": str(face.get("filename") or (Path(str(face.get("path") or "")).name)),
        "face_index": face.get("face_index", face.get("index", 0)),
        "format": str(face.get("format") or ""),
    }


def face_summary(face: Dict[str, Any]) -> Dict[str, Any]:
    """给报告/UI 用的精简 face 描述。"""
    ident = face_identity(face)
    return {
        "family": ident["family"],
        "psname": ident["psname"],
        "weight": ident["weight"],
        "slant": ident["slant"],
        "face_index": ident["face_index"],
    }


def _face_keys(ident: Dict[str, Any]) -> Tuple[Tuple[Any, ...], Tuple[Any, ...]]:
    """判定用的两把键。

    强键 = (family, psname, weight, slant)：同 family、同 psname、同字重 → 同一张 face。
    弱键 = (family, weight, slant)：同 family、同字重但 psname 不同 → 「同 face 不同版本」，
           这才是真的冲突（比如 Build 1.005 vs 1.006）。**字重必须进键**，否则
           .ttc 里的 Regular 与 Bold 会被误判成「同一 face 的另一个版本」。
    """
    weight = ident.get("weight")
    slant = ident.get("slant")
    strong = tuple((f, p, weight, slant)
                   for f in ident["family_keys"] for p in ident["psname_keys"])
    weak = tuple((f, weight, slant) for f in ident["family_keys"])
    return strong, weak


# ── 主库快照 ────────────────────────────────────────────────

def library_faces(cfg: Optional[Dict[str, Any]] = None,
                  library_dirs: Optional[Iterable[str]] = None) -> Dict[str, Any]:
    """主库 face 快照：{exists, faces, files, built_at, error}。

    只保留落在字体库目录内的 face（assfonts 建索引时会连系统字体一起扫）。
    """
    info = index_store.read_index(None, cfg)
    dirs = [str(d) for d in (library_dirs or []) if str(d or "").strip()]
    faces = [f for f in (info.get("fonts") or [])
             if index_store.under_library(f.get("path", ""), dirs)]
    return {
        "exists": bool(info.get("exists")),
        "faces": faces,
        "files": len({f.get("path") for f in faces if f.get("path")}),
        "built_at": info.get("built_at", ""),
        "error": info.get("error", ""),
        "path": info.get("path", ""),
    }


def _build_library_index(faces: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_name: Dict[str, List[Dict[str, Any]]] = {}
    by_strong: Dict[Tuple[str, str], Dict[str, Any]] = {}
    by_psname: Dict[str, List[Dict[str, Any]]] = {}
    by_weak: Dict[str, List[Dict[str, Any]]] = {}
    for raw in faces:
        ident = face_identity(raw)
        entry = {"ident": ident, "raw": raw}
        if ident["filename"]:
            by_name.setdefault(ident["filename"].lower(), []).append(entry)
        strong, weak = _face_keys(ident)
        for s in strong:
            by_strong.setdefault(s, entry)
        for w in weak:
            by_weak.setdefault(w, []).append(entry)
        for ps in ident["psname_keys"]:
            by_psname.setdefault(ps, []).append(entry)
    return {"by_name": by_name, "by_strong": by_strong,
            "by_psname": by_psname, "by_weak": by_weak}


# ── 内容级（L1）比对 ────────────────────────────────────────

def sha256_file(path: Path) -> str:
    try:
        st = path.stat()
    except OSError:
        return ""
    cache_key = (str(path), st.st_size, int(st.st_mtime))
    hit = _HASH_CACHE.get(cache_key)
    if hit is not None:
        return hit
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
    value = digest.hexdigest()
    if len(_HASH_CACHE) >= _HASH_CACHE_MAX:
        _HASH_CACHE.clear()
    _HASH_CACHE[cache_key] = value
    return value


def _same_content(path: Path, sha256: str, size: int) -> bool:
    """同大小 + 同 sha256 才算重复（先比大小，避免无谓地读 NAS 上的大文件）。"""
    if not sha256:
        return False
    try:
        if path.stat().st_size != size:
            return False
    except OSError:
        return False
    return sha256_file(path) == sha256


# ── 探测（给待入库字体建临时索引）────────────────────────────

async def probe_directory(binary: Path, font_dir: Path, probe_dir: Path, *,
                          threads: int = 0, verbose: Optional[int] = None,
                          timeout: int = 900) -> Dict[str, Any]:
    """给 font_dir 里的字体单独建一份 assfonts 索引并读回 face。

    返回 {"success", "message", "faces": [...], "by_path": {path: [face]},
          "by_name": {filename: [face]}, "count"}。

    约定：不抛异常；内核不可用时 success=False 且 message 说明原因。
    """
    font_dir = Path(font_dir)
    probe_dir = Path(probe_dir)
    out: Dict[str, Any] = {"success": False, "message": "", "faces": [], "by_path": {},
                           "by_name": {}, "count": 0}
    try:
        if not font_dir.is_dir():
            out["message"] = f"待比对目录不存在：{font_dir}"
            return out
        result = await index_store.build_index(
            binary, [str(font_dir)], probe_dir,
            threads=int(threads or 0),
            verbose=3 if verbose is None else int(verbose),
            timeout=timeout)
        if not result.get("success"):
            out["message"] = result.get("message") or "探测索引构建失败"
            return out
        info = index_store.read_index(probe_dir)
        if not info.get("exists"):
            out["message"] = info.get("error") or "探测索引未生成"
            return out
        # 内核扫描会带上系统字体目录，这里必须按目录过滤，否则会「发现」一堆系统字体
        faces = [f for f in (info.get("fonts") or [])
                 if index_store.under_library(f.get("path", ""), [str(font_dir)])]
        by_path: Dict[str, List[Dict[str, Any]]] = {}
        by_name: Dict[str, List[Dict[str, Any]]] = {}
        for face in faces:
            p = str(face.get("path") or "")
            ident = face_identity(face)
            by_path.setdefault(norm_path(p), []).append(face)
            if ident["filename"]:
                by_name.setdefault(ident["filename"].lower(), []).append(face)
        out.update({"success": True, "faces": faces, "by_path": by_path,
                    "by_name": by_name, "count": len(faces),
                    "message": f"探测到 {len(faces)} 个 face"})
        return out
    except Exception as e:      # 对外不抛
        logger.warning(f"[字体导入] 探测索引失败 {font_dir}: {type(e).__name__} {e}")
        out["message"] = f"探测索引异常：{type(e).__name__} {e}"
        return out


def norm_path(path: str) -> str:
    if not path:
        return ""
    try:
        return os.path.normcase(str(Path(path).resolve()))
    except Exception:
        return os.path.normcase(str(path))


# ── 判定 ────────────────────────────────────────────────────

def compare(incoming: List[Dict[str, Any]],
            probe: Dict[str, Any],
            lib: Dict[str, Any]) -> Dict[str, Any]:
    """三级判定：每个待入库文件落到 new / duplicate / conflict / invalid 之一。

    incoming: [{"name", "source", "size", "sha256", "path"}]（path=解压出来的绝对路径）
    probe:    probe_directory() 的返回值
    lib:      library_faces() 的返回值

    注意粒度：**以 face 判定、以文件入库**。一个 .ttc 里 3 个 face 只要有 1 个
    是新的就整文件入库；反过来只要有 face 撞车就进 conflict，绝不静默丢文件。
    """
    lib_index = _build_library_index(lib.get("faces") or [])
    probe_by_path = probe.get("by_path") or {}
    probe_by_name = probe.get("by_name") or {}
    out: Dict[str, List[Dict[str, Any]]] = {"new": [], "duplicate": [],
                                            "conflict": [], "invalid": []}

    for item in incoming:
        name = str(item.get("name") or "")
        src = str(item.get("source") or name)
        size = int(item.get("size") or 0)
        sha = str(item.get("sha256") or "")
        path = str(item.get("path") or "")
        base = {"name": name, "source": src, "size": size}

        faces = probe_by_path.get(norm_path(path)) or probe_by_name.get(name.lower()) or []
        if not faces:
            out["invalid"].append({**base, "reason": "内核无法解析（文件损坏或不是字体）"})
            continue

        # L1：同名 + 同大小 + 同 sha256 → 逐字节重复
        dup = None
        for entry in lib_index["by_name"].get(name.lower(), []):
            lib_path = Path(entry["ident"]["path"]) if entry["ident"]["path"] else None
            if lib_path and _same_content(lib_path, sha, size):
                dup = {"reason": "与字体库中同名文件逐字节相同",
                       "existing": str(lib_path),
                       "existing_family": entry["ident"]["family"]}
                break
        if dup:
            out["duplicate"].append({**base, **dup})
            continue

        # L2/L3：逐 face 对撞
        matched_strong: List[Dict[str, Any]] = []
        conflicts: List[Dict[str, Any]] = []
        new_faces: List[Dict[str, Any]] = []
        for face in faces:
            ident = face_identity(face)
            strong, weak = _face_keys(ident)
            hit = next((lib_index["by_strong"][s] for s in strong
                        if s in lib_index["by_strong"]), None)
            if hit is not None:
                matched_strong.append(hit)
                continue
            # psname 是 OpenType 里的唯一标识：family 命名不同（一个英文名、一个中文名）
            # 但 psname 一致 → 同一字体的不同来源/版本，按「冲突」处理而不是当新字体导进来
            ps_hits = [lib_index["by_psname"][p] for p in ident["psname_keys"]
                       if p in lib_index["by_psname"]]
            if ps_hits:
                flat = {e["ident"]["path"]: e for group in ps_hits for e in group}
                conflicts.append({
                    "face": face_summary(face),
                    "existing": [{"path": p, "family": e["ident"]["family"],
                                  "psname": e["ident"]["psname"]}
                                 for p, e in flat.items()],
                    "reason": "同 PostScript 名（psname）但 family 命名不同：疑似同一字体的不同来源",
                })
                continue
            same_family = [lib_index["by_weak"][w] for w in weak if w in lib_index["by_weak"]]
            if same_family:
                flat = {e["ident"]["path"]: e for group in same_family for e in group}
                conflicts.append({"face": face_summary(face),
                                  "existing": [{"path": p, "family": e["ident"]["family"],
                                                "psname": e["ident"]["psname"]}
                                               for p, e in flat.items()],
                                  "reason": "同 face 不同版本（psname 不一致）"})
                continue
            new_faces.append(face_summary(face))

        if conflicts:
            out["conflict"].append({**base, "faces": [face_summary(f) for f in faces],
                                    "conflicts": conflicts,
                                    "reason": conflicts[0]["reason"]})
        elif new_faces:
            out["new"].append({**base, "faces": [face_summary(f) for f in faces]})
        else:
            first = matched_strong[0]["ident"] if matched_strong else {}
            out["duplicate"].append({
                **base,
                "reason": "face 完全命中字体库（同 family + 同 psname）",
                "existing": first.get("path", ""),
                "existing_family": first.get("family", ""),
            })

    counts = {k: len(v) for k, v in out.items()}
    return {
        **out,
        "counts": counts,
        "compared_faces": len(lib.get("faces") or []),
        "library_index_available": bool(lib.get("exists")),
        "library_index_error": lib.get("error", ""),
    }
