"""assfonts 二进制定位、版本探测与在线更新（GitHub Release）。

二进制解析优先级（高 → 低）：
1. 配置 `font_manager.binary_path`（用户自定义路径）
2. `data/bin/assfonts`（网页「一键更新」下载的版本；位于 data 持久卷，重建镜像不丢）
3. `/app/bin/assfonts`（镜像内置，随仓库 backend/bin/assfonts 打进镜像）
4. `<repo>/backend/bin/assfonts`（本地开发直接跑 backend 时）

更新流程（apply_update）：下载 release 的 x86_64-Linux.tar.gz → 取出其中的 bin/assfonts
→ 校验 ELF 头与 e_machine(x86_64) → 试运行 `-h` 解析出版本号 → 原子替换到 data/bin/assfonts。
任一步失败都不会破坏现有二进制。
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import shutil
import stat
import subprocess
import tarfile
import tempfile
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

RELEASE_API = "https://api.github.com/repos/wyzdwdz/assfonts/releases/latest"
# 兜底链路：GitHub API 对未登录请求按 IP 限流（60 次/小时，NAS 公网 IP 很容易被打满），
# 而 Release 页面与资产下载不限流。releases/latest 会 302 到 /releases/tag/vX.Y.Z，
# 据此可推出资产地址（命名规则稳定：assfonts-<tag>-x86_64-Linux.tar.gz）。
RELEASE_LATEST_PAGE = "https://github.com/wyzdwdz/assfonts/releases/latest"
ASSET_URL_TEMPLATE = "https://github.com/wyzdwdz/assfonts/releases/download/{tag}/assfonts-{tag}-x86_64-Linux.tar.gz"
_TAG_IN_URL_RE = re.compile(r"/tag/(v?[0-9][0-9.]*)")
ASSET_RE = re.compile(r"^assfonts-v?([0-9][0-9.]*)-x86_64-Linux\.tar\.gz$")
VERSION_RE = re.compile(r"assfonts\s+v?([0-9][0-9.]*)", re.I)

LOCAL_BINARY = Path("data/bin/assfonts")
LOCAL_STATE = Path("data/bin/assfonts.state.json")

ELF_MAGIC = b"\x7fELF"
EM_X86_64 = 0x3E

_UA = "AnimeManager-FontManager/1.0"
_API_TIMEOUT = 30
_DOWNLOAD_TIMEOUT = 300


# ── 路径与探测 ────────────────────────────────────────────────

def _builtin_candidates() -> Tuple[Path, ...]:
    return (
        Path("/app/bin/assfonts"),
        Path(__file__).resolve().parent.parent / "bin" / "assfonts",
    )


def _looks_like_elf(path: Path) -> bool:
    """ELF 头 + x86_64 架构校验（不实际执行）。"""
    try:
        with open(path, "rb") as f:
            head = f.read(20)
        if len(head) < 20 or head[:4] != ELF_MAGIC:
            return False
        return int.from_bytes(head[18:20], "little") == EM_X86_64
    except OSError:
        return False


def probe_version(binary: Path, timeout: int = 10) -> Optional[str]:
    """执行 `assfonts -h` 并解析版本号；不可执行/输出异常返回 None。"""
    try:
        proc = subprocess.run(
            [str(binary), "-h"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
        )
        text = (proc.stdout or b"").decode("utf-8", errors="replace")
    except Exception:
        return None
    m = VERSION_RE.search(text)
    return m.group(1) if m else None


def resolve_binary(config: Optional[Dict[str, Any]] = None) -> Tuple[Optional[Path], str]:
    """按优先级解析可用的 assfonts 二进制。

    :return: (路径 或 None, 来源标识 custom/updated/builtin/dev/none)
    """
    cfg = (config or {}).get("font_manager", {}) if config else {}

    # 一律返回绝对路径：子进程 cwd 是字幕目录，相对路径会 exec 失败
    custom = str(cfg.get("binary_path") or "").strip()
    if custom:
        p = Path(custom).expanduser()
        if p.is_file() and os.access(str(p), os.X_OK):
            return p.resolve(), "custom"
        logger.warning(f"[字体管家] 配置的自定义 assfonts 路径不可用: {custom}")

    if LOCAL_BINARY.is_file() and os.access(str(LOCAL_BINARY), os.X_OK):
        return LOCAL_BINARY.resolve(), "updated"

    for cand in _builtin_candidates():
        if cand.is_file():
            try:
                if not os.access(str(cand), os.X_OK):
                    os.chmod(str(cand), 0o755)
            except Exception:
                pass
            if os.access(str(cand), os.X_OK):
                return cand.resolve(), "builtin"
    return None, "none"


def load_state() -> Dict[str, Any]:
    """读取上次更新记录（data/bin/assfonts.state.json）。"""
    try:
        with open(LOCAL_STATE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_state(data: Dict[str, Any]) -> None:
    try:
        LOCAL_STATE.parent.mkdir(parents=True, exist_ok=True)
        tmp = LOCAL_STATE.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, LOCAL_STATE)
    except Exception as e:
        logger.warning(f"[字体管家] 保存更新状态失败: {e}")


def binary_info(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """当前二进制状态（路径/来源/版本/大小），供 /status 展示。"""
    path, source = resolve_binary(config)
    state = load_state()
    if not path:
        return {
            "ready": False, "path": "", "source": "none", "version": "",
            "size": 0, "message": "未找到可执行的 assfonts 二进制（镜像内置文件缺失）",
            "updated_at": state.get("updated_at", ""),
        }
    version = probe_version(path)
    try:
        size = path.stat().st_size
    except OSError:
        size = 0
    source_label = {
        "custom": "自定义路径", "updated": "网页更新", "builtin": "镜像内置", "dev": "开发目录",
    }.get(source, source)
    return {
        "ready": bool(version),
        "path": str(path),
        "source": source,
        "source_label": source_label,
        "version": version or "",
        "size": size,
        "message": "" if version else "二进制存在但无法执行，请尝试重新下载更新",
        "updated_at": state.get("updated_at", "") if source == "updated" else "",
    }


# ── 网络（可选代理） ──────────────────────────────────────────

def _opener(config: Optional[Dict[str, Any]] = None):
    """构造 urllib opener：按配置决定是否走 http_proxy。"""
    cfg = (config or {}).get("font_manager", {}) if config else {}
    proxy = ""
    if cfg.get("proxy_for_update", True):
        proxy = str((config or {}).get("http_proxy") or "").strip()
    if proxy:
        handler = urllib.request.ProxyHandler({"http": proxy, "https": proxy})
    else:
        handler = urllib.request.ProxyHandler({})
    return urllib.request.build_opener(handler)


def _http_json(url: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    req = urllib.request.Request(url, headers={
        "User-Agent": _UA,
        "Accept": "application/vnd.github+json",
    })
    with _opener(config).open(req, timeout=_API_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _download(url: str, config: Optional[Dict[str, Any]] = None) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with _opener(config).open(req, timeout=_DOWNLOAD_TIMEOUT) as resp:
        return resp.read()


# ── 版本比较 ─────────────────────────────────────────────────

def _vtuple(ver: str) -> Tuple[int, ...]:
    parts = re.findall(r"\d+", ver or "")
    return tuple(int(p) for p in parts) or (0,)


def is_newer(latest: str, current: str) -> bool:
    a, b = _vtuple(latest), _vtuple(current)
    n = max(len(a), len(b))
    a = a + (0,) * (n - len(a))
    b = b + (0,) * (n - len(b))
    return a > b


# ── 检查更新 ─────────────────────────────────────────────────

def _latest_tag_from_page(config: Optional[Dict[str, Any]] = None) -> str:
    """不依赖 API 取最新 tag：跟随 releases/latest 的 302 跳转，从最终 URL 提取 /tag/vX.Y.Z。"""
    req = urllib.request.Request(RELEASE_LATEST_PAGE, headers={"User-Agent": _UA})
    with _opener(config).open(req, timeout=_API_TIMEOUT) as resp:
        final_url = resp.geturl() or ""
    m = _TAG_IN_URL_RE.search(final_url)
    if not m:
        raise RuntimeError(f"无法从 Release 页面解析版本号（最终地址：{final_url}）")
    return m.group(1)


def _asset_size(url: str, config: Optional[Dict[str, Any]] = None) -> int:
    """HEAD 探测资产大小；失败不致命（下载阶段还会校验 ELF）。"""
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": _UA})
        with _opener(config).open(req, timeout=_API_TIMEOUT) as resp:
            return int(resp.headers.get("Content-Length") or 0)
    except Exception:
        return 0


def _check_update_sync(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    info = binary_info(config)
    current = info.get("version") or ""
    result: Dict[str, Any] = {
        "current": current,
        "current_source": info.get("source", ""),
        "latest": "",
        "has_update": False,
        "asset_name": "",
        "download_url": "",
        "published_at": "",
        "notes": "",
        "size": 0,
        "error": "",
        "via": "",
    }

    # ── 主链路：GitHub API（能拿到资产清单与更新说明，但受 IP 限流）──
    api_error = ""
    try:
        data = _http_json(RELEASE_API, config)
        tag = str(data.get("tag_name") or "")
        result["latest"] = tag.lstrip("vV")
        result["published_at"] = str(data.get("published_at") or "")
        result["notes"] = str(data.get("body") or "")[:2000]
        for item in data.get("assets") or []:
            name = str(item.get("name") or "")
            if ASSET_RE.match(name):
                result["asset_name"] = name
                result["download_url"] = str(item.get("browser_download_url") or "")
                result["size"] = int(item.get("size") or 0)
                break
        result["via"] = "api"
        if not result["download_url"]:
            result["latest"] = ""  # 资产缺失，交给兜底链路重试
            api_error = "该 Release 未提供 x86_64-Linux 构建包"
    except urllib.error.HTTPError as e:
        if e.code == 403:
            api_error = "GitHub API 请求超限（未登录请求按 IP 限流）"
        else:
            api_error = f"GitHub API 返回 {e.code}"
    except Exception as e:
        api_error = f"无法访问 GitHub API：{type(e).__name__} {e}"

    # ── 兜底链路：Release 页面跳转 + 资产命名规则（不限流）──
    if not result["latest"] or not result["download_url"]:
        try:
            tag = _latest_tag_from_page(config)
            norm_tag = tag if tag.startswith("v") else f"v{tag}"
            url = ASSET_URL_TEMPLATE.format(tag=norm_tag)
            result["latest"] = norm_tag.lstrip("vV")
            result["asset_name"] = url.rsplit("/", 1)[-1]
            result["download_url"] = url
            result["size"] = _asset_size(url, config)
            result["via"] = "page"
            result["notes"] = result["notes"] or "（GitHub API 限流，已通过 Release 页面兜底获取版本信息）"
            api_error = ""
        except Exception as e:
            result["error"] = api_error or f"无法获取上游版本信息：{type(e).__name__} {e}"
            return result

    result["has_update"] = bool(result["latest"]) and (
        not current or is_newer(result["latest"], current)
    )
    return result


async def check_update(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return await asyncio.to_thread(_check_update_sync, config)


# ── 应用更新 ─────────────────────────────────────────────────

def _apply_update_sync(download_url: str, asset_name: str, expect_version: str,
                       config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    result: Dict[str, Any] = {"success": False, "version": "", "message": "", "path": ""}
    tmp_dir = Path(tempfile.mkdtemp(prefix="assfonts_update_", dir=str(LOCAL_BINARY.parent) if LOCAL_BINARY.parent.exists() else None))
    try:
        if not download_url:
            result["message"] = "缺少下载地址"
            return result

        blob = _download(download_url, config)
        if not blob:
            result["message"] = "下载内容为空"
            return result
        sha = hashlib.sha256(blob).hexdigest()

        tar_path = tmp_dir / "asset.tar.gz"
        tar_path.write_bytes(blob)

        member_name = ""
        extracted = tmp_dir / "assfonts"
        with tarfile.open(tar_path, "r:gz") as tf:
            target = None
            for m in tf.getmembers():
                if not m.isfile():
                    continue
                # 归档内路径形如 bin/assfonts
                if m.name.rstrip("/").endswith("assfonts"):
                    target = m
                    break
            if target is None:
                result["message"] = "压缩包内未找到 assfonts 可执行文件"
                return result
            member_name = target.name
            with tf.extractfile(target) as src, open(extracted, "wb") as dst:
                shutil.copyfileobj(src, dst)

        if not _looks_like_elf(extracted):
            result["message"] = "下载的二进制不是 x86_64 ELF 可执行文件，已放弃替换"
            return result

        os.chmod(extracted, 0o755)
        new_version = probe_version(extracted)
        if not new_version:
            result["message"] = "新二进制无法执行（-h 探测失败），已放弃替换"
            return result
        if expect_version and is_newer(expect_version, new_version):
            result["message"] = f"下载到的版本({new_version})低于预期({expect_version})，已放弃替换"
            return result

        LOCAL_BINARY.parent.mkdir(parents=True, exist_ok=True)
        os.replace(extracted, LOCAL_BINARY)
        os.chmod(LOCAL_BINARY, 0o755)

        _save_state({
            "version": new_version,
            "asset_name": asset_name or member_name,
            "sha256": sha,
            "size": len(blob),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        })
        result.update({"success": True, "version": new_version, "path": str(LOCAL_BINARY),
                       "message": f"已更新到 assfonts v{new_version}"})
        logger.info(f"[字体管家] assfonts 已更新至 v{new_version}（{asset_name}）")
        return result
    except Exception as e:
        logger.error(f"[字体管家] 更新 assfonts 失败: {type(e).__name__} {e}")
        result["message"] = f"更新失败：{type(e).__name__} {e}"
        return result
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


async def apply_update(download_url: str, asset_name: str, expect_version: str,
                       config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return await asyncio.to_thread(_apply_update_sync, download_url, asset_name, expect_version, config)
