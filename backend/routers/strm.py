from fastapi import APIRouter, HTTPException, Query, Body
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import os
import asyncio
import uuid
import json

from strm.strm_generator import StrmGenerator
from config_manager import ConfigManager
from logger import log_audit
from task_history import start_task, log_task, finish_task

router = APIRouter(prefix="/api/strm", tags=["虚拟库 (STRM)"])

class StrmConfig(BaseModel):
    source_path: str
    target_path: str
    content_prefix: Optional[str] = ""
    content_suffix: Optional[str] = ""
    url_encode: bool = False
    copy_meta: bool = False
    clean_target: bool = False
    clean_empty_dirs: bool = False
    overwrite: bool = False
    overwrite_strm: bool = False
    overwrite_meta: bool = False
    sync_mode: Optional[str] = "local" # local, tree_file
    tree_file_path: Optional[str] = ""
    process_interval: Optional[float] = 0

@router.get("/tasks", summary="获取任务列表")
async def get_strm_tasks():
    """
    返回系统已配置的所有 STRM 虚拟库生成任务。
    """
    config = ConfigManager.get_config()
    return config.get("strm_tasks", [])

@router.post("/preview", summary="预览内容生成")
async def strm_preview(config: StrmConfig):
    """
    根据给定的前缀、路径规则，模拟生成一个 .strm 文件的内部链接。
    """
    source_dir = config.source_path or "/data/media"
    sample_file = os.path.join(source_dir, "演示目录", "test.mkv")
    preview_content = StrmGenerator.calculate_strm_content(source_dir, sample_file, config.dict())
    return {
        "status": "success", 
        "sample_file": f"[虚拟示例] {sample_file}",
        "preview_content": preview_content
    }

@router.post("/execute", summary="执行同步任务")

async def strm_execute(config: StrmConfig):

    """

    立即开始执行 STRM 生成任务，支持流式进度返回。支持本地扫描和目录树文件两种模式。

    """

    task_dict = config.dict()

    log_audit("STRM", "手动", f"开始执行同步任务 (模式: {config.sync_mode}): {config.source_path}")

    return StreamingResponse(StrmGenerator.generate(task_dict), media_type="application/x-ndjson")



@router.post("/run/{task_id}", summary="启动特定任务")

async def run_specific_task(task_id: str):

    """

    通过任务 ID 触发一个预设的 STRM 同步任务，任务将在后台运行。

    """

    config = ConfigManager.get_config()

    tasks = config.get("strm_tasks", [])

    task = next((t for t in tasks if t.get("id") == task_id), None)

    if not task:

        raise HTTPException(status_code=404, detail="任务未找到")

    

    # 统一转换配置，确保格式正确

    gen_config = {

        "name": task.get("name"),

        "source_dir": task.get("source_dir") or task.get("source_path"),

        "target_dir": task.get("target_dir") or task.get("target_path"),

        "content_prefix": task.get("content_prefix", ""),

        "content_suffix": task.get("content_suffix", ""),

        "url_encode": bool(task.get("url_encode", False)),

        "copy_meta": bool(task.get("copy_meta", False)),

        "clean_target": bool(task.get("clean_target", False)),

        "clean_empty_dirs": bool(task.get("clean_empty_dirs", False)),

        "overwrite": bool(task.get("overwrite", False)),

        "overwrite_strm": bool(task.get("overwrite_strm", True)),

        "overwrite_meta": bool(task.get("overwrite_meta", False)),

                "cd2_mapping_path": task.get("cd2_mapping_path", ""),

                "sync_mode": task.get("sync_mode", "local"),

                "tree_file_path": task.get("tree_file_path", ""),

                "process_interval": float(task.get("process_interval", 0)),

                "force_refresh": bool(task.get("force_refresh", False))

            }

    
    task_id = f"strm_{uuid.uuid4().hex[:8]}"
    task_name = task.get("name", "STRM 同步")
    gen_config["task_id"] = task_id
    
    log_audit("STRM", "触发", f"后台启动任务: {task_name} (模式: {gen_config['sync_mode']})")
    asyncio.create_task(_strm_background_runner(gen_config, task_id, task_name))
    return {"status": "success", "task_id": task_id, "message": "任务已在后台启动"}

async def _strm_background_runner(config: Dict[str, Any], task_id: str, task_name: str):
    """STRM 后台任务包装器，集成任务历史记录"""
    processed = 0
    skipped = 0
    errors = 0
    meta_copied = 0
    meta_skipped = 0
    deleted = 0
    start_time = None
    
    try:
        import time
        start_time = time.time()
        
        await start_task(task_id, "STRM", task_name)
        await log_task(task_id, f"🚀 开始执行 STRM 同步: {task_name}")
        await log_task(task_id, f"📁 源: {config.get('source_dir') or config.get('source_path')}")
        await log_task(task_id, f"🔧 模式: {config.get('sync_mode', 'local')} | 覆盖: {config.get('overwrite_strm', True)}")
        
        async for msg in StrmGenerator.generate(config):
            try:
                data = json.loads(msg) if isinstance(msg, str) else msg
                msg_type = data.get("type")
                if msg_type == "item":
                    status = data.get("status")
                    source = data.get("source", "")
                    message = data.get("message", "")
                    
                    if status == "success":
                        if "STRM" in message:
                            processed += 1
                        elif "Meta" in message:
                            meta_copied += 1
                        await log_task(task_id, f"✅ {os.path.basename(source)}")
                    elif status == "skip":
                        if "STRM" in message:
                            skipped += 1
                        elif "Meta" in message:
                            meta_skipped += 1
                    elif status == "error":
                        errors += 1
                        await log_task(task_id, f"❌ {os.path.basename(source)}: {data.get('msg', '')}", "ERROR")
                    elif status == "deleted":
                        deleted += 1
                elif msg_type == "finish":
                    stats = data.get("stats", {})
                    strm_created = stats.get("strm_created", 0)
                    strm_skipped = stats.get("strm_skipped", 0)
                    meta_copied = stats.get("meta_copied", 0)
                    meta_skipped = stats.get("meta_skipped", 0)
                    deleted = stats.get("deleted", 0)
                    duration = stats.get("duration", "未知")
                    
                    total_files = strm_created + strm_skipped
                    
                    # 详细统计输出
                    await log_task(task_id, "──────────────────")
                    await log_task(task_id, f"📄 STRM 文件：")
                    await log_task(task_id, f"   ├ ✅ 新增：{strm_created}")
                    await log_task(task_id, f"   └ ⏭️ 跳过：{strm_skipped}")
                    await log_task(task_id, "")
                    await log_task(task_id, f"🖼️ 元数据文件：")
                    await log_task(task_id, f"   ├ ✅ 同步：{meta_copied}")
                    await log_task(task_id, f"   └ ⏭️ 跳过：{meta_skipped}")
                    if deleted > 0:
                        await log_task(task_id, "")
                        await log_task(task_id, f"🧹 清理冗余：{deleted}")
                    await log_task(task_id, "")
                    await log_task(task_id, f"⏱️ 总计耗时：{duration}")
                    await log_task(task_id, "──────────────────")
                    await log_task(task_id, f"🏁 扫描完成，共处理 {total_files} 个文件")
            except: pass
        
        # 计算耗时
        duration = "未知"
        if start_time:
            elapsed = time.time() - start_time
            if elapsed < 60:
                duration = f"{elapsed:.1f}秒"
            else:
                minutes = int(elapsed // 60)
                seconds = int(elapsed % 60)
                duration = f"{minutes}分{seconds}秒"
        
        final_summary = f"🏁 任务结束: 成功 {processed}"
        if skipped > 0: final_summary += f" | 跳过 {skipped}"
        if errors > 0: final_summary += f" | 失败 {errors}"
        
        await log_task(task_id, final_summary)
        
        # 构建统计信息
        stats = {
            "strm_created": processed,
            "strm_skipped": skipped,
            "meta_copied": meta_copied,
            "meta_skipped": meta_skipped,
            "deleted": deleted,
            "duration": duration,
            "success": processed,
            "skipped": skipped,
            "errors": errors
        }
        
        await finish_task(task_id, "completed", processed, stats)
        log_audit("STRM", "完成", f"任务执行完成: {task_name}", details={"processed": processed, "skipped": skipped, "errors": errors, "meta_copied": meta_copied, "deleted": deleted})
    except Exception as e:
        await log_task(task_id, f"❌ 任务异常终止: {str(e)}", "ERROR")
        await finish_task(task_id, "error", processed)
        log_audit("STRM", "异常", f"任务执行失败: {str(e)}", level="ERROR")
