"""
高级外观设置 API
- 配置读写 (存入 config.json 的 appearance 字段)
- 背景图片上传/读取/删除
- 壁纸管理（在线源 / 上传 / 历史，后台预取由 wallpaper_service 负责）
"""
import os
import uuid
import logging
import asyncio
from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response
from config_manager import ConfigManager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/appearance", tags=["外观与壁纸"])

APPEARANCE_DIR = os.path.join("data", "appearance")
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def _ensure_dir():
    os.makedirs(APPEARANCE_DIR, exist_ok=True)


@router.get("/config", summary="获取外观配置")
async def get_appearance_config():
    """获取外观配置"""
    config = ConfigManager.get_config()
    return config.get("appearance", {})


@router.put("/config", summary="更新外观配置（合并写入）")
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


@router.post("/upload", summary="上传背景图片")
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


@router.get("/image/{filename}", summary="读取背景图片")
async def get_image(filename: str):
    """读取背景图片"""
    filepath = os.path.join(APPEARANCE_DIR, filename)
    if not await asyncio.to_thread(os.path.exists, filepath):
        raise HTTPException(status_code=404, detail="图片不存在")
    return FileResponse(filepath)


@router.delete("/image/{filename}", summary="删除背景图片")
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


@router.get("/images", summary="列出所有已上传的背景图片")
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


# ── 壁纸管理 ───────────────────────────────────────────────
# 完整的壁纸管理系统（按访问设备分电脑端 pc / 移动端 mobile 两套配置）：
# - 在线源：API 随机 / 自定义 URL（后端按设备分别后台预取，proxy 秒回就绪图）
# - 本地上传：手动上传的图（data/wallpaper，origin=upload，两端共用图库）
# - 历史壁纸：系统自动收录的历史使用图（data/wallpaper，origin=auto，按设备分离）
# - 配置持久化到 config.json 的 wallpaper.devices.<device> 字段

import httpx
from url_guard import safe_get, UnsafeURLError
from wallpaper_service import (
    DEFAULT_WALLPAPER_CONFIG,
    DEVICE_ANY,
    DEVICE_LABELS,
    SUPPORTED_DEVICES,
    WALLPAPER_API_SOURCES,
    WALLPAPER_DIR,
    describe_bad_image_response,
    find_latest_history_for_source,
    get_wallpaper_config,
    is_valid_image,
    list_history,
    list_uploads,
    notify_wallpaper_config_changed,
    read_local_image,
    record_history,
    remove_library_entry,
    resolve_device,
    resolve_wallpaper_target,
    save_wallpaper_config,
)


def _clear_profile_reference(field: str, filename: str) -> bool:
    """删除图库文件后，清理所有设备配置里对它的引用。"""
    cleared = False
    for device in SUPPORTED_DEVICES:
        cfg = get_wallpaper_config(device)
        if cfg.get(field) == filename:
            cfg[field] = ""
            save_wallpaper_config(device, cfg)
            cleared = True
    return cleared


@router.get("/wallpaper/sources", summary="获取可用的壁纸 API 源列表")
async def get_wallpaper_sources(device: str = Query("", description="访问设备：pc / mobile，留空返回全部")):
    """获取可用的壁纸 API 源列表（按设备过滤：设备专属源 + 两端通用源）"""
    if device in SUPPORTED_DEVICES:
        sources = [
            source for source in WALLPAPER_API_SOURCES
            if source.get("device") in (device, DEVICE_ANY)
        ]
    else:
        sources = WALLPAPER_API_SOURCES
    return {"sources": sources}


@router.get("/wallpaper/config", summary="获取某设备的壁纸配置")
async def get_wallpaper_config_route(
    request: Request,
    device: str = Query("", description="访问设备：pc / mobile；留空时按 User-Agent 推断"),
):
    """获取某设备的壁纸配置（另一设备不受影响）"""
    target = resolve_device(device, request.headers.get("user-agent", ""))
    return get_wallpaper_config(target)


@router.put("/wallpaper/config", summary="更新某设备的壁纸配置")
async def update_wallpaper_config_route(
    request: Request,
    payload: dict,
    device: str = Query("", description="访问设备：pc / mobile；留空时按 User-Agent 推断"),
):
    """更新某设备的壁纸配置（只写该设备的档案）"""
    target = resolve_device(device, request.headers.get("user-agent", ""))
    current = get_wallpaper_config(target)
    for key in DEFAULT_WALLPAPER_CONFIG:
        if key in payload:
            current[key] = payload[key]
    # 兼容旧字段 cache_ttl → refresh_interval
    if "cache_ttl" in payload and "refresh_interval" not in payload:
        try:
            current["refresh_interval"] = int(payload["cache_ttl"])
        except (TypeError, ValueError):
            pass
    save_wallpaper_config(target, current)
    notify_wallpaper_config_changed(target)
    logger.info(f"壁纸配置已更新（{DEVICE_LABELS.get(target, target)}）: {current}")
    return {"success": True, "config": current}


@router.get("/wallpaper/uploads", summary="列出手动上传的壁纸图片")
async def list_wallpaper_uploads():
    """列出手动上传的壁纸图片（两端共用图库）"""
    return await asyncio.to_thread(list_uploads)


@router.get("/wallpaper/history", summary="列出自动收录的历史壁纸图片")
async def list_wallpaper_history(device: str = Query("", description="访问设备：pc / mobile，留空返回全部")):
    """列出自动收录的历史壁纸图片（按设备过滤，保留通用条目）"""
    wanted = device if device in SUPPORTED_DEVICES else None
    return await asyncio.to_thread(list_history, wanted)


@router.get("/wallpaper/uploads/{filename}", summary="读取本地壁纸图片（上传/历史通用）")
async def get_wallpaper_upload(filename: str):
    """读取本地壁纸图片"""
    result = await asyncio.to_thread(read_local_image, filename)
    if result is None:
        raise HTTPException(status_code=404, detail="图片不存在")
    content, ct = result
    return Response(
        content=content,
        media_type=ct,
        headers={
            "Cache-Control": "public, max-age=3600",
            "Access-Control-Allow-Origin": "*",
        },
    )


@router.post("/wallpaper/upload", summary="上传壁纸图片")
async def upload_wallpaper(file: UploadFile = File(...)):
    """上传壁纸图片（写入 data/wallpaper，索引由 library 回填为 upload）"""
    await asyncio.to_thread(lambda: os.makedirs(WALLPAPER_DIR, exist_ok=True))

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"不支持的文件格式: {ext}")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="文件大小超过 10MB 限制")

    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(WALLPAPER_DIR, filename)

    def _write_file():
        with open(filepath, "wb") as f:
            f.write(content)
    await asyncio.to_thread(_write_file)

    logger.info(f"壁纸图片已上传: {filename}")
    return {"success": True, "filename": filename}


@router.delete("/wallpaper/uploads/{filename}", summary="删除已上传的壁纸图片")
async def delete_wallpaper_upload(filename: str):
    """删除已上传的壁纸图片"""
    filepath = os.path.join(WALLPAPER_DIR, filename)
    if not await asyncio.to_thread(os.path.exists, filepath):
        raise HTTPException(status_code=404, detail="图片不存在")

    await asyncio.to_thread(remove_library_entry, filename, "upload")

    # 如果有设备正在使用这张图片，清除所有设备配置里的引用
    if _clear_profile_reference("upload_filename", filename):
        notify_wallpaper_config_changed()

    logger.info(f"壁纸图片已删除: {filename}")
    return {"success": True}


@router.delete("/wallpaper/history/{filename}", summary="删除历史壁纸图片")
async def delete_wallpaper_history(filename: str):
    """删除历史壁纸图片"""
    filepath = os.path.join(WALLPAPER_DIR, filename)
    if not await asyncio.to_thread(os.path.exists, filepath):
        raise HTTPException(status_code=404, detail="图片不存在")

    await asyncio.to_thread(remove_library_entry, filename, "auto")

    if _clear_profile_reference("history_filename", filename):
        notify_wallpaper_config_changed()

    logger.info(f"历史壁纸已删除: {filename}")
    return {"success": True}


@router.get("/wallpaper_proxy", summary="代理壁纸图片（解决 WebGL CORS）")
async def proxy_wallpaper(
    request: Request,
    url: str = Query("", description="要代理的壁纸 URL，为空时使用配置中的壁纸源"),
    refresh: bool = Query(False, description="强制刷新（跳过就绪缓存）"),
    device: str = Query("", description="访问设备：pc / mobile；留空时按 User-Agent 推断"),
):
    """
    代理壁纸图片。

    - 本地图（上传/历史）：直接读 data/wallpaper 返回。
    - 在线源：按访问设备取配置，优先返回后台预取好的最新就绪图（秒开），
      只有预取尚未完成或显式传 url 时才实时下载（超时 10s）。
    """
    device = resolve_device(device, request.headers.get("user-agent", ""))
    cfg = get_wallpaper_config(device)
    explicit_url = url.strip()
    target_url = explicit_url if explicit_url else resolve_wallpaper_target(cfg, device)

    # 本地图模式
    if target_url.startswith("local:"):
        filename = target_url[6:]
        result = await asyncio.to_thread(read_local_image, filename)
        if result is None:
            raise HTTPException(status_code=404, detail="壁纸图片不存在")
        content, ct = result
        return Response(
            content=content,
            media_type=ct,
            headers={
                "Cache-Control": "no-store",
                "Access-Control-Allow-Origin": "*",
            },
        )

    if not target_url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="无效的 URL")

    # 在线源：优先返回该设备后台预取好的就绪图
    if not explicit_url and not refresh:
        ready = await asyncio.to_thread(find_latest_history_for_source, cfg, device)
        if ready:
            result = await asyncio.to_thread(read_local_image, ready.get("filename"))
            if result is not None:
                content, ct = result
                return Response(
                    content=content,
                    media_type=ct,
                    headers={
                        "Cache-Control": "no-store",
                        "Access-Control-Allow-Origin": "*",
                        "X-Wallpaper-Source": "prefetched",
                        "X-Wallpaper-Device": device,
                    },
                )

    # 回退：同步下载（刚启动、预取尚未完成，或显式指定 URL）
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await safe_get(client, target_url)
            if resp.status_code == 200 and is_valid_image(resp.content):
                content_type = resp.headers.get("content-type", "image/jpeg")
                if not explicit_url:
                    st = cfg.get("source_type", "api")
                    # 本地图缺失时 resolve_wallpaper_target 已回落在在线源
                    if st not in ("api", "url"):
                        st = "api"
                    source_id = cfg.get("api_source_id", "") if st == "api" else ""
                    source_url = target_url if st == "url" else ""
                    await asyncio.to_thread(
                        record_history, resp.content, st, source_id, source_url, content_type, device
                    )
                return Response(
                    content=resp.content,
                    media_type=content_type,
                    headers={
                        "Cache-Control": "no-store",
                        "Access-Control-Allow-Origin": "*",
                        "X-Wallpaper-Device": device,
                    },
                )
            else:
                detail = describe_bad_image_response(resp)
                logger.warning(f"[壁纸] 代理下载失败：{detail}")
                raise HTTPException(status_code=502, detail=f"壁纸源没有返回图片：{detail}")
    except UnsafeURLError as e:
        logger.warning(f"壁纸代理拒绝 URL: {e}")
        raise HTTPException(status_code=400, detail=f"URL 不被允许: {e}")
    except httpx.RequestError as e:
        logger.warning(f"壁纸代理请求失败: {e}")
        raise HTTPException(status_code=502, detail=f"壁纸代理失败: {str(e)}")
