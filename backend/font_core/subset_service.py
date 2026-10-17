"""随行字幕子集化的复用服务（整理任务 × 字体管家共用）。

为什么要单独抽一层：

1. **口径唯一**：字体管家页面与整理任务必须用同一套「内核 / 字体库 / 索引 / 缺字体」
   判定，否则会出现「页面说字体齐全、整理却回退了」这种自相矛盾。
2. **批量场景要省**：整理任务是无人值守的批量流程，不能每个视频都重新读一遍
   650KB 的 fonts.json，所以索引读取带 mtime 缓存。
3. **成败只能看产物**：assfonts 退出码恒为 0（见 runner.py 顶部说明），
   缺字体时也是 0 且无产物，这里统一按产物 + 日志判定。

对外接口：
    ctx = await resolve_context(cfg)          # 内核 + 索引 + 已知字体名
    await precheck_files(paths, ctx)          # 只读预检（预览模式用）
    await subset_files(paths, work_dir=..., ctx=ctx)   # 真跑内核
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set

from font_core import ass_parser, index_store, runner
from font_core import binary as af_binary

logger = logging.getLogger(__name__)

SUBTITLE_EXTS = (".ass", ".ssa")
DEFAULT_TIMEOUT = 300

# 同时跑几个 assfonts 进程：整理任务本身是串行处理视频的，这里再兜一层，
# 避免多个任务并发时把 NAS 的 CPU 打满。
_CONCURRENCY = 2
_SEMAPHORE = asyncio.Semaphore(_CONCURRENCY)

# [WARN] Missing codepoints for "字体名" (400,0): 0x8bd5  0x6d4b
_CODEPOINT_RE = re.compile(
    r'missing codepoints for\s*"?([^"\n:]+?)"?\s*(?:\([^)]*\))?\s*:\s*(.+)$', re.I
)

# fonts.json 的读取缓存：{key: (路径, mtime_ns, size), info: {...}}
_index_cache: Dict[str, Any] = {"key": None, "info": None}


# ── 字体来源（与字体管家同一套配置口径） ─────────────────────

def _fm(cfg: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    return (cfg or {}).get("font_manager", {}) or {}


def library_dirs(cfg: Optional[Dict[str, Any]]) -> List[str]:
    """字体库目录列表（主库 + 额外库），去空去重。"""
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


def temp_font_dir(cfg: Optional[Dict[str, Any]]) -> Path:
    return Path(str(_fm(cfg).get("temp_font_dir") or "data/fonts/temp_fonts"))


def temp_index_dir(cfg: Optional[Dict[str, Any]]) -> Path:
    return temp_font_dir(cfg).parent / "temp_index"


def list_temp_fonts(cfg: Optional[Dict[str, Any]]) -> List[Path]:
    d = temp_font_dir(cfg)
    out: List[Path] = []
    try:
        for e in os.scandir(d):
            if e.is_file() and ass_parser.is_font_file(e.name):
                out.append(Path(e.path))
    except OSError:
        pass
    return out


def extra_font_dirs(cfg: Optional[Dict[str, Any]], extra_font: str = "") -> List[str]:
    """实际下发的 -f 目录：配置的额外字体目录 + 临时字体池（池里有字体时才带）。"""
    dirs = [extra_font] if str(extra_font or "").strip() else []
    if list_temp_fonts(cfg):
        pool = str(temp_font_dir(cfg))
        if pool not in dirs:
            dirs.append(pool)
    return dirs


def merged_known_fonts(faces: Any, cfg: Optional[Dict[str, Any]]) -> Set[str]:
    """主库索引 + 临时字体索引的字体名合集（缺字体判定要算上临时字体）。"""
    names = index_store.font_name_set(faces or [])
    try:
        tinfo = index_store.read_index(temp_index_dir(cfg))
        names |= index_store.font_name_set(tinfo.get("fonts") or [])
    except Exception:
        pass
    return names


def read_index_cached(cfg: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """带 mtime 缓存的索引读取（批量整理时每个视频都会问一次）。"""
    path = index_store.index_file(cfg)
    try:
        st = os.stat(path)
        key = (str(path), st.st_mtime_ns, st.st_size)
    except OSError:
        key = (str(path), None, None)
    if _index_cache.get("info") is not None and _index_cache.get("key") == key:
        return _index_cache["info"]
    info = index_store.read_index(None, cfg)
    _index_cache["key"], _index_cache["info"] = key, info
    return info


def invalidate_index_cache() -> None:
    _index_cache["key"], _index_cache["info"] = None, None


# ── 上下文 ───────────────────────────────────────────────────

@dataclass
class SubsetContext:
    binary: Optional[Path] = None
    db_dir: Optional[Path] = None
    known: Set[str] = field(default_factory=set)
    extra_font_dirs: List[str] = field(default_factory=list)
    error: str = ""

    @property
    def ok(self) -> bool:
        return bool(self.binary and self.db_dir and self.known)


async def resolve_context(cfg: Optional[Dict[str, Any]] = None) -> SubsetContext:
    """解析「内核 + 索引目录 + 已知字体名」。

    索引不存在时会自动建一次（与字体管家页面行为一致），失败则返回带 error 的上下文，
    调用方据此整体回退到「原字幕照常搬」，绝不阻断整理任务。
    """
    if cfg is None:
        from config_manager import ConfigManager
        cfg = ConfigManager.get_config()

    ctx = SubsetContext()

    binary, _source = af_binary.resolve_binary(cfg)
    if not binary:
        ctx.error = "未找到 assfonts 内核，请到字体管家检查或一键更新"
        return ctx
    ctx.binary = binary

    libs = library_dirs(cfg)
    if not libs:
        ctx.error = "尚未在字体管家选择字体库目录"
        return ctx
    bad = [d for d in libs if not Path(d).is_dir()]
    if bad:
        ctx.error = f"字体库目录不可用：{bad[0]}"
        return ctx

    # 索引读取/字体名归一化都是纯 CPU 活：3.8 万 face 时读一次 300~400ms、
    # 归一化一次 100ms，放在事件循环里会让「整理字幕」把整个后端一起卡住。
    info = await asyncio.to_thread(read_index_cached, cfg)
    if not (info.get("exists") and info.get("count")):
        info = await index_store.ensure_index(binary, cfg, libs)
        invalidate_index_cache()
        info = (await asyncio.to_thread(read_index_cached, cfg)) if info.get("exists") else info
        if not (info.get("exists") and info.get("count")):
            ctx.error = info.get("error") or "字体索引不可用，请到字体管家重建索引"
            return ctx

    ctx.db_dir = Path(str(info.get("path") or "")).parent
    ctx.known = await asyncio.to_thread(merged_known_fonts, info.get("fonts") or [], cfg)
    if not ctx.known:
        ctx.error = "字体索引里没有可用字体，请到字体管家重建索引"
        return ctx
    ctx.extra_font_dirs = extra_font_dirs(cfg)
    return ctx


# ── 单文件判定 ───────────────────────────────────────────────

def _base_result() -> Dict[str, Any]:
    return {
        "status": "failed", "output": "", "missing": [], "warnings": [],
        "fonts": [], "duration_ms": 0, "log": "", "reason": "",
    }


async def _classify(src: Path, ctx: SubsetContext) -> tuple[Dict[str, Any], bool]:
    """只读判定：返回 (结果, 是否需要跑内核)。

    - 非 .ass/.ssa → skipped
    - 已内嵌字体   → skipped（再嵌一次只会让体积翻倍）
    - 缺字体       → missing（不启内核，快且不在临时目录留垃圾）
    - 其余         → 需要跑内核
    """
    res = _base_result()
    if not src.is_file():
        res.update(status="failed", reason="字幕文件不存在")
        return res, False
    if src.suffix.lower() not in SUBTITLE_EXTS:
        res.update(status="skipped", reason="非 ASS/SSA 字幕，跳过子集化")
        return res, False
    try:
        raw = await asyncio.to_thread(src.read_bytes)
    except OSError as e:
        res.update(status="failed", reason=f"读取字幕失败：{e}")
        return res, False

    summary = ass_parser.inspect_ass(raw)
    fonts = list(summary.get("fonts") or [])
    res["fonts"] = fonts
    if summary.get("has_embedded_fonts"):
        res.update(status="skipped", reason="字幕已内嵌字体，跳过")
        return res, False
    missing = runner.missing_by_index(fonts, ctx.known)
    if missing:
        res.update(status="missing", missing=missing,
                   reason="缺失字体：" + "、".join(missing))
        return res, False
    return res, True


async def precheck_files(paths: Iterable[str], ctx: SubsetContext) -> Dict[str, Dict[str, Any]]:
    """只读预检（预览模式）：不产生任何文件，也不启动内核。"""
    out: Dict[str, Dict[str, Any]] = {}
    for p in paths:
        src = Path(p).resolve()
        res, need = await _classify(src, ctx)
        if need:
            res["status"] = "planned"
        out[str(src)] = res
    return out


# ── 执行 ─────────────────────────────────────────────────────

def _parse_codepoint_warnings(log: str) -> List[str]:
    """把 `Missing codepoints` 抽成可读告警（缺字形不是失败，成品仍然可用）。"""
    out: List[str] = []
    for line in (log or "").splitlines():
        m = _CODEPOINT_RE.search(line.strip())
        if m:
            out.append(f"{m.group(1).strip()} 缺少字形：{m.group(2).strip()}")
    return out


def _finalize(src: Path, copy: Path, work: Path, raw: Dict[str, Any],
              fonts: Optional[List[str]] = None) -> Dict[str, Any]:
    """把内核产物改名成「原字幕名」并整理成统一结果。

    产物必须叫原名：processor 侧用「相关文件名」做键（related_outcomes /
    related_targets），基名一变状态就串了；交付名里的 .assfonts 标记由 processor
    在目标路径上另行插入。
    """
    res = _base_result()
    res["fonts"] = list(fonts or [])
    res["duration_ms"] = int(raw.get("duration_ms") or 0)
    res["log"] = (raw.get("log") or "")[-4000:]
    res["warnings"] = _parse_codepoint_warnings(res["log"])

    if raw.get("status") != "success":
        res.update(status=raw.get("status") or "failed",
                   missing=list(raw.get("missing") or []),
                   reason=raw.get("error") or "子集化失败")
        return res

    out = Path(str(raw.get("output") or ""))
    if not out.is_file():
        res.update(status="failed", reason="内核未产出成品字幕")
        return res

    target = work / src.name
    try:
        if target.exists():
            target.unlink()
        shutil.move(str(out), str(target))
    except OSError as e:
        res.update(status="failed", reason=f"成品改名失败：{e}")
        return res

    res.update(status="success", output=str(target), reason="")
    return res


async def _run_single(copy: Path, src: Path, work: Path, ctx: SubsetContext,
                      fonts: List[str], timeout: int) -> Dict[str, Any]:
    async with _SEMAPHORE:
        raw = await runner.run_convert(
            ctx.binary, copy, ctx.db_dir,
            mode=runner.MODE_DEFAULT,
            extra_font_dirs=ctx.extra_font_dirs,
            output_dir=str(work),
            keep_subset_dir=False,
            known_fonts=ctx.known,
            referenced_fonts=fonts,
            timeout=timeout,
        )
    return _finalize(src, copy, work, raw, fonts)


async def _run_combined(sources: List[Path], copies: Dict[str, Path], work: Path,
                        ctx: SubsetContext, fonts_map: Dict[str, List[str]],
                        timeout: int) -> Optional[Dict[str, Dict[str, Any]]]:
    """合并子集化（-c 两阶段）：多个字幕共享一份子集字体，避免各带一份。

    实测 `-c` 只产出共享字体夹、不产出 .ass，runner.run_combined 已封装成两阶段。
    返回 None 表示整批不可用（调用方会退化为逐个处理）。
    """
    paths = [copies[str(s)] for s in sources]
    referenced = {str(p.resolve()): fonts_map.get(str(s), []) for s, p in zip(sources, paths)}
    async with _SEMAPHORE:
        combined = await runner.run_combined(
            ctx.binary, paths, ctx.db_dir,
            extra_font_dirs=ctx.extra_font_dirs,
            output_dir=str(work),
            keep_subset_dir=False,
            known_fonts=ctx.known,
            referenced_map=referenced,
            timeout=timeout,
        )
    results = combined.get("results") or []
    if not results:
        logger.info(f"[字幕子集化] 合并模式不可用（{combined.get('error') or '无产物'}），退化为逐个处理")
        return None

    by_path = {str(r.get("path") or ""): r for r in results}
    out: Dict[str, Dict[str, Any]] = {}
    for src, copy in zip(sources, paths):
        raw = by_path.get(str(copy.resolve())) or {
            "status": "failed",
            "error": combined.get("error") or "合并子集化失败",
            "log": combined.get("log") or "",
            "duration_ms": combined.get("duration_ms") or 0,
        }
        out[str(src)] = _finalize(src, copy, work, raw, fonts_map.get(str(src)))
    return out


async def subset_files(paths: Iterable[str], *, work_dir: str, ctx: SubsetContext,
                       timeout: int = DEFAULT_TIMEOUT) -> Dict[str, Dict[str, Any]]:
    """批量把字幕子集化到 work_dir，成品改回原文件名。

    :return: {源字幕绝对路径: {status, output, missing, warnings, fonts, duration_ms, reason}}
             status: success / skipped / missing / failed
    """
    results: Dict[str, Dict[str, Any]] = {}
    prepared: List[Path] = []
    copies: Dict[str, Path] = {}
    work = Path(work_dir)

    for p in paths:
        src = Path(p).resolve()
        res, need = await _classify(src, ctx)
        results[str(src)] = res
        if not need:
            continue
        try:
            work.mkdir(parents=True, exist_ok=True)
            copy = work / src.name
            await asyncio.to_thread(shutil.copy2, src, copy)
        except OSError as e:
            res.update(status="failed", reason=f"临时副本创建失败：{e}")
            continue
        copies[str(src)] = copy
        prepared.append(src)

    if not prepared:
        return results

    fonts_map = {str(s): (results[str(s)].get("fonts") or []) for s in prepared}

    if len(prepared) >= 2:
        combined = await _run_combined(prepared, copies, work, ctx, fonts_map, timeout)
        if combined:
            results.update(combined)
            return results

    for src in prepared:
        results[str(src)] = await _run_single(
            copies[str(src)], src, work, ctx, fonts_map[str(src)], timeout
        )
    return results


async def subset_subtitle(src: str, *, work_dir: str, ctx: SubsetContext,
                          timeout: int = DEFAULT_TIMEOUT) -> Dict[str, Any]:
    """单文件便捷入口。"""
    res = await subset_files([src], work_dir=work_dir, ctx=ctx, timeout=timeout)
    return res.get(str(Path(src).resolve()), _base_result())


# ── 状态摘要（供前端/日志展示） ──────────────────────────────

def summarize(results: Dict[str, Dict[str, Any]]) -> Dict[str, int]:
    out = {"success": 0, "skipped": 0, "missing": 0, "failed": 0}
    for r in (results or {}).values():
        key = r.get("status") or "failed"
        out[key] = out.get(key, 0) + 1
    return out
