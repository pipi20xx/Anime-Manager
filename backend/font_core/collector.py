"""字体包采集 —— 跟随整理流程触发，异步处理（无轮询）。

**与字幕子集化无任何关联**：只负责「发现字体包 → 解压 → 比对 → 入库」，
不判断这个包属于哪一集、不参与子集化、不改处理历史。

触发：`processor.py` 枚举同目录文件时顺手判断压缩包，命中就交给
`submit_font_archives()` —— 本函数只做「名字过滤 + 账本去重 + 入队」，微秒级。
不做轮询：整理流程本来就已经列过目录，再单独扫一遍（尤其网盘路径）纯属额外开销。

投递后由单 worker 串行处理（串行 = 不会两个包同时往 imported/ 写、也不会同时重建索引）：
    等文件稳定（size/mtime 不变）→ 硬链/复制进工作区 → analyze → auto_commit → 索引 debounce

幂等有两层：
1. 采集账本：`(绝对路径, size, mtime)`，同一个包不会被重复投递（整理 12 集也只投一次）；
2. 入库判重：sha256 完全相同 / 同 face 同 psname / 同 psname 不同 family（判冲突、默认保留库内）。

对外接口：
    submit_font_archives(source_via, root, names)   # 整理流程调用
    stop_worker()                                   # 关闭时收尾
    state_snapshot()                                # 设置页/诊断展示
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from font_core import archive, importer, import_store

logger = logging.getLogger(__name__)

# 文件名里出现 font/fonts/字体（带词边界，避免命中 fzlantinghei 之类）
NAME_RE = re.compile(r"(?i)(^|[^a-z])(fonts?|字体)([^a-z]|$)")

DEFAULT_SETTLE = 10          # 内部固定：size/mtime 连续 10 秒不变即认为写完
DEFAULT_SETTLE_TIMEOUT = 1800  # 内部固定：最多等 30 分钟（大包慢盘也够）
_STATE_TTL_DAYS = 30

_STATE: Dict[str, Any] = {"done": {}, "last_submit": "", "last_result": {}}
# 已投递但还没处理完的 key（"占位"）：防止 worker 处理期间同一个包被再次投递。
# 只在内存里：进程重启时队列本来就丢了，pending 一起丢是正确语义。
_PENDING: set = set()

_QUEUE: Optional[asyncio.Queue] = None
_WORKER: Optional[asyncio.Task] = None
_STOP = False


# ── 配置 ────────────────────────────────────────────────────

def _fm(cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if cfg is None:
        cfg = _cfg_now()
    return (cfg or {}).get("font_manager", {}) or {}


def _cfg_now() -> Dict[str, Any]:
    try:
        from config_manager import ConfigManager
        return ConfigManager.get_config() or {}
    except Exception:
        return {}


def _to_int(value: Any, default: int, lo: int, hi: int) -> int:
    try:
        return max(lo, min(hi, int(value)))
    except (TypeError, ValueError):
        return default


def enabled(cfg: Optional[Dict[str, Any]] = None) -> bool:
    return bool(_fm(cfg).get("collect_enabled"))


def settle_seconds(cfg: Optional[Dict[str, Any]] = None) -> int:
    """等多久算写完：内部固定值，不暴露给用户调。"""
    return DEFAULT_SETTLE


def settle_timeout(cfg: Optional[Dict[str, Any]] = None) -> int:
    """等稳定的上限：内部固定值（超时说明包还在下，跳过等下次整理再遇到）。"""
    return DEFAULT_SETTLE_TIMEOUT


def cleanup_after(cfg: Optional[Dict[str, Any]] = None) -> bool:
    return bool(_fm(cfg).get("collect_cleanup"))


def collect_mode(cfg: Optional[Dict[str, Any]] = None) -> str:
    mode = str(_fm(cfg).get("collect_mode") or "auto_commit").strip().lower()
    return mode if mode in ("auto_commit", "report_only") else "auto_commit"


# ── 状态 / 账本 ─────────────────────────────────────────────

def _state_file(cfg: Optional[Dict[str, Any]] = None) -> Path:
    return importer.import_root(cfg) / ".collect_state.json"


def _load_state(cfg: Optional[Dict[str, Any]] = None) -> None:
    try:
        with open(_state_file(cfg), "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            _STATE["done"] = data.get("done") or {}
            _STATE["last_submit"] = data.get("last_submit") or ""
            _STATE["last_result"] = data.get("last_result") or {}
    except (OSError, json.JSONDecodeError):
        pass


def _save_state(cfg: Optional[Dict[str, Any]] = None) -> None:
    fp = _state_file(cfg)
    cutoff = time.time() - _STATE_TTL_DAYS * 86400
    _STATE["done"] = {k: v for k, v in (_STATE["done"] or {}).items() if float(v or 0) >= cutoff}
    try:
        fp.parent.mkdir(parents=True, exist_ok=True)
        tmp = fp.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(_STATE, fh, ensure_ascii=False)
        os.replace(tmp, fp)
    except OSError as e:
        logger.debug(f"[字体采集] 状态落盘失败: {e}")


def _key(path: Path, size: int, mtime: int) -> str:
    return f"{path.as_posix()}|{size}|{mtime}"


def state_snapshot() -> Dict[str, Any]:
    return {
        "last_submit": _STATE.get("last_submit", ""),
        "last_result": _STATE.get("last_result", {}),
        "processed": len(_STATE.get("done") or {}),
        "pending": len(_PENDING),
        "queued": _QUEUE.qsize() if _QUEUE is not None else 0,
        "worker_running": worker_running(),
    }


def worker_running() -> bool:
    return bool(_WORKER and not _WORKER.done())


# ── 投递（整理流程调用，同步且极轻）──────────────────────────

def _looks_like_font_archive(name: str) -> bool:
    return archive.is_archive_name(name) and bool(NAME_RE.search(name))


def _key_cloud(v_dir: str, name: str, size: int, write_time: int) -> str:
    """云源账本 key：路径 + 大小 + 云端修改时间（对应本地的 path+size+mtime）。"""
    return f"cd2:{str(v_dir).rstrip('/')}/{name}|{int(size or 0)}|{int(write_time or 0)}"


def submit_font_archives(source_via: str, root: str, names: List[str],
                         task_id: str = "", *,
                         cloud_entries: Optional[List[Dict[str, Any]]] = None,
                         cd2_client_id: str = "") -> Dict[str, Any]:
    """整理流程调用：把同目录里"看起来是字体包"的文件丢进采集队列。

    - 只做名字过滤 + 账本去重 + `put_nowait`，不 stat、不解压、不 await；
    - 本地源：直接拿本地文件处理；
    - 云源（cd2）：先按云端条目（size / write_time）记账，worker 里再用 CD2 接口
      把包下载到临时目录，之后走同一条流水线（下载完即删临时文件）。
    """
    out: Dict[str, Any] = {"accepted": [], "skipped": [], "reason": ""}
    try:
        cfg = _cfg_now()
        if not enabled(cfg):
            out["reason"] = "未启用"
            return out
        if not names:
            return out

        is_cloud = source_via == "cd2"
        entries = {(e.get("name") or ""): e for e in (cloud_entries or []) if not e.get("is_dir")}
        _load_state(cfg)
        queued: List[Dict[str, Any]] = []
        for name in names:
            if not _looks_like_font_archive(name):
                continue

            if is_cloud:
                entry = entries.get(name) or {}
                size = int(entry.get("size") or 0)
                wtime = int(entry.get("write_time") or 0)
                key = _key_cloud(root, name, size, wtime)
                path_label = f"{str(root).rstrip('/')}/{name}"
            else:
                path = Path(root) / name
                try:
                    st = path.stat()
                except OSError:
                    continue
                size = st.st_size
                key = _key(path, size, int(st.st_mtime))
                path_label = str(path)

            if key in (_STATE["done"] or {}):
                out["skipped"].append({"path": path_label, "reason": "已处理过"})
                continue
            if key in _PENDING:
                # 已在队列里/正在处理：同一集多个视频、或 worker 还在跑，都不重复投
                out["skipped"].append({"path": path_label, "reason": "正在处理中"})
                continue

            _PENDING.add(key)
            item: Dict[str, Any] = {"key": key, "task_id": task_id, "at": time.time(),
                                    "size": size, "via": "cd2" if is_cloud else "local"}
            if is_cloud:
                item.update({"v_dir": str(root), "name": name, "client_id": cd2_client_id})
            else:
                item["path"] = str(Path(root) / name)
            queued.append(item)

        if queued:
            _ensure_worker()
            for item in queued:
                _QUEUE.put_nowait(item)
            _STATE["last_submit"] = time.strftime("%Y-%m-%d %H:%M:%S")
            out["accepted"] = [item.get("path") or f"{item.get('v_dir')}/{item.get('name')}"
                               for item in queued]
            logger.info(f"[字体采集] 投递 {len(queued)} 个字体包（task={task_id or '-'}）："
                        f"{', '.join(Path(str(x)).name for x in out['accepted'])}")
        return out
    except Exception as e:      # 绝不影响整理
        logger.warning(f"[字体采集] 投递异常（忽略）: {type(e).__name__} {e}")
        out["reason"] = f"投递异常：{e}"
        return out


# ── 队列 / worker ───────────────────────────────────────────

def _ensure_worker() -> None:
    global _QUEUE, _WORKER
    if _QUEUE is None:
        _QUEUE = asyncio.Queue()
    if _WORKER is None or _WORKER.done():
        _WORKER = asyncio.create_task(_worker_loop())
        logger.info("[字体采集] worker 已启动（串行处理）")


async def _worker_loop() -> None:
    while not _STOP:
        try:
            item = await _QUEUE.get()
        except asyncio.CancelledError:
            raise
        try:
            await _handle(item)
        except asyncio.CancelledError:
            raise
        except Exception as e:      # 单条失败不影响后续
            logger.warning(f"[字体采集] 处理失败 {item.get('path')}: {type(e).__name__} {e}")
        finally:
            try:
                _QUEUE.task_done()
            except Exception:
                pass


async def stop_worker() -> None:
    global _STOP, _WORKER
    _STOP = True
    if _WORKER and not _WORKER.done():
        _WORKER.cancel()
        try:
            await _WORKER
        except (asyncio.CancelledError, Exception):
            pass
    _WORKER = None
    _STOP = False


def _mark_done(item: Dict[str, Any], cfg: Dict[str, Any]) -> None:
    """记账本：本地用 path+size+mtime，云源用 v_dir+name+size+write_time（由调用方放进 key）。"""
    key = str(item.get("key") or "")
    if not key:
        return
    _STATE.setdefault("done", {})[key] = time.time()
    _save_state(cfg)


def _release(item: Dict[str, Any]) -> None:
    """处理没走完就释放占位，等下一次整理枚举时还能重试。"""
    _PENDING.discard(str(item.get("key") or ""))


def _binary_of(cfg: Dict[str, Any]) -> Path:
    from font_core import binary as af_binary
    binary_path, _ = af_binary.resolve_binary(cfg)
    return Path(binary_path) if binary_path else Path("__assfonts_unavailable__")


async def _handle(item: Dict[str, Any]) -> Dict[str, Any]:
    if str(item.get("via") or "local") == "cd2":
        return await _handle_cloud(item)
    return await _handle_local(item)


async def _handle_local(item: Dict[str, Any]) -> Dict[str, Any]:
    path = Path(str(item.get("path") or ""))
    cfg = _cfg_now()
    out: Dict[str, Any] = {"job_id": "", "source": str(path), "success": False,
                           "counts": {}, "committed": 0, "message": ""}

    if not enabled(cfg):
        out["message"] = "已停用，丢弃本次任务"
        _release(item)
        return out

    if not await _wait_stable(path, settle_seconds(cfg), settle_timeout(cfg)):
        out["message"] = "文件迟迟不稳定（可能仍在下载），本次跳过，下次整理会再试"
        logger.info(f"[字体采集] {path} {out['message']}")
        _release(item)
        return out

    try:
        st = path.stat()
    except OSError as e:
        out["message"] = f"文件不可读：{e}"
        _release(item)
        return out
    if st.st_size > importer.limits(cfg).max_archive_bytes:
        out["message"] = "超过单包大小上限"
        _mark_done(item, cfg)
        _release(item)
        return out

    job = await _enqueue(cfg, path)
    if not job.get("ok"):
        out["message"] = job.get("message", "投递失败")
        _release(item)
        return out
    _mark_done(item, cfg)
    _release(item)

    processed = await _process(cfg, _binary_of(cfg), job["job_id"], path, allow_cleanup=True)
    processed["job_id"] = job["job_id"]
    return processed


async def _handle_cloud(item: Dict[str, Any]) -> Dict[str, Any]:
    """云源（CD2）：先把包下载到临时目录，再走与本地完全相同的流水线。

    为什么不在整理流程里下载：那会把网络 IO 塞进整理队列。放这里异步串行做，
    下载完立刻删临时文件，不占额外的持久空间。
    """
    cfg = _cfg_now()
    v_dir = str(item.get("v_dir") or "").rstrip("/")
    name = str(item.get("name") or "")
    label = f"{v_dir}/{name}"
    out: Dict[str, Any] = {"job_id": "", "source": label, "success": False,
                           "counts": {}, "committed": 0, "message": ""}

    if not enabled(cfg):
        out["message"] = "已停用，丢弃本次任务"
        _release(item)
        return out
    try:
        if int(item.get("size") or 0) > importer.limits(cfg).max_archive_bytes:
            out["message"] = "超过单包大小上限"
            _mark_done(item, cfg)
            _release(item)
            return out
    except (TypeError, ValueError):
        pass

    local, err = await _download_cloud(cfg, item)
    if local is None:
        out["message"] = err or "云端下载失败"
        logger.info(f"[字体采集] {label} {out['message']}（下次整理会再试）")
        _release(item)
        return out

    try:
        job = await _enqueue(cfg, local)
        if not job.get("ok"):
            out["message"] = job.get("message", "投递失败")
            _release(item)
            return out
        _mark_done(item, cfg)
        _release(item)
        processed = await _process(cfg, _binary_of(cfg), job["job_id"], None, allow_cleanup=False)
        processed["job_id"] = job["job_id"]
        return processed
    finally:
        shutil.rmtree(local.parent, ignore_errors=True)      # 临时目录整体清掉


def _resolve_cd2_client(v_path: str, cd2_client_id: str = ""):
    """按「显式 id > 挂载路径前缀 > 单实例兜底」找 CD2 客户端（与字幕子集化一致）。"""
    try:
        from clients.manager import ClientManager
    except Exception:
        return None
    all_clients = ClientManager.get_all_clients() or []
    cds = [c for c in all_clients if c.get("type") == "cd2"]
    if not cds:
        return None
    if cd2_client_id and any(c.get("id") == cd2_client_id for c in cds):
        return ClientManager.get_client(cd2_client_id)
    for conf in cds:
        mount = str(conf.get("mount_path") or "").rstrip("/")
        if mount and str(v_path).startswith(mount):
            return ClientManager.get_client(conf.get("id"))
    if len(cds) == 1:
        return ClientManager.get_client(cds[0].get("id"))
    return None


async def _download_cloud(cfg: Dict[str, Any], item: Dict[str, Any]) -> tuple:
    """把云端的字体包下到临时目录，返回 (本地路径, 错误说明)。"""
    v_dir = str(item.get("v_dir") or "").rstrip("/")
    name = str(item.get("name") or "")
    dest_dir = importer.temp_staging_root(cfg) / "cloud" / uuid.uuid4().hex[:12]
    dest = dest_dir / name
    try:
        client = await asyncio.to_thread(_resolve_cd2_client, v_dir, str(item.get("client_id") or ""))
        if client is None:
            return None, "未找到可用的 CD2 客户端"
        try:
            logged = await asyncio.to_thread(client.login)
        except Exception as e:
            return None, f"CD2 登录异常：{type(e).__name__} {e}"
        if not logged:
            return None, "CD2 未登录"
        browser = getattr(client, "_file_browser", None)
        if browser is None:
            return None, "CD2 客户端缺少 file_browser"
        dest_dir.mkdir(parents=True, exist_ok=True)
        ok, msg = await asyncio.to_thread(browser.download_file, f"{v_dir}/{name}", str(dest))
        if not ok or not dest.is_file():
            return None, f"云端下载失败：{msg}"
        return dest, ""
    except Exception as e:
        shutil.rmtree(dest_dir, ignore_errors=True)
        return None, f"云端下载异常：{type(e).__name__} {e}"


async def _wait_stable(path: Path, settle: int, timeout: int) -> bool:
    """等 size/mtime 连续 `settle` 秒不变；超时返回 False。"""
    deadline = time.time() + timeout
    try:
        st = path.stat()
    except OSError:
        return False
    last = (st.st_size, int(st.st_mtime), time.time())
    step = max(2, min(15, settle or 5))
    while time.time() < deadline:
        await asyncio.sleep(step)
        try:
            st = path.stat()
        except OSError:
            return False
        cur = (st.st_size, int(st.st_mtime))
        if cur != (last[0], last[1]):
            last = (cur[0], cur[1], time.time())
            continue
        if time.time() - last[2] >= settle:
            return True
    return False


async def _enqueue(cfg: Optional[Dict[str, Any]], path: Path) -> Dict[str, Any]:
    """建 job 并把压缩包复制（优先硬链）进 incoming/。"""
    try:
        # 顺手清理过期工作区：自动采集也会产生 job，不能只靠网页上传那条路径清理
        try:
            await asyncio.to_thread(importer.cleanup_expired, cfg)
        except Exception:
            pass
        job = importer.create_job(cfg, origin="collect")
        paths = importer.job_paths(cfg, job["job_id"])
        target = paths["incoming"] / path.name
        try:
            os.link(path, target)          # 同盘硬链：瞬时、不占空间
        except OSError:
            await asyncio.to_thread(shutil.copy2, str(path), str(target))
        await import_store.create(cfg, job["job_id"], "collect")
        return {"ok": True, "job_id": job["job_id"]}
    except Exception as e:
        logger.warning(f"[字体采集] 投递失败 {path}: {type(e).__name__} {e}")
        return {"ok": False, "message": f"投递失败：{type(e).__name__} {e}"}


async def _process(cfg: Optional[Dict[str, Any]], binary: Path,
                   job_id: str, source: Optional[Path], *,
                   allow_cleanup: bool = True) -> Dict[str, Any]:
    """analyze →（auto_commit 时）commit → 调度索引重建。

    主库索引过期时（新增字体后还没重建），比对会把已有字体全判成「新增」→ 重复入库。
    所以这里检测到 `library.stale` 就先重建索引、再重新比对一次。
    """
    out: Dict[str, Any] = {"job_id": job_id, "source": str(source), "success": False,
                           "counts": {}, "committed": 0, "message": ""}
    try:
        report = await importer.analyze(cfg, binary, job_id, keep_extracted=True)
        if report.get("success") and (report.get("library") or {}).get("stale"):
            rebuilt = await importer.rebuild_now(cfg, binary)
            if rebuilt.get("success"):
                logger.info(f"[字体采集] {job_id} 主库索引已过期，重建后重新比对")
                out["reindexed"] = True
                report = await importer.analyze(cfg, binary, job_id, keep_extracted=True)

        out["success"] = bool(report.get("success"))
        out["counts"] = report.get("counts") or {}
        out["message"] = report.get("message", "")
        if not report.get("success"):
            return out
        if collect_mode(cfg) == "auto_commit":
            committed = await asyncio.to_thread(importer.commit, cfg, job_id, report)
            out["committed"] = int(committed.get("count") or 0)
            out["message"] = committed.get("message", "")
            if out["committed"]:
                # 连续导入的关键：只对「本批新增的那几个字体」做增量探测（秒级），
                # 把它们并入比对基线；全库重建交给 debounce，一批导入只重建一次。
                try:
                    from font_core import index_delta
                    await index_delta.refresh(cfg, binary, committed.get("paths") or [])
                except Exception as e:
                    logger.warning(f"[字体采集] 增量索引探测失败（下次分析会兜底）: {e}")
                importer.schedule_rebuild(cfg, binary)
                await import_store.save_commit(cfg, job_id, committed,
                                               committed.get("report") or report)
                logger.info(f"[字体采集] {job_id} 入库 {out['committed']} 个字体 → {committed.get('target')}")
                if allow_cleanup and source is not None and cleanup_after(cfg):
                    try:
                        source.unlink()
                        out["cleaned"] = True
                    except OSError as e:
                        logger.debug(f"[字体采集] 删除原包失败 {source}: {e}")
        return out
    except Exception as e:
        out["message"] = f"处理异常：{type(e).__name__} {e}"
        logger.warning(f"[字体采集] {job_id} 处理失败: {out['message']}")
        return out
