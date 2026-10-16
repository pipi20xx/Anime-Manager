"""调用 assfonts 完成字幕字体的子集化 / 内嵌 / 清理 / 合并。

assfonts 的命令行参数（v0.7.3，选项名可混用长短形式）：
    -i/--input <files>      输入字幕（可一次多个）
    -d/--dbpath <dir>       字体索引目录（fonts.json 所在）
    -f/--fontpath <dirs>    额外字体目录（可重复，多次 -f 会叠加）
    -o/--output <dir>       输出目录（必须已存在，否则 assfonts 直接报错退出）
    -s/--subset-only        仅子集化，不嵌入
    -e/--embed-only         仅嵌入，不子集化
    -r/--rename             重命名子集化字体
    -l/--luminance <num>    HDR 亮度压暗
    -c/--font-combined      合并多个输入文件的同名字体（实验性）
    -m/--multi-thread <num> 内部线程数
    -v/--verbose <num>      日志级别 0-3

⚠️ 实测得到的三个反直觉行为（本模块据此设计）：
1. **退出码恒为 0** —— 缺字体、输出目录不存在、参数错误，assfonts 都返回 0。
   因此判定成败只能看「产物是否生成 + 日志文本」，绝不能信 returncode。
2. **`-v 0/1` 会连 `Missing the font` 警告一起吞掉** —— 仅靠日志会把「缺字体」误判成
   「未知失败」。故当日志无 missing 信息且无产物时，用调用方传入的索引字体名集合
   自行比对字幕引用字体，给出可行动的缺失清单（known_fonts 兜底）。
3. **`-c`（合并同名字体）永远不产出 .ass** —— 只输出共享目录 `subsetted_fonts/`。
   所以它不是一个可以直接交付的模式，必须两阶段：
   阶段一 `-c` 合并出字体夹，阶段二逐个文件 `-e -f <字体夹>` 嵌入。

各模式的实际产物（实测）：
    默认（子集+嵌入）   <stem>.assfonts.ass  + <stem>_subsetted/
    -s 仅子集化         仅 <stem>_subsetted/（没有 .ass！交付物是字体夹）
    -e 仅嵌入           <stem>.assfonts.ass（无 _subsetted）
    -e -s 清除内嵌      <stem>.cleaned.ass（输入没有内嵌字体时不产出任何文件）
    -c 合并             仅 <stem>_subsetted/ 或 subsetted_fonts/
    -r 重命名           <stem>.rename.assfonts.ass（另有 <stem>.rename.ass 中间产物）
    -l HDR              <stem>.hdr.assfonts.ass（.hdr 会插在 .rename 之前）
    -o <dir>            所有产物（含 _subsetted）都落到该目录
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

logger = logging.getLogger(__name__)

OUT_SUFFIX = ".assfonts.ass"
CLEANED_SUFFIX = ".cleaned.ass"
SUBSET_DIR_SUFFIX = "_subsetted"
COMBINED_DIR_NAME = "subsetted_fonts"

# ── 处理模式 ─────────────────────────────────────────────────

MODE_DEFAULT = "default"                  # 子集化 + 内嵌（常用）
MODE_SUBSET_ONLY = "subset_only"          # 仅子集化字体，交付字体夹
MODE_EMBED_ONLY = "embed_only"            # 仅内嵌（不子集化，字体按原样嵌入）
MODE_CLEAN_EMBEDDED = "clean_embedded"    # 清除已内嵌字体
MODE_COMBINED_SUBSET = "combined_subset"  # 多文件合并同名字体（两阶段）

MODE_LABELS: Dict[str, str] = {
    MODE_DEFAULT: "子集化 + 内嵌",
    MODE_SUBSET_ONLY: "仅子集化字体（输出字体包）",
    MODE_EMBED_ONLY: "仅内嵌字体（不子集化）",
    MODE_CLEAN_EMBEDDED: "清除已内嵌字体",
    MODE_COMBINED_SUBSET: "合并子集化（多文件共享字体，两阶段）",
}

MODE_DESCRIPTIONS: Dict[str, str] = {
    MODE_DEFAULT: "按字幕实际用到的字符裁剪字体并内嵌进字幕，成品脱离字体库也能正常显示。",
    MODE_SUBSET_ONLY: "只生成裁剪后的字体文件（_subsetted 文件夹），不改字幕；适合先子集化再用其它工具嵌入。",
    MODE_EMBED_ONLY: "把字体原样嵌入字幕，不做裁剪，成品体积较大；适合字体已裁剪过的场景。",
    MODE_CLEAN_EMBEDDED: "把字幕里已内嵌的字体段删除，还原成一个干净的普通字幕（输出 .cleaned.ass）。",
    MODE_COMBINED_SUBSET: "多个字幕共享同一份子集字体：先合并同名字体，再逐个内嵌，避免每个字幕各带一份重复字体。",
}

# 各模式的交付物类型：ass=单个字幕文件 / zip=字体包
MODE_OUTPUT_KIND: Dict[str, str] = {
    MODE_DEFAULT: "ass",
    MODE_SUBSET_ONLY: "zip",
    MODE_EMBED_ONLY: "ass",
    MODE_CLEAN_EMBEDDED: "ass",
    MODE_COMBINED_SUBSET: "ass",
}

ALL_MODES: Tuple[str, ...] = tuple(MODE_LABELS.keys())

# 实际输出形如： [WARN] Missing the font: "方正兰亭黑" (700,0)
_MISSING_RE = re.compile(r'missing the font:\s*"?([^"\n\r]+?)"?\s*(?:\([^)]*\))?\s*$', re.I)
_MISSING_FROM_LOG_RE = re.compile(r'found missing fonts', re.I)
_ERROR_RE = re.compile(r"\[error\]", re.I)


def is_valid_mode(mode: str) -> bool:
    return mode in MODE_LABELS


def normalize_mode(mode: Optional[str]) -> str:
    return mode if is_valid_mode(mode or "") else MODE_DEFAULT


# ── 命令构造（纯函数，便于单测） ─────────────────────────────

def _abs(path: Any) -> str:
    """统一转绝对路径。

    子进程的 cwd 是「字幕所在目录」而非进程工作目录，因此 -d/-f 与内核路径
    只要带相对成分就会在子进程里解析失败（实测表现为
    `[ERROR] --dbpath: Directory does not exist: "data/fonts/index"`）。
    """
    return str(Path(str(path)).expanduser().resolve())


def build_command(binary: Path, inputs: Sequence[Path], db_dir: Path, *,
                  mode: str = MODE_DEFAULT,
                  extra_font_dirs: Iterable[str] = (),
                  output_dir: Optional[str] = None,
                  rename: bool = False,
                  combine: bool = False,
                  hdr_luminance: int = 0,
                  threads: int = 0,
                  verbose: Optional[int] = None) -> List[str]:
    cmd: List[str] = [_abs(binary), "-i"] + [_abs(p) for p in inputs]
    cmd += ["-d", _abs(db_dir)]

    if mode == MODE_SUBSET_ONLY:
        cmd.append("-s")
    elif mode == MODE_EMBED_ONLY:
        cmd.append("-e")
    elif mode == MODE_CLEAN_EMBEDDED:
        cmd += ["-e", "-s"]
    # MODE_DEFAULT 不需要模式标志；-c 由 combine 参数单独控制

    if combine:
        cmd.append("-c")
    for d in extra_font_dirs:
        d = str(d or "").strip()
        if d:
            cmd += ["-f", _abs(d)]
    if output_dir:
        cmd += ["-o", _abs(output_dir)]
    if rename:
        cmd.append("-r")
    if hdr_luminance and int(hdr_luminance) > 0:
        cmd += ["-l", str(int(hdr_luminance))]
    if threads and int(threads) > 0:
        cmd += ["-m", str(int(threads))]
    if verbose is not None and int(verbose) != 3:
        cmd += ["-v", str(int(verbose))]
    return cmd


def predict_outputs(ass_path: Path, work_dir: Path, *, mode: str = MODE_DEFAULT,
                    rename: bool = False, hdr_luminance: int = 0) -> Dict[str, Path]:
    """按命名规则预测产物（仅供清理旧产物用；判定仍以实际扫描为准）。"""
    stem = ass_path.stem
    hdr = ".hdr" if hdr_luminance and int(hdr_luminance) > 0 else ""
    rn = ".rename" if rename else ""
    if mode == MODE_CLEAN_EMBEDDED:
        main = work_dir / f"{stem}{CLEANED_SUFFIX}"
    else:
        main = work_dir / f"{stem}{hdr}{rn}{OUT_SUFFIX}"
    return {
        "main": main,
        "subset_dir": work_dir / f"{stem}{hdr}{SUBSET_DIR_SUFFIX}",
    }


# ── 产物扫描 ─────────────────────────────────────────────────

def scan_artifacts(ass_path: Path, work_dir: Optional[Path] = None,
                   min_mtime: Optional[float] = None) -> Dict[str, List[Path]]:
    """扫描工作目录下属于该字幕的产物 / 中间文件 / 子集字体夹。

    用 startswith+endswith 手工匹配而非 glob，避免字幕名里的 [ ] * ? 被当作通配符；
    并显式排除输入文件自身（否则清理残留时会误删源字幕）。

    min_mtime：只认「本次执行之后」产生的文件。当输出目录是共享目录（-o 指向公共
    文件夹）时，同名旧文件可能属于**别的任务**，既不能预删也不能误当成本次成品，
    用修改时间过滤即可两全（同名再跑时 assfonts 会重写，mtime 自然刷新）。
    """
    parent = Path(work_dir) if work_dir else ass_path.parent
    stem = ass_path.stem
    input_name = ass_path.name
    # 中间产物只可能是 <stem>[.hdr][.rename].ass 这一种形态
    intermediate_re = re.compile(re.escape(stem) + r"(?:\.hdr)?(?:\.rename)?\.ass")

    outputs: List[Path] = []
    cleaned: List[Path] = []
    subset_dirs: List[Path] = []
    intermediates: List[Path] = []

    try:
        entries = list(os.scandir(parent))
    except OSError:
        return {"outputs": outputs, "cleaned": cleaned,
                "subset_dirs": subset_dirs, "intermediates": intermediates}

    for e in entries:
        name = e.name
        if name == input_name or not name.startswith(stem) or name == stem:
            continue
        p = Path(e.path)
        if min_mtime is not None:
            try:
                if e.stat().st_mtime < min_mtime:
                    continue
            except OSError:
                continue
        try:
            if e.is_dir():
                # <stem>_subsetted / <stem>.hdr_subsetted / 合并模式的 subsetted_fonts
                if name.endswith(SUBSET_DIR_SUFFIX) or name == COMBINED_DIR_NAME:
                    subset_dirs.append(p)
            elif e.is_file():
                if name.endswith(CLEANED_SUFFIX):
                    cleaned.append(p)
                elif name.endswith(OUT_SUFFIX):
                    outputs.append(p)
                elif intermediate_re.fullmatch(name):
                    intermediates.append(p)
        except OSError:
            continue

    def _mtime(p: Path) -> float:
        try:
            return p.stat().st_mtime
        except OSError:
            return 0.0

    for lst in (outputs, cleaned, subset_dirs):
        lst.sort(key=_mtime, reverse=True)
    return {"outputs": outputs, "cleaned": cleaned,
            "subset_dirs": subset_dirs, "intermediates": intermediates}


def clean_artifacts(ass_path: Path, work_dir: Optional[Path] = None) -> None:
    """清理上一轮残留，避免把旧成品误判为本次成功。"""
    found = scan_artifacts(ass_path, work_dir)
    for p in found["outputs"] + found["cleaned"] + found["intermediates"]:
        try:
            p.unlink()
        except OSError:
            pass
    for d in found["subset_dirs"]:
        shutil.rmtree(d, ignore_errors=True)


# ── 缺字体检测 ───────────────────────────────────────────────

def parse_missing(text: str) -> List[str]:
    missing: List[str] = []
    for line in (text or "").splitlines():
        m = _MISSING_RE.search(line.strip())
        if m:
            name = m.group(1).strip().strip('"').strip()
            if name and name not in missing:
                missing.append(name)
    return missing


def normalize_font_key(name: str) -> str:
    """字体名归一化：去 ASS 竖排前缀 @、去空格、统一大小写（用于与索引比对）。"""
    if not name:
        return ""
    n = name.strip().lstrip("@").replace(" ", "").replace("\u3000", "")
    return n.casefold()


def missing_by_index(referenced: Iterable[str], known_fonts: Optional[Set[str]]) -> List[str]:
    """用索引里的字体名集合自行比对，供日志被 -v 静默时兜底。"""
    if not known_fonts:
        return []
    known = {normalize_font_key(k) for k in known_fonts if k}
    out: List[str] = []
    for name in referenced:
        if normalize_font_key(name) not in known and name not in out:
            out.append(name)
    return out


# ── 执行 ─────────────────────────────────────────────────────

async def _exec(cmd: List[str], cwd: Path, timeout: int) -> Tuple[bool, int, str, int]:
    """执行 assfonts 命令 → (是否执行成功, 退出码, 输出文本, 耗时ms)。"""
    started = time.monotonic()
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
        )
    except Exception as e:
        return False, -1, f"无法启动 assfonts：{type(e).__name__} {e}", 0

    try:
        raw, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except Exception:
            pass
        return False, -1, f"处理超时（{timeout}s）", int((time.monotonic() - started) * 1000)

    text = (raw or b"").decode("utf-8", errors="replace")
    return True, proc.returncode or 0, text, int((time.monotonic() - started) * 1000)


def _ensure_dir(path: Path) -> Optional[str]:
    """assfonts 不会自建输出目录（报 `--output: Directory does not exist` 且退出码仍为 0），
    所以必须先建好。返回错误信息或 None。"""
    try:
        path.mkdir(parents=True, exist_ok=True)
        return None
    except Exception as e:
        return f"输出目录不可用：{path}（{e}）"


async def run_convert(binary: Path, ass_path: Path, db_dir: Path, *,
                      mode: str = MODE_DEFAULT,
                      extra_font_dirs: Iterable[str] = (),
                      output_dir: Optional[str] = None,
                      rename: bool = False,
                      combine: bool = False,
                      hdr_luminance: int = 0,
                      threads: int = 0,
                      verbose: Optional[int] = None,
                      keep_subset_dir: bool = True,
                      known_fonts: Optional[Set[str]] = None,
                      referenced_fonts: Optional[Sequence[str]] = None,
                      timeout: int = 900) -> Dict[str, Any]:
    """对单个字幕执行一次 assfonts 转换（覆盖全部处理模式）。

    :return: {status: success/skipped/missing/failed, mode, output, output_name,
              output_kind, output_size, subset_dir, cleaned, duration_ms, log, error}
    """
    mode = normalize_mode(mode)
    result: Dict[str, Any] = {
        "status": "failed", "mode": mode, "missing": [], "output": "", "output_name": "",
        "output_kind": MODE_OUTPUT_KIND.get(mode, "ass"), "output_size": 0,
        "subset_dir": "", "cleaned": "", "duration_ms": 0, "log": "", "error": "",
    }

    if not ass_path.is_file():
        result["error"] = f"字幕文件不存在：{ass_path}"
        return result

    abs_ass = ass_path.resolve()
    work_dir = Path(output_dir).resolve() if output_dir else abs_ass.parent
    err = _ensure_dir(work_dir)
    if err:
        result["error"] = err
        return result

    # 「清除内嵌」：输入本就没有内嵌字体时 assfonts 什么都不做，这里提前给出明确结论
    if mode == MODE_CLEAN_EMBEDDED:
        try:
            from font_core.ass_parser import has_embedded_fonts, decode_ass_text
            if not has_embedded_fonts(decode_ass_text(abs_ass.read_bytes())):
                result.update({"status": "skipped",
                               "error": "该字幕没有内嵌字体，无需清除"})
                return result
        except Exception:
            pass

    # 任务自己的工作目录是私有的，可以放心预清理；
    # 共享输出目录（-o 指向公共文件夹）绝不预删 —— 同名文件可能属于别的任务。
    own_dir = work_dir == abs_ass.parent
    if own_dir:
        clean_artifacts(abs_ass, work_dir)
    else:
        clean_artifacts(abs_ass, abs_ass.parent)
    run_start = time.time() - 1.0  # 1s 宽限，规避文件系统 mtime 精度问题

    cmd = build_command(binary, [abs_ass], db_dir, mode=mode,
                        extra_font_dirs=extra_font_dirs, output_dir=str(work_dir) if output_dir else None,
                        rename=rename, combine=combine, hdr_luminance=hdr_luminance,
                        threads=threads, verbose=verbose)

    ok, code, text, ms = await _exec(cmd, abs_ass.parent, timeout)
    result["log"] = text.strip()[-6000:]
    result["duration_ms"] = ms
    if not ok:
        result["error"] = text.strip()[-300:]
        return result

    found = scan_artifacts(abs_ass, work_dir, min_mtime=run_start)
    if not own_dir:
        src = scan_artifacts(abs_ass, abs_ass.parent, min_mtime=run_start)
        for key in ("outputs", "cleaned", "subset_dirs", "intermediates"):
            found[key] = found[key] + src[key]

    # 缺字体判定：优先日志，日志被 -v 静默时退回索引比对
    missing = parse_missing(text)
    if not missing and not found["outputs"] and not found["cleaned"]:
        missing = missing_by_index(referenced_fonts or [], known_fonts)
        if missing:
            result["missing_via"] = "index"
    result["missing"] = missing
    if missing:
        result["status"] = "missing"
        result["error"] = "缺失字体：" + "、".join(missing)
        return result

    # 按模式挑选主交付物
    main: Optional[Path] = None
    subset_dir: Optional[Path] = None
    if mode == MODE_SUBSET_ONLY:
        subset_dir = found["subset_dirs"][0] if found["subset_dirs"] else None
        if subset_dir is None:
            result["status"] = "failed"
            result["error"] = _first_error(text) or "未生成子集字体文件夹（_subsetted）"
            return result
        result["output_kind"] = "zip"
        result["output"] = str(subset_dir)
        result["output_name"] = f"{abs_ass.stem}_subsetted.zip"
    elif mode == MODE_CLEAN_EMBEDDED:
        main = found["cleaned"][0] if found["cleaned"] else None
        if main is None:
            result["status"] = "failed"
            result["error"] = _first_error(text) or "未生成清理后的字幕（.cleaned.ass）"
            return result
        result["output"] = str(main)
        result["output_name"] = f"{abs_ass.stem}.cleaned.ass"
    else:
        main = found["outputs"][0] if found["outputs"] else None
        subset_dir = found["subset_dirs"][0] if found["subset_dirs"] else None
        if main is None:
            result["status"] = "failed"
            result["error"] = _first_error(text) or "处理结束但未生成成品字幕"
            return result
        result["output"] = str(main)
        result["output_name"] = f"{abs_ass.stem}.assfonts.ass"

    # 清理中间产物与（可选的）子集字体夹
    for p in found["intermediates"]:
        try:
            p.unlink()
        except OSError:
            pass
    # 其余产物（如对已内嵌字幕处理时附带生成的 .cleaned.ass）保留在目录中，
    # 不主动删除，并登记到结果里供前端按需下载。
    if subset_dir is not None:
        result["subset_dir"] = str(subset_dir)
        if not keep_subset_dir and mode != MODE_SUBSET_ONLY:
            shutil.rmtree(subset_dir, ignore_errors=True)
            result["subset_dir"] = ""
    if found["cleaned"] and mode != MODE_CLEAN_EMBEDDED:
        result["cleaned"] = str(found["cleaned"][0])
    if found["outputs"] and mode != MODE_CLEAN_EMBEDDED:
        result["secondary_output"] = str(found["outputs"][0])

    try:
        result["output_size"] = _dir_size(Path(result["output"])) if result["output_kind"] == "zip" \
            else Path(result["output"]).stat().st_size
    except OSError:
        result["output_size"] = 0

    result["status"] = "success"
    result["error"] = ""
    return result


async def run_combined(binary: Path, ass_paths: Sequence[Path], db_dir: Path, *,
                       extra_font_dirs: Iterable[str] = (),
                       output_dir: Optional[str] = None,
                       rename: bool = False,
                       hdr_luminance: int = 0,
                       threads: int = 0,
                       verbose: Optional[int] = None,
                       keep_subset_dir: bool = True,
                       known_fonts: Optional[Set[str]] = None,
                       referenced_map: Optional[Dict[str, Sequence[str]]] = None,
                       timeout: int = 1800) -> Dict[str, Any]:
    """合并子集化（两阶段）—— 多个字幕共享同一份子集字体。

    实测：`-c` 只产出共享字体夹 `subsetted_fonts/`，不会产出任何 .ass。
    因此正确流程是：
        阶段一  assfonts -i f1 f2 ... -d db -c            → subsetted_fonts/
        阶段二  assfonts -e -i fi -d db -f subsetted_fonts → fi.assfonts.ass
    :return: {status, stage, combined_dir, results: [{path, status, output, error, ...}]}
    """
    if not ass_paths:
        return {"status": "failed", "error": "没有输入字幕", "results": []}

    inputs = [Path(p).resolve() for p in ass_paths]
    for p in inputs:
        if not p.is_file():
            return {"status": "failed", "error": f"字幕文件不存在：{p}", "results": []}

    work_dir = Path(output_dir).resolve() if output_dir else inputs[0].parent
    err = _ensure_dir(work_dir)
    if err:
        return {"status": "failed", "error": err, "results": []}

    # 阶段一：合并子集化
    for p in inputs:
        clean_artifacts(p, work_dir)
    stage1_cmd = build_command(binary, inputs, db_dir, mode=MODE_DEFAULT, combine=True,
                               extra_font_dirs=extra_font_dirs,
                               output_dir=str(work_dir) if output_dir else None,
                               rename=rename, hdr_luminance=hdr_luminance,
                               threads=threads, verbose=verbose)
    ok, code, text, ms = await _exec(stage1_cmd, inputs[0].parent, timeout)
    if not ok:
        return {"status": "failed", "stage": "combine", "error": text.strip()[-300:], "results": []}

    combined_dir = None
    for cand in (work_dir, inputs[0].parent):
        d = cand / COMBINED_DIR_NAME
        if d.is_dir():
            combined_dir = d
            break
    if combined_dir is None:
        missing = parse_missing(text)
        return {
            "status": "missing" if missing else "failed",
            "stage": "combine",
            "missing": missing,
            "error": ("缺失字体：" + "、".join(missing)) if missing
                     else (_first_error(text) or "合并阶段未生成字体夹 subsetted_fonts"),
            "log": text.strip()[-4000:],
            "results": [],
        }

    # 阶段二：逐个文件仅嵌入（字体来自合并后的字体夹）
    results: List[Dict[str, Any]] = []
    for p in inputs:
        r = await run_convert(binary, p, db_dir, mode=MODE_EMBED_ONLY,
                              extra_font_dirs=[str(combined_dir)], output_dir=str(work_dir),
                              rename=rename, hdr_luminance=hdr_luminance, threads=threads,
                              verbose=verbose, keep_subset_dir=keep_subset_dir,
                              known_fonts=known_fonts,
                              referenced_fonts=(referenced_map or {}).get(str(p)),
                              timeout=timeout)
        r["path"] = str(p)
        results.append(r)

    if not keep_subset_dir:
        shutil.rmtree(combined_dir, ignore_errors=True)
        combined_dir = None

    ok_count = sum(1 for r in results if r.get("status") == "success")
    miss_count = sum(1 for r in results if r.get("status") == "missing")
    status = "success" if ok_count and not miss_count and ok_count == len(results) else (
        "missing" if miss_count and not ok_count else
        ("partial" if ok_count else "failed"))
    return {
        "status": status,
        "stage": "done",
        "combined_dir": str(combined_dir) if combined_dir else "",
        "duration_ms": ms,
        "log": text.strip()[-4000:],
        "results": results,
    }


def _first_error(text: str) -> str:
    errs = [ln.strip() for ln in (text or "").splitlines() if _ERROR_RE.search(ln)]
    return "；".join(errs[:3])


def _dir_size(path: Path) -> int:
    total = 0
    try:
        for root, _dirs, files in os.walk(path):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass
    except OSError:
        pass
    return total


def zip_dir(path: Path, arc_root: Optional[str] = None) -> bytes:
    """把产物目录打包为 zip（仅子集化模式的交付物）。"""
    import io
    import zipfile

    root = Path(path)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        if root.is_file():
            zf.write(root, arcname=arc_root or root.name)
        else:
            base = arc_root or root.name
            for cur, _dirs, files in os.walk(root):
                for f in sorted(files):
                    full = Path(cur) / f
                    rel = full.relative_to(root)
                    zf.write(full, arcname=str(Path(base) / rel).replace("\\", "/"))
    return buf.getvalue()
