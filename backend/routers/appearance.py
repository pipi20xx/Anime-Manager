"""
高级外观设置 API
- 配置读写 (存入 config.json 的 appearance 字段)
- 背景图片上传/读取/删除
"""
import os
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
