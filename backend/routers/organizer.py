from fastapi import APIRouter, HTTPException, Query, Body, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Dict, Any, List
import asyncio
import json
import uuid
from datetime import datetime

from organizer_core.file_explorer import FileExplorer
from organizer_core.renamer import Renamer
from organizer_core.organizer import Organizer
from config_manager import ConfigManager
from logger import log_audit
from task_history import start_task, log_task, finish_task

router = APIRouter(tags=["整理重命名"])

_background_tasks: Dict[str, Dict[str, Any]] = {}

class FileListRequest(BaseModel):
    path: str = "/"

class FileOperationRequest(BaseModel):
    src: str
    dst: str

class FilePathRequest(BaseModel):
    path: str

@router.post("/api/files/list", summary="列出目录文件")
async def list_files(request: FileListRequest):
    """
    浏览服务器目录，返回文件和文件夹列表。
    """
    try:
        data = FileExplorer.list_directory(request.path)
        return {"status": "success", "data": data}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="路径不存在")
    except PermissionError:
        raise HTTPException(status_code=403, detail="权限不足")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/files/delete", summary="删除文件或目录")
async def delete_file(request: FilePathRequest):
    try:
        FileExplorer.delete_item(request.path)
        log_audit("文件管理", "删除", f"删除了: {request.path}")
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/files/copy", summary="复制文件或目录")
async def copy_file(request: FileOperationRequest):
    try:
        FileExplorer.copy_item(request.src, request.dst)
        log_audit("文件管理", "复制", f"从 {request.src} 复制到 {request.dst}")
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/files/move", summary="移动/重命名文件或目录")
async def move_file(request: FileOperationRequest):
    try:
        FileExplorer.move_item(request.src, request.dst)
        log_audit("文件管理", "移动", f"从 {request.src} 移动到 {request.dst}")
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/files/info", summary="获取文件详情")
async def get_file_info(request: FilePathRequest):
    try:
        data = FileExplorer.get_file_info(request.path)
        return {"status": "success", "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class RenamePreviewRequest(BaseModel):
    rule_id: str
    result_data: Dict[str, Any] # 完整的识别结果

class BatchExecuteRequest(BaseModel):
    items: List[Dict[str, Any]]
    conflict_mode: str = "skip"

@router.post("/api/rename/preview", summary="重命名预览")
async def preview_rename(request: RenamePreviewRequest):
    """
    根据识别结果和指定的重命名规则，计算目标路径。
    """
    config = ConfigManager.get_config()
    rules = config.get("rename_rules", Renamer.get_default_rules())
    
    # 找到对应的规则
    rule = next((r for r in rules if r["id"] == request.rule_id), None)
    if not rule:
        return {"status": "error", "message": "规则未找到"}
        
    result_data = request.result_data
    # 判定是电影还是剧集
    # 优先看 category, 其次看 type, 最后看 season/episode
    final = result_data.get("final_result", {})
    cat = final.get("category")
    m_type = final.get("type") or result_data.get("raw_meta", {}).get("type")
    
    is_movie = False
    if cat == "电影" or m_type == "movie": is_movie = True
    elif cat == "剧集" or m_type == "tv": is_movie = False
    else:
        # Fallback: 如果有季/集号且不为0，视为剧集
        s = final.get("season")
        e = final.get("episode")
        if s or e: is_movie = False
        else: is_movie = True # 默认视为电影

    pattern = rule.get("movie_pattern" if is_movie else "tv_pattern")
    if not pattern:
        return {"status": "error", "message": "该类型未定义命名模板"}
        
    original_filename = final.get("filename") or result_data.get("filename") or "unknown.mkv"
    
    try:
        new_path = Renamer.format_path(result_data, pattern, original_filename)
        return {"status": "success", "new_path": new_path, "pattern_used": pattern}
    except Exception as e:
        return {"status": "error", "message": str(e)}

async def _background_task_runner(task: Dict[str, Any], dry_run: bool, task_id: str):
    """
    后台任务运行器：静默消耗生成器，更新任务状态。
    """
    task_name = task.get("name", "未命名")
    processed = 0
    skipped = 0
    errors = 0
    start_time = None
    
    try:
        import time
        start_time = time.time()
        
        _background_tasks[task_id] = {
            "task_id": task_id,
            "name": task_name,
            "status": "running",
            "dry_run": dry_run,
            "processed": 0,
            "started_at": datetime.now().isoformat()
        }
        await start_task(task_id, "整理", task_name)
        await log_task(task_id, f"🚀 开始执行整理任务: {task_name}")
        await log_task(task_id, f"📁 源: {task.get('source_dir')}")
        await log_task(task_id, f"🔧 模式: {'预览 (Dry Run)' if dry_run else '正式执行 (Move/Copy)'}")
        
        log_audit("整理", "后台启动", f"任务已转入后台运行: {task_name}", details={"task_id": task_id})
        
        async for msg in Organizer.run_task(task, dry_run, task_id):
            try:
                data = json.loads(msg) if isinstance(msg, str) else msg
                data_type = data.get("type")
                if data_type == "scan":
                    # 扫描目录较多时，仅在日志显示顶层路径，避免刷屏
                    pass
                elif data_type == "item":
                    status = data.get("status")
                    source = data.get("source", "")
                    filename = os.path.basename(source)
                    target = data.get("target", "")
                    title = data.get("title", "")
                    season = data.get("season", "")
                    episode = data.get("episode", "")
                    
                    if status in ["success", "preview"]:
                        processed += 1
                        _background_tasks[task_id]["processed"] = processed
                        
                        # 构建日志信息
                        if title and (season or episode):
                            # 有识别信息
                            episode_info = f"S{season}E{episode}" if season and episode else (f"S{season}" if season else f"E{episode}")
                            if target:
                                target_name = os.path.basename(target)
                                await log_task(task_id, f"✅ {title} {episode_info}\n   {filename} → {target_name}")
                            else:
                                await log_task(task_id, f"✅ {title} {episode_info}\n   {filename}")
                        else:
                            # 无识别信息，显示文件名
                            if target:
                                target_name = os.path.basename(target)
                                await log_task(task_id, f"✅ {filename} → {target_name}")
                            else:
                                await log_task(task_id, f"✅ {filename}")
                    elif status == "error":
                        errors += 1
                        await log_task(task_id, f"❌ {filename}: {data.get('msg', '')}", "ERROR")
                elif data_type == "skip":
                    skipped += 1
                    # await log_task(task_id, f"⏭️ 跳过: {os.path.basename(data.get('source', ''))} ({data.get('reason', '')})")
                elif data_type == "finish":
                    _background_tasks[task_id]["total"] = data.get("count", 0)
                    
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
                    
                    # 详细统计输出
                    await log_task(task_id, "──────────────────")
                    await log_task(task_id, f"📊 整理统计：")
                    await log_task(task_id, f"   ├ ✅ 成功：{processed}")
                    await log_task(task_id, f"   ├ ⏭️ 跳过：{skipped}")
                    if errors > 0:
                        await log_task(task_id, f"   └ ❌ 失败：{errors}")
                    else:
                        await log_task(task_id, f"   └ ❌ 失败：{errors}")
                    await log_task(task_id, "")
                    await log_task(task_id, f"⏱️ 总计耗时：{duration}")
                    await log_task(task_id, "──────────────────")
                    await log_task(task_id, f"🏁 扫描完成，共发现 {data.get('count', 0)} 个可整理项目")
            except: pass
        
        final_summary = f"🏁 整理结束: 成功 {processed}"
        if skipped > 0: final_summary += f" | 跳过 {skipped}"
        if errors > 0: final_summary += f" | 失败 {errors}"
        
        await log_task(task_id, final_summary)
        _background_tasks[task_id]["status"] = "completed"
        _background_tasks[task_id]["finished_at"] = datetime.now().isoformat()
        
        # 构建统计信息
        stats = {
            "success": processed,
            "skipped": skipped,
            "errors": errors
        }
        
        await finish_task(task_id, "completed", processed, stats)
        log_audit("整理", "后台完成", f"任务后台运行结束: {task_name}", details={"processed": processed, "skipped": skipped, "errors": errors})
        
    except Exception as e:
        await log_task(task_id, f"❌ 任务异常终止: {str(e)}", "ERROR")
        if task_id in _background_tasks:
            _background_tasks[task_id]["status"] = "error"
            _background_tasks[task_id]["error"] = str(e)
            _background_tasks[task_id]["finished_at"] = datetime.now().isoformat()
        await finish_task(task_id, "error", processed)
        log_audit("整理", "后台异常", f"任务后台运行中断: {str(e)}", level="ERROR", details={"task_id": task_id})

@router.post("/api/organize/start_background", summary="启动后台整理任务")
async def start_background_organize(request: Request, task: Dict[str, Any] = Body(...), dry_run: bool = Query(True)):
    """
    以静默后台模式启动整理任务，执行过程通过系统日志查看。
    """
    task_id = f"bg_{uuid.uuid4().hex[:8]}"
    asyncio.create_task(_background_task_runner(task, dry_run, task_id))
    return {"status": "success", "task_id": task_id, "message": "任务已在后台启动，您可以关闭此窗口。"}

@router.get("/api/organize/background_tasks", summary="获取后台任务列表")
async def list_background_tasks():
    """
    获取所有后台任务的状态。
    """
    return list(_background_tasks.values())

@router.delete("/api/organize/background_tasks/{task_id}", summary="删除后台任务记录")
async def delete_background_task(task_id: str):
    """
    删除已完成的后台任务记录。
    """
    if task_id in _background_tasks:
        task = _background_tasks[task_id]
        if task.get("status") == "running":
            raise HTTPException(status_code=400, detail="无法删除正在运行的任务")
        del _background_tasks[task_id]
        return {"status": "success", "message": "任务记录已删除"}
    raise HTTPException(status_code=404, detail="任务不存在")

@router.get("/api/organize/stop", summary="停止整理任务")
async def stop_organize(task_id: str):
    """
    通过任务 ID 强制停止正在运行的整理任务。
    """
    Organizer.stop_task(task_id)
    if task_id in _background_tasks:
        _background_tasks[task_id]["status"] = "stopped"
        _background_tasks[task_id]["finished_at"] = datetime.now().isoformat()
        processed = _background_tasks[task_id].get("processed", 0)
        await finish_task(task_id, "stopped", processed)
    return {"status": "success", "message": "已发送停止指令"}

@router.get("/api/organize/stream", summary="流式执行任务")
async def stream_organize(request: Request, task_id: str, dry_run: str = "true"):
    """
    实时推送整理进度（NDJSON 格式），适用于正式任务。
    """
    config = ConfigManager.get_config()
    tasks = config.get("organize_tasks", [])
    task = next((t for t in tasks if t["id"] == task_id), None)
    
    if not task:
        raise HTTPException(status_code=404, detail="任务未找到")
        
    is_dry = dry_run.lower() == "true"
    
    async def event_generator():
        try:
            async for data in Organizer.run_task(task, is_dry, task_id):
                if await request.is_disconnected():
                    log_audit("整理", "任务中断", f"检测到客户端连接断开，正在停止任务: {task_id}")
                    Organizer.stop_task(task_id)
                    break
                yield data
        except asyncio.CancelledError:
            log_audit("整理", "任务中断", f"任务流已被系统取消 (task_id: {task_id})")
            Organizer.stop_task(task_id)
        except Exception as e:
            log_audit("整理", "执行异常", f"任务流中断: {str(e)}", level="ERROR")
            yield json.dumps({"type": "error", "message": str(e)}) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")

@router.post("/api/organize/stream_adhoc", summary="流式执行临时任务")
async def stream_organize_adhoc(request: Request, task: Dict[str, Any] = Body(...), dry_run: bool = Query(True), task_id: str = Query(None)):
    """
    流式执行一次性的、不在配置列表中的整理任务。
    """
    if not task_id:
        task_id = str(uuid.uuid4())

    async def event_generator():
        try:
            async for data in Organizer.run_task(task, dry_run, task_id):
                if await request.is_disconnected():
                    log_audit("整理", "任务中断", f"临时任务客户端已断开: {task_id}")
                    Organizer.stop_task(task_id)
                    break
                yield data
        except asyncio.CancelledError:
            log_audit("整理", "任务中断", f"临时任务已被取消 (task_id: {task_id})")
            Organizer.stop_task(task_id)
        except Exception as e:
             yield json.dumps({"type": "error", "message": str(e)}) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")

@router.post("/api/organize/recalculate", summary="单项全流程重算")
async def recalculate_item(request: dict):
    """
    针对单个文件进行“识别+渲染”重算，用于修正预览效果。
    """
    filename = request.get("filename")
    task_config = request.get("task_config") # 包含 rule_id, anime_priority 等
    
    if not filename or not task_config:
        raise HTTPException(status_code=400, detail="缺少文件名或任务配置")
        
    # 1. 立即获取最新规则缓存
    all_cached = ConfigManager.get_cached_rules()
    config = ConfigManager.get_config()
    
    # 合并规则
    all_noise = config.get("custom_noise_words", []) + all_cached.get("noise", [])
    all_groups = config.get("custom_release_groups", []) + all_cached.get("groups", [])
    all_render = config.get("custom_render_words", []) + all_cached.get("render", [])
    
    from recognition.recognizer import MovieRecognizer
    # 2. 执行识别
    result_data, _ = await MovieRecognizer.recognize_full(
        filename, 
        all_noise=all_noise, 
        all_groups=all_groups, 
        api_key=config.get("tmdb_api_key", ""),
        anime_priority=task_config.get("anime_priority", True),
        all_render=all_render,
        force_filename=True # 修正时通常针对单个文件名
    )
    
    if not result_data.get("success"):
        return {"type": "error", "source": filename, "status": "error", "reason": "识别失败"}

    # 3. 计算路径
    # 找到对应的重命名规则
    rule_id = task_config.get("rule_id")
    rules = config.get("rename_rules", [])
    rule = next((r for r in rules if r["id"] == rule_id), None)
    
    if not rule:
        return {"type": "error", "source": filename, "status": "error", "reason": "规则未找到"}
        
    final = result_data.get("final_result", {})
    is_movie = final.get("category") == "电影"
    pattern = rule.get("movie_pattern" if is_movie else "tv_pattern")
    
    try:
        new_path = Renamer.format_path(result_data, pattern, final.get("filename", filename.split('/')[-1]))
        target_abs = task_config.get("target_dir", "").rstrip("/") + "/" + new_path
        
        # 返回与 NDJSON 流中一致 healthy 的 item 格式
        return {
            "type": "item",
            "source": filename,
            "target": target_abs,
            "status": "success",
            "meta": result_data # 携带完整元数据供前端 commit 使用
        }
    except Exception as e:
        return {"type": "error", "source": filename, "status": "error", "reason": str(e)}

async def _background_batch_runner(items: List[Dict[str, Any]], conflict_mode: str, task_id: str):
    """
    后台批处理运行器
    """
    try:
        log_audit("整理", "批处理后台启动", f"正式执行任务已转入后台，共 {len(items)} 项")
        async for _ in Organizer.execute_batch(items, conflict_mode, task_id):
            pass
        log_audit("整理", "批处理后台完成", "正式执行任务后台运行结束")
    except Exception as e:
        log_audit("整理", "批处理后台异常", f"正式执行中断: {str(e)}", level="ERROR")

@router.post("/api/organize/execute_background", summary="后台正式执行批处理")
async def batch_execute_background(body: BatchExecuteRequest, task_id: str = Query(None)):
    """
    将确认后的文件列表转入后台进行物理移动或复制。
    """
    if not task_id:
        task_id = f"bg_exec_{uuid.uuid4().hex[:8]}"
    
    asyncio.create_task(_background_batch_runner(body.items, body.conflict_mode, task_id))
    return {"status": "success", "task_id": task_id, "message": "正式执行已在后台启动。"}

@router.post("/api/organize/execute", summary="正式执行批处理")
async def batch_execute(request: Request, body: BatchExecuteRequest, task_id: str = Query(None)):
    """
    接收前端确认的列表，进行物理移动/复制，并实时推送结果。
    """
    if not task_id:
        task_id = str(uuid.uuid4())

    log_audit("整理", "批处理", f"开始执行批处理任务，共 {len(body.items)} 项", details=f"Conflict Mode: {body.conflict_mode}")
    
    async def event_generator():
        try:
            async for data in Organizer.execute_batch(body.items, body.conflict_mode, task_id):
                if await request.is_disconnected():
                    log_audit("整理", "任务中断", f"批处理连接断开，停止执行: {task_id}")
                    Organizer.stop_task(task_id)
                    break
                yield data
        except asyncio.CancelledError:
            log_audit("整理", "任务中断", f"批处理任务已被取消 (task_id: {task_id})")
            Organizer.stop_task(task_id)
        except Exception as e:
            yield json.dumps({"type": "error", "message": str(e)}) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")

# --- Organize History ---

@router.get("/api/organize/history", summary="获取整理历史")
async def get_organize_history(limit: int = 50, offset: int = 0):
    """
    分页查询已完成的文件整理记录。
    """
    from database import db
    from models import OrganizeHistory
    from sqlmodel import select

    async with db.session_scope():
        stmt = select(OrganizeHistory).order_by(OrganizeHistory.processed_at.desc()).offset(offset).limit(limit)
        return await db.all(OrganizeHistory, stmt)

@router.delete("/api/organize/history/clear", summary="清空整理历史")
async def clear_organize_history():
    """
    彻底清空数据库中的整理历史记录（不影响磁盘文件）。
    """
    from database import db
    from models import OrganizeHistory
    from sqlmodel import delete

    try:
        async with db.session_scope() as session:
            await session.execute(delete(OrganizeHistory))
            await session.commit()
        log_audit("整理", "历史清理", "用户清空了全部整理历史记录")
        return {"success": True, "message": "历史记录已清空"}
    except Exception as e:
        return {"success": False, "message": str(e)}

@router.delete("/api/organize/history/{history_id}", summary="删除单条整理历史")
async def delete_organize_history(history_id: int, delete_file: bool = Query(False)):
    """
    通过 ID 删除指定的整理记录。
    可选参数 delete_file: 是否同时物理删除对应的目标文件/目录。
    """
    from database import db
    from models import OrganizeHistory
    import os

    try:
        async with db.session_scope():
            history = await db.get(OrganizeHistory, history_id)
            if not history:
                raise HTTPException(status_code=404, detail="记录不存在")
            
            # 如果要求删除物理文件
            if delete_file:
                # 仅尝试删除源路径（原始文件，适用于 copy/link 模式后的清理）
                if history.source_path:
                    try:
                        if os.path.exists(history.source_path):
                            FileExplorer.delete_item(history.source_path)
                            log_audit("整理", "文件删除", f"通过历史记录删除了原始源文件: {history.source_path}")
                    except Exception as e:
                        log_audit("整理", "文件删除失败", f"尝试删除源文件 {history.source_path} 时出错: {str(e)}", level="ERROR")

            await db.delete(history)
            return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        return {"success": False, "message": str(e)}








