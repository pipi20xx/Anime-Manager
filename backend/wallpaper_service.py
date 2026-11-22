"""
壁纸服务：按访问设备（电脑端 / 移动端）后台自动预取 + 历史图库索引 + 就绪图查找。

设计目标（解决「打开页面实时下载导致卡住」的问题）：
- 壁纸配置按访问设备拆成 pc / mobile 两份，互不影响：
  手机打开页面用竖屏源 + 移动端历史图，电脑打开页面用横屏源 + 电脑端历史图。
- 在线壁纸（API 随机 / 自定义 URL）由后台循环按各自的 refresh_interval 预取，
  下载成功后写入本地图库 data/wallpaper/（origin=auto），并登记到 library.json；
  历史条目带 device 标记，前端按设备过滤展示。
- /wallpaper_proxy 优先返回「当前设备 + 当前源最近一次预取好的图」，前端秒开，不再等网络。
- 手动上传的图（origin=upload）与自动收录的历史图（origin=auto）统一存放于
  data/wallpaper/，用 library.json 区分，前端分两个 TAB 展示。
- 兼容旧版本：旧配置只有一份扁平设置、旧历史图没有 device 字段。
  读取时按「已有设备档案 → 旧扁平配置」的顺序继承，并把旧历史图按来源源推断设备
  （loliapi_acg_pc → 电脑端，loliapi_acg_pe → 移动端，其余标记为通用）。

无状态、无循环依赖：本模块只依赖 config_manager / url_guard / httpx。
"""
import asyncio
import hashlib
import json
import logging
import os
import re
import time
import uuid
from typing import Dict, List, Optional, Tuple

import httpx

from config_manager import ConfigManager
from url_guard import safe_get, UnsafeURLError

logger = logging.getLogger(__name__)

# 统一本地图库目录：手动上传 + 自动收录历史图
WALLPAPER_DIR = os.path.join("data", "wallpaper")
LIBRARY_INDEX_PATH = os.path.join(WALLPAPER_DIR, "library.json")

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
MAX_FILE_SIZE = 10 * 1024 * 1024

# 历史图按设备分别计数，每个设备最多保留 HISTORY_LIMIT 张
# （清理最旧的条目，但不会清理当前配置引用与当前就绪图）
HISTORY_LIMIT = 50

# ── 设备维度 ──────────────────────────────────────────────
DEVICE_PC = "pc"
DEVICE_MOBILE = "mobile"
DEVICE_ANY = "any"  # 通用：旧版本迁移条目 / 跨设备共用
SUPPORTED_DEVICES = (DEVICE_PC, DEVICE_MOBILE)
DEVICE_LABELS = {DEVICE_PC: "电脑端", DEVICE_MOBILE: "移动端", DEVICE_ANY: "通用"}

# 预设壁纸 API 源列表 —— 前端按访问设备过滤展示
# device: pc 仅电脑端 / mobile 仅移动端 / any 两端通用（横屏竖屏均可）
WALLPAPER_API_SOURCES = [
    {
        "id": "loliapi_acg_pc",
        "name": "LoliAPI ACG (横屏)",
        "url": "https://www.loliapi.com/acg/pc/",
        "category": "acg",
        "orientation": "landscape",
        "device": DEVICE_PC,
        "is_random": True,
    },
    {
        "id": "loliapi_acg_pe",
        "name": "LoliAPI ACG (竖屏)",
        "url": "https://www.loliapi.com/acg/pe/",
        "category": "acg",
        "orientation": "portrait",
        "device": DEVICE_MOBILE,
        "is_random": True,
    },
    {
        "id": "loliapi_acg_auto",
        "name": "LoliAPI ACG (双端自适应)",
        "url": "https://www.loliapi.com/acg/",
        "category": "acg",
        "orientation": "any",
        "device": DEVICE_ANY,
        "is_random": True,
    },
    {
        "id": "loliapi_bg",
        "name": "LoliAPI 随机二次元",
        "url": "https://www.loliapi.com/bg/",
        "category": "acg",
        "orientation": "any",
        "device": DEVICE_ANY,
        "is_random": True,
    },
]

DEFAULT_WALLPAPER_CONFIG = {
    "source_type": "api",              # "api" | "url" | "upload" | "history"
    "api_source_id": "loliapi_acg_pc",
    "custom_url": "",
    "upload_filename": "",
    "history_filename": "",
    "refresh_interval": 60,            # 后台自动下载新图的间隔（秒），0 = 停止下载
    "display_mode": "latest",          # 显示方式："latest" 跟随最新 | "rotation" 图库轮播
    "rotation_interval": 60,           # 图库轮播间隔（秒），仅在 display_mode=rotation 时使用
    "rotation_include_history": True,  # 轮播范围：包含历史图库
    "rotation_include_uploads": False, # 轮播范围：包含上传壁纸
}

# 每个设备在没有任何历史配置时的默认源
DEFAULT_DEVICE_SOURCE = {
    DEVICE_PC: "loliapi_acg_pc",
    DEVICE_MOBILE: "loliapi_acg_pe",
}

_SOURCE_BY_ID = {source["id"]: source for source in WALLPAPER_API_SOURCES}

# 旧配置迁移：设备专属源在另一端没有现成映射时，换成本设备默认源
_SOURCE_COUNTERPART = {
    "loliapi_acg_pc": "loliapi_acg_pe",
    "loliapi_acg_pe": "loliapi_acg_pc",
}

# User-Agent 兜底推断（前端一般会显式传 device）
_MOBILE_UA_HINTS = ("android", "iphone", "ipad", "ipod", "mobile", "harmonyos", "windows phone")

# 预取触发事件：配置变更时 set，让循环立刻按新配置预取
_prefetch_wake = asyncio.Event()

# 各设备最近一次预取时间（monotonic 秒）；0 表示尽快预取
_last_prefetch_at: Dict[str, float] = {device: 0.0 for device in SUPPORTED_DEVICES}


# ── 设备解析 ──────────────────────────────────────────────

def normalize_device(device: Optional[str]) -> str:
    """把任意输入归一为受支持的设备标识，未知值按电脑端处理。"""
    return device if device in SUPPORTED_DEVICES else DEVICE_PC


def resolve_device(device: Optional[str], user_agent: str = "") -> str:
    """优先使用显式 device；缺失时按 User-Agent 推断，最后回落电脑端。"""
    if device in SUPPORTED_DEVICES:
        return device
    ua = (user_agent or "").lower()
    if any(hint in ua for hint in _MOBILE_UA_HINTS):
        return DEVICE_MOBILE
    return DEVICE_PC


def _ensure_wallpaper_dir():
    os.makedirs(WALLPAPER_DIR, exist_ok=True)


# ── 按设备读取/保存配置 ────────────────────────────────────

def _source_for_device(source_id: str, device: str) -> str:
    """把来源换成目标设备可用的源：通用源保持原样，设备专属源做对端映射。"""
    source = _SOURCE_BY_ID.get(source_id)
    fallback = DEFAULT_DEVICE_SOURCE.get(device, DEFAULT_WALLPAPER_CONFIG["api_source_id"])
    if source is None:
        return fallback
    if source.get("device") in (DEVICE_ANY, device):
        return source_id
    return _SOURCE_COUNTERPART.get(source_id, fallback)


def _profile_from_base(base: Dict, device: str) -> Dict:
    """从已有档案（或旧版扁平配置）推导某设备的完整壁纸配置。"""
    profile = {k: base[k] for k in DEFAULT_WALLPAPER_CONFIG if k in base}
    # 兼容旧版本：cache_ttl 迁移为 refresh_interval
    if "refresh_interval" not in profile and "cache_ttl" in base:
        try:
            profile["refresh_interval"] = int(base["cache_ttl"])
        except (TypeError, ValueError):
            pass
    merged = {**DEFAULT_WALLPAPER_CONFIG, **profile}
    merged["api_source_id"] = _source_for_device(merged.get("api_source_id", ""), device)
    return merged


def get_wallpaper_config(device: str = DEVICE_PC) -> Dict:
    """读取某设备的壁纸配置。

    优先取 wallpaper.devices[device]；缺失时从另一设备档案继承（源自动换端），
    再回落到旧版本扁平字段，保证升级后无需手动重配。
    """
    device = normalize_device(device)
    wallpaper = ConfigManager.get_config().get("wallpaper", {}) or {}
    stored = wallpaper.get("devices")
    devices = stored if isinstance(stored, dict) else {}

    if isinstance(devices.get(device), dict):
        return _profile_from_base(devices[device], device)

    base: Optional[Dict] = None
    for candidate in SUPPORTED_DEVICES:
        if isinstance(devices.get(candidate), dict):
            base = devices[candidate]
            break
    return _profile_from_base(base or wallpaper, device)


def get_all_wallpaper_configs() -> Dict[str, Dict]:
    """一次读出所有设备的壁纸配置。"""
    return {device: get_wallpaper_config(device) for device in SUPPORTED_DEVICES}


def save_wallpaper_config(device: str, wallpaper: Dict):
    """只保存某设备的壁纸配置，另一设备保持不变。

    旧版本的扁平字段保留在配置里但不参与读取，避免深合并时删键带来的兼容问题。
    """
    device = normalize_device(device)
    profile = {k: wallpaper[k] for k in DEFAULT_WALLPAPER_CONFIG if k in wallpaper}
    profile.pop("cache_ttl", None)

    current = ConfigManager.get_config().get("wallpaper", {}) or {}
    stored = current.get("devices")
    devices = {
        key: dict(value)
        for key, value in stored.items()
        if isinstance(value, dict)
    } if isinstance(stored, dict) else {}
    devices[device] = profile
    ConfigManager.update_config({"wallpaper": {"devices": devices}})


def resolve_wallpaper_target(cfg: Optional[Dict] = None, device: str = DEVICE_PC) -> str:
    """根据壁纸配置解析出最终要请求的目标 URL / 本地引用。"""
    wp = cfg or get_wallpaper_config(device)
    source_type = wp.get("source_type", "api")

    if source_type == "upload":
        filename = wp.get("upload_filename", "")
        if filename:
            return f"local:{filename}"
        source_type = "api"

    if source_type == "history":
        filename = wp.get("history_filename", "")
        if filename:
            return f"local:{filename}"
        source_type = "api"

    if source_type == "url":
        custom_url = (wp.get("custom_url", "") or "").strip()
        if custom_url:
            return custom_url
        source_type = "api"

    if source_type == "api":
        api_id = wp.get("api_source_id", DEFAULT_WALLPAPER_CONFIG["api_source_id"])
        for source in WALLPAPER_API_SOURCES:
            if source["id"] == api_id:
                return source["url"]
        fallback_id = DEFAULT_DEVICE_SOURCE.get(
            normalize_device(device), DEFAULT_WALLPAPER_CONFIG["api_source_id"]
        )
        return _SOURCE_BY_ID[fallback_id]["url"]

    return _SOURCE_BY_ID[DEFAULT_WALLPAPER_CONFIG["api_source_id"]]["url"]


def is_valid_image(data: bytes) -> bool:
    """校验数据是否为有效图片。"""
    if not data or len(data) < 16:
        return False
    if data[:3] == b'\xff\xd8\xff':  # JPEG
        return True
    if data[:8] == b'\x89PNG\r\n\x1a\n':  # PNG
        return True
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':  # WebP
        return True
    if data[:6] in (b'GIF87a', b'GIF89a'):  # GIF
        return True
    return False


def _compute_source_key(source_type: str, source_id: str, source_url: str) -> Optional[str]:
    """给在线源算一个稳定的 key，用于匹配「当前源最近一次预取的图」。"""
    if source_type == "api":
        return f"api:{source_id or ''}"
    if source_type == "url":
        url = (source_url or "").strip()
        return f"url:{hashlib.md5(url.encode()).hexdigest()}" if url else None
    return None


def _source_key_for_config(cfg: Dict) -> Optional[str]:
    st = cfg.get("source_type")
    if st == "api":
        return _compute_source_key("api", cfg.get("api_source_id", ""), "")
    if st == "url":
        return _compute_source_key("url", "", (cfg.get("custom_url", "") or "").strip())
    return None


def _ext_from_content_type(content_type: str) -> str:
    ct = (content_type or "").lower()
    if "png" in ct:
        return ".png"
    if "webp" in ct:
        return ".webp"
    if "gif" in ct:
        return ".gif"
    if "bmp" in ct:
        return ".bmp"
    return ".jpg"


def content_type_for_filename(filename: str) -> str:
    ext = os.path.splitext(filename or "")[1].lower()
    return {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".webp": "image/webp",
        ".gif": "image/gif", ".bmp": "image/bmp",
    }.get(ext, "image/jpeg")


# ── 图库索引 ──────────────────────────────────────────────

def _infer_device_from_source(source_id: str) -> str:
    """旧历史图没有 device 字段时，按来源 id 推断设备。"""
    sid = (source_id or "").lower()
    if sid.endswith("_pe") or "mobile" in sid or "portrait" in sid:
        return DEVICE_MOBILE
    if sid.endswith("_pc") or "desktop" in sid or "landscape" in sid:
        return DEVICE_PC
    return DEVICE_ANY


def _entry_device(entry: Dict) -> str:
    """读取条目设备；缺失或非法时按来源推断。"""
    device = entry.get("device")
    if device in (DEVICE_PC, DEVICE_MOBILE, DEVICE_ANY):
        return device
    return _infer_device_from_source(entry.get("source_id", ""))


def _load_library() -> List[Dict]:
    """读取 library.json，并为遗留条目回填 origin / device。"""
    _ensure_wallpaper_dir()
    entries: List[Dict] = []
    if os.path.exists(LIBRARY_INDEX_PATH):
        try:
            with open(LIBRARY_INDEX_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                entries = [e for e in data if isinstance(e, dict)]
        except Exception:
            logger.warning("[壁纸] 图库索引读取失败，将重建")
            entries = []

    changed = False
    # 旧版本历史图没有 device：按来源推断（通用源标记为 any，两端都可见）
    for entry in entries:
        if entry.get("device") not in (DEVICE_PC, DEVICE_MOBILE, DEVICE_ANY):
            entry["device"] = _infer_device_from_source(entry.get("source_id", ""))
            changed = True

    indexed = {e.get("filename") for e in entries}
    try:
        files = os.listdir(WALLPAPER_DIR)
    except FileNotFoundError:
        files = []
    for fname in files:
        ext = os.path.splitext(fname)[1].lower()
        if ext not in ALLOWED_EXTENSIONS or fname in indexed:
            continue
        filepath = os.path.join(WALLPAPER_DIR, fname)
        try:
            size = os.path.getsize(filepath)
            mtime = os.path.getmtime(filepath)
        except OSError:
            continue
        entries.append({
            "filename": fname,
            "size": size,
            "origin": "upload",
            "device": DEVICE_ANY,
            "source_type": "upload",
            "source_id": "",
            "source_url": "",
            "source_key": None,
            "created_at": mtime,
        })
        changed = True

    if changed:
        _save_library(entries)
    return entries


def _save_library(entries: List[Dict]):
    _ensure_wallpaper_dir()
    try:
        tmp = LIBRARY_INDEX_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)
        os.replace(tmp, LIBRARY_INDEX_PATH)
    except Exception as e:
        logger.warning(f"[壁纸] 图库索引写入失败: {e}")


def list_uploads() -> List[Dict]:
    """手动上传的壁纸列表（新→旧）。上传图库两端共用，选择哪张按设备分别保存。"""
    items = [
        {
            "filename": e.get("filename"),
            "size": e.get("size", 0),
            "created_at": e.get("created_at", 0),
        }
        for e in _load_library()
        if e.get("origin") == "upload"
    ]
    items.sort(key=lambda e: e.get("created_at", 0), reverse=True)
    return items


def list_history(device: Optional[str] = None) -> List[Dict]:
    """自动收录的历史壁纸列表（新→旧）。

    传入 device 时只返回该设备条目和「通用」条目；不传则返回全部。
    """
    wanted = device if device in SUPPORTED_DEVICES else None
    items = []
    for entry in _load_library():
        if entry.get("origin") != "auto":
            continue
        entry_device = _entry_device(entry)
        if wanted and entry_device not in (wanted, DEVICE_ANY):
            continue
        items.append({
            "filename": entry.get("filename"),
            "size": entry.get("size", 0),
            "created_at": entry.get("created_at", 0),
            "device": entry_device,
            "source_type": entry.get("source_type", ""),
            "source_id": entry.get("source_id", ""),
            "source_url": entry.get("source_url", ""),
        })
    items.sort(key=lambda e: e.get("created_at", 0), reverse=True)
    return items


def find_latest_history_for_source(
    cfg: Optional[Dict] = None,
    device: str = DEVICE_PC,
    library: Optional[List[Dict]] = None,
) -> Optional[Dict]:
    """查找某设备当前在线源最近一次预取好的图（即「就绪图」）。

    通用（any）条目也会参与匹配，保证升级前已缓存的图仍可秒开。
    """
    device = normalize_device(device)
    wp = cfg or get_wallpaper_config(device)
    key = _source_key_for_config(wp)
    if key is None:
        return None
    entries = library if library is not None else _load_library()
    matches = [
        e for e in entries
        if e.get("origin") == "auto"
        and e.get("source_key") == key
        and _entry_device(e) in (device, DEVICE_ANY)
    ]
    if not matches:
        return None
    matches.sort(key=lambda e: e.get("created_at", 0), reverse=True)
    return matches[0]


def _prune_library(library: List[Dict]) -> List[Dict]:
    """按设备限制历史图数量，超出 HISTORY_LIMIT 时清理最旧的。

    保护范围：所有设备配置里引用的上传图 / 历史图，以及每个设备的当前就绪图。
    """
    auto = [e for e in library if e.get("origin") == "auto"]
    if len(auto) <= HISTORY_LIMIT:
        return library

    configs = get_all_wallpaper_configs()
    protected = set()
    for cfg in configs.values():
        for field in ("upload_filename", "history_filename"):
            value = cfg.get(field)
            if value:
                protected.add(value)
    for device, cfg in configs.items():
        ready = find_latest_history_for_source(cfg, device, library=library)
        if ready:
            protected.add(ready.get("filename"))

    remove_names = set()
    for device in (*SUPPORTED_DEVICES, DEVICE_ANY):
        bucket = [e for e in auto if _entry_device(e) == device]
        excess = len(bucket) - HISTORY_LIMIT
        if excess <= 0:
            continue
        removable = sorted(
            (e for e in bucket if e.get("filename") not in protected),
            key=lambda e: e.get("created_at", 0),
        )
        for entry in removable[:excess]:
            name = entry.get("filename")
            if name:
                remove_names.add(name)

    for name in remove_names:
        filepath = os.path.join(WALLPAPER_DIR, name)
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except OSError:
            pass
    return [e for e in library if e.get("filename") not in remove_names]


def record_history(
    content: bytes,
    source_type: str,
    source_id: str,
    source_url: str,
    content_type: str,
    device: str = DEVICE_PC,
) -> Optional[str]:
    """把一张在线壁纸收录进历史图库（同设备内按内容 md5 去重），返回文件名。"""
    if not content or not is_valid_image(content):
        return None
    device = normalize_device(device)
    _ensure_wallpaper_dir()

    md5 = hashlib.md5(content).hexdigest()
    library = _load_library()
    for e in library:
        if e.get("origin") != "auto" or e.get("content_md5") != md5:
            continue
        # 只复用同一设备（或通用）的条目；另一设备的同图会单独收录，避免历史串端
        if _entry_device(e) not in (device, DEVICE_ANY):
            continue
        # 内容去重：刷新来源信息与时间，保证「最近使用」排序与当前源就绪图正确
        e["source_type"] = source_type
        e["source_id"] = source_id
        e["source_url"] = source_url
        e["source_key"] = _compute_source_key(source_type, source_id, source_url)
        e["created_at"] = time.time()
        _save_library(library)
        return e.get("filename")

    ext = _ext_from_content_type(content_type)
    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(WALLPAPER_DIR, filename)
    try:
        with open(filepath, "wb") as f:
            f.write(content)
    except OSError as e:
        logger.warning(f"[壁纸] 历史图写入失败: {e}")
        return None

    library.append({
        "filename": filename,
        "size": len(content),
        "origin": "auto",
        "device": device,
        "source_type": source_type,
        "source_id": source_id,
        "source_url": source_url,
        "source_key": _compute_source_key(source_type, source_id, source_url),
        "content_md5": md5,
        "created_at": time.time(),
    })
    library = _prune_library(library)
    _save_library(library)
    return filename


def remove_library_entry(filename: str, origin: str) -> bool:
    """删除图库中某个文件（文件 + 索引）。"""
    _ensure_wallpaper_dir()
    filepath = os.path.join(WALLPAPER_DIR, filename)
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
    except OSError:
        return False

    library = _load_library()
    library = [e for e in library if not (e.get("filename") == filename and e.get("origin") == origin)]
    _save_library(library)
    return True


def read_local_image(filename: str) -> Optional[Tuple[bytes, str]]:
    """读取本地图库图片，返回 (内容, content_type)。"""
    filepath = os.path.join(WALLPAPER_DIR, filename)
    if not os.path.exists(filepath):
        return None
    try:
        with open(filepath, "rb") as f:
            content = f.read()
    except OSError:
        return None
    if not content:
        return None
    return content, content_type_for_filename(filename)


# ── 后台预取 ──────────────────────────────────────────────

# 随机图源（loliapi 之类）一般是「302 跳到一个随机 CDN 上的随机图」：
# 单次抽签可能正好 404、或撞上 CDN 的反爬/人机校验页，所以失败再抽一次。
FETCH_ATTEMPTS = 2

# 各设备连续预取失败次数（只影响日志频率，不影响行为）
_fail_streak: Dict[str, int] = {device: 0 for device in SUPPORTED_DEVICES}


class WallpaperSourceError(Exception):
    """壁纸源没能给出可用图片。消息本身就是给日志 / 接口看的人话原因。"""


def _html_title(body: bytes) -> str:
    """从 HTML 响应里抠 <title>，用来判断对面回的是 404 页还是反爬校验页。"""
    try:
        text = (body or b"")[:4000].decode("utf-8", "replace")
    except Exception:
        return ""
    match = re.search(r"<title[^>]*>(.*?)</title>", text, re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    return re.sub(r"\s+", " ", match.group(1)).strip()[:60]


def describe_bad_image_response(resp) -> str:
    """把「不是可用图片」的响应翻译成人话：状态码 / 类型 / 体积 / 头部字节 / 网页标题 / 最终 URL。

    日志与接口报错共用，避免只抛一句「返回无效数据」让人没法排查。
    """
    body = resp.content or b""
    status = resp.status_code
    content_type = (resp.headers.get("content-type") or "").split(";")[0].strip() or "(无)"
    size = len(body)
    url = str(resp.url)
    head = " ".join(f"{byte:02x}" for byte in body[:12]) or "(空)"

    if status != 200:
        extra = ""
        if "html" in content_type.lower():
            title = _html_title(body)
            extra = f"，页面标题「{title}」" if title else ""
        return f"源站返回 HTTP {status}（{content_type}，{size} 字节{extra}）：{url}"

    if "html" in content_type.lower() or body[:1] == b"<":
        title = _html_title(body)
        hint = ("，像是 CDN 的反爬/人机校验页"
                if (b"__tst_status" in body or b"EO_Bot" in body) else "，像是错误页")
        return (f"返回的是网页而不是图片（{content_type}，{size} 字节"
                f"{'，标题「' + title + '」' if title else ''}{hint}）：{url}")

    if size == 0:
        return f"响应为空（{content_type}）：{url}"

    return f"响应不是可识别的图片（{content_type}，{size} 字节，头部 {head}）：{url}"


def _log_prefetch_failure(device: str, detail: str) -> None:
    """同一设备连续失败只在第 1 次与每 10 次打 WARNING，其余降 DEBUG（源站抽风时别刷屏）。"""
    streak = _fail_streak.get(device, 0) + 1
    _fail_streak[device] = streak
    text = f"[壁纸] {DEVICE_LABELS[device]}预取失败（连续 {streak} 次）：{detail}"
    if streak == 1 or streak % 10 == 0:
        logger.warning(text)
    else:
        logger.debug(text)


async def _download_online(url: str) -> Tuple[bytes, str]:
    """下载在线壁纸并校验，返回 (内容, content_type)；失败抛 `WallpaperSourceError`。

    失败会按 `FETCH_ATTEMPTS` 重抽（随机源换一次抽签常常就好了）；
    被安全校验拒绝（内网地址 / 协议不对）不重试，直接抛。
    """
    if not url.startswith(("http://", "https://")):
        raise WallpaperSourceError(f"不支持的地址（只允许 http/https）：{url}")

    problems: List[str] = []
    for _ in range(FETCH_ATTEMPTS):
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await safe_get(client, url)
        except UnsafeURLError as e:
            raise WallpaperSourceError(f"URL 被安全校验拒绝：{e}") from e
        except httpx.RequestError as e:
            problems.append(f"请求失败（{type(e).__name__}: {e}）")
            continue

        if resp.status_code == 200 and is_valid_image(resp.content):
            return resp.content, resp.headers.get("content-type", "image/jpeg")
        problems.append(describe_bad_image_response(resp))

    # 两次结果常常一模一样，去重后更好读
    raise WallpaperSourceError("；".join(dict.fromkeys(problems)))


async def prefetch_once(device: str = DEVICE_PC) -> bool:
    """按某设备的配置预取一次。本地图无需预取，直接视为就绪。"""
    device = normalize_device(device)
    cfg = get_wallpaper_config(device)
    target = resolve_wallpaper_target(cfg, device)

    if target.startswith("local:"):
        _fail_streak[device] = 0
        return True

    try:
        content, content_type = await _download_online(target)
    except WallpaperSourceError as e:
        _log_prefetch_failure(device, str(e))
        return False

    st = cfg.get("source_type", "api")
    # 本地图缺失时 resolve_wallpaper_target 已回落在在线源，这里同步修正来源类型
    if st not in ("api", "url"):
        st = "api"
    source_id = cfg.get("api_source_id", "") if st == "api" else ""
    source_url = target if st == "url" else ""
    filename = record_history(
        content, st, source_id, source_url, content_type, device=device
    )
    if filename:
        _fail_streak[device] = 0
        logger.info(f"[壁纸] {DEVICE_LABELS[device]}后台预取完成并收录历史: {filename}")
        return True
    logger.warning(f"[壁纸] {DEVICE_LABELS[device]}预取到的图片未能收录（历史图落盘失败）")
    return False


def _device_interval(cfg: Dict) -> int:
    """读取某设备的后台下载间隔；0 / 负值表示停止下载。"""
    try:
        return int(cfg.get("refresh_interval", 60))
    except (TypeError, ValueError):
        return 60


async def _prefetch_device(device: str):
    """预取单个设备；成功后按完成时间重新计时，异常只记录不打断循环。"""
    try:
        await prefetch_once(device)
    except Exception as e:
        logger.warning(f"[壁纸] {DEVICE_LABELS[device]}预取异常: {type(e).__name__}: {e}")
    finally:
        _last_prefetch_at[device] = time.monotonic()


async def wallpaper_prefetch_loop():
    """后台预取循环：各设备按自己的 refresh_interval 独立预取；0 = 停止下载。"""
    logger.info("[壁纸] 后台预取循环已启动（电脑端 / 移动端独立）")
    while True:
        now = time.monotonic()
        due: List[str] = []
        waits: List[float] = []
        for device in SUPPORTED_DEVICES:
            interval = _device_interval(get_wallpaper_config(device))
            if interval <= 0:
                continue
            interval = max(interval, 10)
            next_at = _last_prefetch_at.get(device, 0.0) + interval
            if next_at <= now:
                due.append(device)
            else:
                waits.append(next_at - now)

        if due:
            # 两端可能同时到期：并发预取，避免慢速源拖住另一台设备
            await asyncio.gather(*(_prefetch_device(device) for device in due))
            # 预取完立即重新评估，让另一台设备的到期时间不被顺延
            continue

        if not waits:
            # 两个设备都停止后台下载：仅等待配置变更后重新评估
            try:
                await _prefetch_wake.wait()
            finally:
                _prefetch_wake.clear()
            continue

        timeout = max(0.5, min(waits))
        try:
            await asyncio.wait_for(_prefetch_wake.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            pass
        finally:
            _prefetch_wake.clear()


def notify_wallpaper_config_changed(device: Optional[str] = None):
    """配置变更后调用：唤醒预取循环。

    指定 device 时只让该设备立即按新配置重新预取，避免牵连另一台设备的节奏。
    """
    targets = SUPPORTED_DEVICES if device is None else (normalize_device(device),)
    for target in targets:
        _last_prefetch_at[target] = 0.0
    try:
        _prefetch_wake.set()
    except RuntimeError:
        pass
