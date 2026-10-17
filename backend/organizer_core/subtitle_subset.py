"""整理任务里的「随行字幕子集化」编排。

只做三件事，真正的内核调用都在 font_core.subset_service 里：

1. 判断哪些随行字幕该处理（`.ass/.ssa`、本地源、开关开启、非 hash_only）；
2. 批量子集化（≥2 个走合并模式，共享一份子集字体）；
3. 产出 src 覆盖表 + 每个文件的结论，供 processor 换 plan、写日志与整理历史。

语义约定（与产品确认过）：

- 成功 → 用内嵌成品替换该字幕的源路径，交付名在 processor 侧加 `.assfonts` 标记；
- 缺字体 / 失败 / 已内嵌 / 非 ASS → **不改 src**，原字幕照常搬进目标目录；
- 任何情况下都不阻断整理：字体没配好也只是少一次子集化。
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import time
import uuid
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

from config_manager import ConfigManager
from font_core import subset_service as ss

logger = logging.getLogger(__name__)

# 临时目录里超过这个时间的残留目录会在下次整理时顺手清掉
STALE_SECONDS = 24 * 3600
_swept_roots: set = set()

LogFn = Callable[..., Awaitable[Any]]

# 同一进程内只写一次系统日志的提示（避免 CD2 任务每集刷屏）
_syslog_once: set = set()


def _sys_log(msg: str, level: str = "INFO", once: str = "") -> None:
    """写系统日志（logger）。

    整理任务大多在后半夜自动跑，没人盯着任务中心；缺字体这类提示如果只进
    任务历史，事后在「系统日志」里完全看不到，所以这里双写一份。
    """
    if once:
        if once in _syslog_once:
            return
        _syslog_once.add(once)
    text = f"[字幕子集化] {msg}"
    lvl = (level or "INFO").upper()
    if lvl == "WARN":
        logger.warning(text)
    elif lvl == "ERROR":
        logger.error(text)
    else:
        logger.info(text)


def _human_size(size: int) -> str:
    try:
        size = int(size)
    except (TypeError, ValueError):
        return "未知大小"
    if size >= 1024 * 1024:
        return f"{size / 1024 / 1024:.2f} MB"
    if size >= 1024:
        return f"{size / 1024:.0f} KB"
    return f"{size} B"


class RelatedSubtitleSubsetter:
    """随行字幕子集化的编排器（无状态，全部静态方法）。"""

    @staticmethod
    def candidates(related_files: List[str]) -> List[str]:
        return [f for f in (related_files or [])
                if os.path.splitext(f)[1].lower() in ss.SUBTITLE_EXTS]

    @staticmethod
    def _sweep_stale(base: Path) -> None:
        """清掉上次异常退出留下的临时目录（每个进程只扫一次）。"""
        key = str(base)
        if key in _swept_roots:
            return
        _swept_roots.add(key)
        try:
            if not base.is_dir():
                return
            now = time.time()
            for entry in base.iterdir():
                try:
                    if entry.is_dir() and now - entry.stat().st_mtime > STALE_SECONDS:
                        shutil.rmtree(entry, ignore_errors=True)
                        logger.info(f"[字幕子集化] 已清理陈旧临时目录: {entry}")
                except OSError:
                    continue
        except OSError:
            pass

    @staticmethod
    def _work_root(cfg: Dict[str, Any], task_id: Optional[str]) -> Path:
        fm = (cfg or {}).get("font_manager", {}) or {}
        base = Path(str(fm.get("organize_tmp_dir") or "data/fonts/organize_tmp"))
        RelatedSubtitleSubsetter._sweep_stale(base)
        tag = re.sub(r'[^0-9A-Za-z_.-]', '_', str(task_id or "adhoc"))[:48] or "adhoc"
        return base / tag / uuid.uuid4().hex[:8]

    @staticmethod
    async def prepare(
        related_files: List[str],
        root: str,
        task: Dict[str, Any],
        *,
        dry_run: bool = False,
        task_id: Optional[str] = None,
        log: Optional[LogFn] = None,
    ) -> Tuple[Dict[str, str], Dict[str, Dict[str, Any]], str]:
        """返回 (src 覆盖表, 每个文件的结论, 临时目录)。

        :param related_files: 扫描到的随行文件名（相对 root）
        :param root: 视频所在目录
        :param task: 整理任务配置
        :param dry_run: 预览模式只做只读预检，不启动内核、不落任何文件
        :param log: 写日志的回调（processor 传 _log_both，保证外层任务与识别任务都能看到）
        :return: (overrides{文件名: 成品绝对路径}, info{文件名: {subset, missing, ...}}, work_dir)
        """
        overrides: Dict[str, str] = {}
        info: Dict[str, Dict[str, Any]] = {}
        work_root = ""

        if not task.get("subset_subtitles"):
            return overrides, info, work_root
        if task.get("action_type") == "hash_only":
            return overrides, info, work_root

        files = RelatedSubtitleSubsetter.candidates(related_files)
        if not files:
            return overrides, info, work_root

        async def _log(msg: str, level: str = "INFO", once: str = "") -> None:
            # 双写：系统日志 + 任务中心（任务历史）
            _sys_log(msg, level, once)
            if log is not None:
                try:
                    await log(msg, level)
                except Exception:
                    pass

        if (task.get("source_via") or "local") != "local":
            await _log("⚠️ 随行字幕在云盘上，暂不支持子集化（按原字幕搬运）", "WARN",
                       once="cloud-source")
            info = {f: {"subset": "skipped", "reason": "云源字幕"} for f in files}
            return overrides, info, work_root

        cfg = ConfigManager.get_config()
        ctx = await ss.resolve_context(cfg)
        if not ctx.ok:
            await _log(f"⚠️ 字幕子集化已跳过：{ctx.error}（按原字幕搬运）", "WARN",
                       once=f"noctx:{ctx.error}")
            info = {f: {"subset": "unavailable", "reason": ctx.error} for f in files}
            return overrides, info, work_root

        abs_paths = [os.path.join(root, f) for f in files]

        # ── 预览：只读预检 ──
        if dry_run:
            checked = await ss.precheck_files(abs_paths, ctx)
            for f, p in zip(files, abs_paths):
                r = checked.get(str(Path(p).resolve())) or {}
                status = r.get("status") or "failed"
                info[f] = {
                    "subset": status,
                    "missing": r.get("missing") or [],
                    "fonts": len(r.get("fonts") or []),
                    "referenced": list(r.get("fonts") or []),
                }
                if status == "missing":
                    await _log(f"⚠️ [预览] 缺字体，将按原字幕搬运：{f}"
                               f"（{'、'.join(r.get('missing') or [])}）", "WARN")
                elif status == "planned":
                    # 预览不改动任何文件，但要把「将带 .assfonts 标记」提前反映到目标名上；
                    # 值填原路径，processor 侧只是照旧用原文件、仅改交付名。
                    overrides[f] = p
                    await _log(f"✂️ [预览] 将子集化：{f}（引用 {info[f]['fonts']} 种字体）")
                else:
                    await _log(f"⏭️ [预览] 不子集化：{f}（{r.get('reason') or status}）")
            return overrides, info, work_root

        # ── 正式执行 ──
        work_root = str(RelatedSubtitleSubsetter._work_root(cfg, task_id))
        started = time.monotonic()
        try:
            results = await ss.subset_files(abs_paths, work_dir=work_root, ctx=ctx)
        except Exception as e:  # 任何异常都只降级，不阻断整理
            logger.warning(f"[字幕子集化] 执行异常，按原字幕搬运: {e}")
            await _log(f"⚠️ 字幕子集化异常，按原字幕搬运：{type(e).__name__} {e}", "WARN")
            info = {f: {"subset": "failed", "reason": str(e)} for f in files}
            return overrides, info, work_root

        for f, p in zip(files, abs_paths):
            r = results.get(str(Path(p).resolve())) or {}
            status = r.get("status") or "failed"
            info[f] = {
                "subset": status,
                "missing": r.get("missing") or [],
                "fonts": len(r.get("fonts") or []),
                "referenced": list(r.get("fonts") or []),
                "duration_ms": r.get("duration_ms") or 0,
            }
            if status == "success":
                out = r.get("output") or ""
                overrides[f] = out
                try:
                    size = os.path.getsize(out)
                except OSError:
                    size = 0
                await _log(f"✂️ 子集化：{f}（引用 {info[f]['fonts']} 种字体 → {_human_size(size)}）")
                for warn in (r.get("warnings") or [])[:3]:
                    await _log(f"⚠️ {f}：{warn}", "WARN")
            elif status == "missing":
                await _log(f"⚠️ 缺字体，按原字幕搬运：{f}"
                           f"（{'、'.join(r.get('missing') or [])}）", "WARN")
            elif status == "skipped":
                await _log(f"⏭️ 不子集化：{f}（{r.get('reason') or '已内嵌'}）")
            else:
                await _log(f"⚠️ 子集化失败，按原字幕搬运：{f}"
                           f"（{r.get('reason') or '未知原因'}）", "WARN")

        counts = {"success": 0, "skipped": 0, "missing": 0, "failed": 0}
        for _v in info.values():
            _k = _v.get("subset") or "failed"
            counts[_k] = counts.get(_k, 0) + 1
        _parts = [f"已内嵌 {counts['success']}"]
        if counts["missing"]:
            _parts.append(f"缺字体 {counts['missing']}")
        if counts["skipped"]:
            _parts.append(f"跳过 {counts['skipped']}")
        if counts["failed"]:
            _parts.append(f"失败 {counts['failed']}")
        _sys_log(f"随行字幕处理完成（{'、'.join(_parts)}，"
                 f"耗时 {int((time.monotonic() - started) * 1000)}ms）")
        return overrides, info, work_root

    @staticmethod
    def cleanup(work_root: Optional[str]) -> None:
        """删掉本次的临时目录（成品已搬走，输入副本与 _subsetted 都没用了）。"""
        if not work_root:
            return
        try:
            shutil.rmtree(work_root, ignore_errors=True)
        except Exception as e:
            logger.debug(f"[字幕子集化] 清理临时目录失败: {work_root} | {e}")
