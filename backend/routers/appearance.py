"""
高级外观设置 API
- 配置读写 (存入 config.json 的 appearance 字段)
- 背景图片上传/读取/删除
"""
import os
import time
import uuid
import logging
import asyncio
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from config_manager import ConfigManager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/appearance", tags=["appearance"])

APPEARANCE_DIR = os.path.join("data", "appearance")
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def _ensure_dir():
    os.makedirs(APPEARANCE_DIR, exist_ok=True)


@router.get("/config")
async def get_appearance_config():
    """获取外观配置"""
    config = ConfigManager.get_config()
    return config.get("appearance", {})


@router.put("/config")
async def update_appearance_config(payload: dict):
    """更新外观配置（合并写入）"""
    current_config = ConfigManager.get_config()
    current_appearance = current_config.get("appearance", {})

    # 深度合并
    def deep_merge(base: dict, override: dict) -> dict:
        result = base.copy()
        for k, v in override.items():
            # instances 和 pages 字段整体替换：前端每次都发送完整状态，
            # 深合并会导致已删除的 key 残留在配置中无法清除
            if k in ("instances", "pages"):
                result[k] = v
            elif k in result and isinstance(result[k], dict) and isinstance(v, dict):
                result[k] = deep_merge(result[k], v)
            else:
                result[k] = v
        return result

    merged = deep_merge(current_appearance, payload)
    ConfigManager.update_config({"appearance": merged})
    logger.info("外观配置已更新")
    return {"success": True, "appearance": merged}


@router.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    """上传背景图片"""
    await asyncio.to_thread(_ensure_dir)

    # 校验扩展名
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"不支持的文件格式: {ext}")

    # 读取内容并校验大小
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="文件大小超过 10MB 限制")

    # 生成唯一文件名
    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(APPEARANCE_DIR, filename)

    def _write_file():
        with open(filepath, "wb") as f:
            f.write(content)
    await asyncio.to_thread(_write_file)

    logger.info(f"外观图片已上传: {filename}")
    return {"success": True, "filename": filename}


@router.get("/image/{filename}")
async def get_image(filename: str):
    """读取背景图片"""
    filepath = os.path.join(APPEARANCE_DIR, filename)
    if not await asyncio.to_thread(os.path.exists, filepath):
        raise HTTPException(status_code=404, detail="图片不存在")
    return FileResponse(filepath)


@router.delete("/image/{filename}")
async def delete_image(filename: str):
    """删除背景图片"""
    filepath = os.path.join(APPEARANCE_DIR, filename)
    if not await asyncio.to_thread(os.path.exists, filepath):
        raise HTTPException(status_code=404, detail="图片不存在")

    await asyncio.to_thread(os.remove, filepath)

    # 清理配置中对该图片的引用
    config = ConfigManager.get_config()
    appearance = config.get("appearance", {})
    changed = False

    for section in ["global", "modal", "card"]:
        section_config = appearance.get(section, {})
        bg_key = "background_image"
        if section_config.get(bg_key) == filename:
            section_config[bg_key] = ""
            changed = True

    # 清理页面级背景及页面级组件覆盖中的引用
    pages = appearance.get("pages", {})
    for page_key, page_config in pages.items():
        if not isinstance(page_config, dict):
            continue
        if page_config.get("background_image") == filename:
            page_config["background_image"] = ""
            changed = True
        # 页面级组件覆盖（overrides）中的背景图片引用
        overrides = page_config.get("overrides", {})
        if isinstance(overrides, dict):
            for cat_key, cat_config in overrides.items():
                if isinstance(cat_config, dict) and cat_config.get("background_image") == filename:
                    cat_config["background_image"] = ""
                    changed = True

    # 清理实例级覆盖中的引用
    instances = appearance.get("instances", {})
    for inst_key, inst_config in instances.items():
        if not isinstance(inst_config, dict):
            continue
        for cat_key, cat_config in inst_config.items():
            if isinstance(cat_config, dict) and cat_config.get("background_image") == filename:
                cat_config["background_image"] = ""
                changed = True

    if changed:
        ConfigManager.update_config({"appearance": appearance})

    logger.info(f"外观图片已删除: {filename}")
    return {"success": True}


@router.get("/images")
async def list_images():
    """列出所有已上传的背景图片"""
    await asyncio.to_thread(_ensure_dir)

    def _list():
        images = []
        for f in sorted(os.listdir(APPEARANCE_DIR)):
            ext = os.path.splitext(f)[1].lower()
            if ext in ALLOWED_EXTENSIONS:
                filepath = os.path.join(APPEARANCE_DIR, f)
                images.append({
                    "filename": f,
                    "size": os.path.getsize(filepath),
                })
        return images
    return await asyncio.to_thread(_list)


# ── 壁纸代理 ──────────────────────────────────────────────
# 前端 WebGL 纹理加载需要 CORS 支持，loliapi.com 不提供 CORS 头，
# 通过后端代理获取图片并返回带 CORS 头的响应。

import hashlib
import httpx
from fastapi.responses import Response
from fastapi import Query

WALLPAPER_CACHE_DIR = os.path.join("data", "tmp", "wallpaper")

# 已知的随机壁纸 API 域名 —— 这些 URL 不变但每次请求返回不同图片
# 对这类源使用短时间缓存（30 秒），保证同一次页面加载中多个请求（CSS 背景、
# <img> 标签、WebGL 纹理、tone 分析）拿到同一张图片，但页面刷新后能获取新图
RANDOM_WALLPAPER_DOMAINS = {
    "loliapi.com",
    "www.loliapi.com",
    "api.loliapi.com",
    "random.iisu.cn",
    "api.dujin.org",
    "img.xjh.me",
    "random.52ecy.cn",
}

# 随机壁纸的短缓存时间（秒）—— 一次页面加载周期内多个请求共享同一张图
RANDOM_WALLPAPER_CACHE_TTL = 30
# 固定壁纸的长缓存时间（秒）
FIXED_WALLPAPER_CACHE_TTL = 3600


def _is_random_wallpaper_url(url: str) -> bool:
    """判断 URL 是否指向随机壁纸 API（URL 不变但每次返回不同图片）"""
    from urllib.parse import urlparse
    try:
        host = urlparse(url).hostname or ""
        return host.lower() in RANDOM_WALLPAPER_DOMAINS
    except Exception:
        return False


def _ensure_wallpaper_dir():
    os.makedirs(WALLPAPER_CACHE_DIR, exist_ok=True)


def _is_valid_image(data: bytes) -> bool:
    """校验数据是否为有效图片"""
    if not data or len(data) < 16:
        return False
    # 检查常见图片 magic bytes
    if data[:3] == b'\xff\xd8\xff':  # JPEG
        return True
    if data[:8] == b'\x89PNG\r\n\x1a\n':  # PNG
        return True
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':  # WebP
        return True
    if data[:6] in (b'GIF87a', b'GIF89a'):  # GIF
        return True
    return False


@router.get("/wallpaper_proxy")
async def proxy_wallpaper(
    url: str = Query("", description="要代理的壁纸 URL，为空时使用默认 loliapi 地址"),
    refresh: bool = Query(False, description="强制刷新（跳过缓存），用于随机壁纸 API"),
):
    """
    代理外部壁纸图片，解决 WebGL CORS 限制。
    不传 url 时默认使用 https://www.loliapi.com/acg/pc/

    缓存策略：
    - 随机壁纸 API（如 loliapi.com）：短缓存 30 秒。同一次页面加载中多个请求
      （CSS 背景、<img>、WebGL 纹理、tone 分析）共享同一张图片，但 30 秒后
      缓存过期，下次页面刷新能获取新图片。前端通过 _ts cache-buster 确保
      不同页面加载的 URL 不同。
    - 固定 URL 壁纸：长缓存 1 小时，减少带宽消耗。
    - refresh=True 可强制跳过缓存。
    """
    target_url = url.strip() if url.strip() else "https://www.loliapi.com/acg/pc/"
    if not target_url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="无效的 URL")

    is_random = _is_random_wallpaper_url(target_url)
    cache_ttl = RANDOM_WALLPAPER_CACHE_TTL if is_random else FIXED_WALLPAPER_CACHE_TTL
    skip_cache = refresh

    # 使用 URL hash 作为缓存 key
    url_hash = hashlib.md5(target_url.encode()).hexdigest()

    # 尝试读取缓存
    cached_files = []
    if not skip_cache:
        try:
            for f in os.listdir(WALLPAPER_CACHE_DIR):
                if f.startswith(url_hash):
                    cached_files.append(f)
        except FileNotFoundError:
            pass

        # 如果有缓存且未过期，直接返回
        if cached_files:
            cached_file = os.path.join(WALLPAPER_CACHE_DIR, cached_files[0])
            try:
                stat = os.stat(cached_file)
                age = time.time() - stat.st_mtime
                if age < cache_ttl:
                    def _read_cache():
                        with open(cached_file, "rb") as f:
                            return f.read()
                    cached = await asyncio.to_thread(_read_cache)
                    if cached and _is_valid_image(cached):
                        # 推断 content-type
                        ext = os.path.splitext(cached_files[0])[1].lower()
                        ct = {
                            ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                            ".png": "image/png", ".webp": "image/webp",
                            ".gif": "image/gif",
                        }.get(ext, "image/jpeg")
                        return Response(
                            content=cached,
                            media_type=ct,
                            headers={
                                "Cache-Control": f"public, max-age={cache_ttl}",
                                "Access-Control-Allow-Origin": "*",
                            },
                        )
            except (OSError, IOError):
                pass

    # 下载新图片
    await asyncio.to_thread(_ensure_wallpaper_dir)
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(target_url)
            if resp.status_code == 200 and _is_valid_image(resp.content):
                # 推断扩展名
                content_type = resp.headers.get("content-type", "image/jpeg")
                ext_map = {
                    "image/jpeg": ".jpg", "image/png": ".png",
                    "image/webp": ".webp", "image/gif": ".gif",
                }
                ext = ext_map.get(content_type, ".jpg")

                # 写入缓存（随机壁纸也缓存，但 TTL 更短）
                cache_filename = f"{url_hash}{ext}"
                cache_filepath = os.path.join(WALLPAPER_CACHE_DIR, cache_filename)

                # 清理同 hash 的旧缓存
                for old in cached_files:
                    try:
                        os.remove(os.path.join(WALLPAPER_CACHE_DIR, old))
                    except OSError:
                        pass

                def _write():
                    with open(cache_filepath, "wb") as f:
                        f.write(resp.content)
                await asyncio.to_thread(_write)

                return Response(
                    content=resp.content,
                    media_type=content_type,
                    headers={
                        "Cache-Control": f"public, max-age={cache_ttl}",
                        "Access-Control-Allow-Origin": "*",
                    },
                )
            else:
                raise HTTPException(status_code=502, detail="壁纸源返回无效数据")
    except httpx.RequestError as e:
        logger.warning(f"壁纸代理请求失败: {e}")
        raise HTTPException(status_code=502, detail=f"壁纸代理失败: {str(e)}")
