from fastapi import APIRouter, Request
import os
import asyncio
import logging
import json
import uuid

from strm.strm_generator import StrmGenerator
from config_manager import ConfigManager
from logger import log_audit
from notification import NotificationManager
from task_history import start_task, log_task, finish_task

router = APIRouter(prefix="/api/webhook", tags=["Webhook 回调"])
logger = logging.getLogger("Webhook")

async def process_cd2_notification(data: list, source: str = "webhook"):
    """
    内部处理函数，可由 Webhook 路由调用，也可由系统内部直接触发。
    """
    if not data:
        return 0
    
    task_id = f"webhook_{uuid.uuid4().hex[:8]}"
    await start_task(task_id, "Webhook联动", f"CD2 {source}")
    await log_task(task_id, f"🚀 收到 CD2 联动请求，共 {len(data)} 个事件")

    config = ConfigManager.get_config()
    strm_tasks = config.get("strm_tasks", [])
    
    all_clients = {c.get('id'): c for c in config.get("download_clients", []) if c.get("type") == "cd2"}

    processed_count = 0
    processing_tasks = []
    task_id_ref = task_id
    task_stats = {} # task_name -> count

    for item in data:
        action = item.get("action")
        file_path = item.get("source_file", "").split(':')[0]
        
        if not file_path:
            continue

        if action != "create":
            continue
            
        if str(item.get("is_dir", "")).lower() == "true":
            continue

        filename = os.path.basename(file_path)
        await log_task(task_id_ref, f"📥 事件: {filename}")
        log_audit("CD2联动", "收到事件", f"收到 CD2 文件变动通知", details=f"动作: {action} | 路径: {file_path}")

        matched = False
        clean_cloud_path = '/' + file_path.lstrip('/')

        for task in strm_tasks:
            if not task.get("webhook_enabled", True):
                continue
                
            src_root = task.get("source_path") or task.get("source_dir")
            if not src_root: continue

            client_id = task.get("cd2_client_id")
            client_conf = all_clients.get(client_id, {})
            if not client_id and len(all_clients) == 1:
                client_conf = list(all_clients.values())[0]

            mapping_root = (task.get("cd2_mapping_path") or client_conf.get("mount_path") or "").strip()
            mapping_root = mapping_root.rstrip('/')
            
            local_file_path = os.path.normpath(mapping_root + clean_cloud_path)
            
            is_match = local_file_path.startswith(os.path.normpath(src_root)) or clean_cloud_path.startswith(os.path.normpath(src_root))
            
            if is_match:
                from monitor import MonitorManager
                task_name = task.get('name', '未命名')
                task_stats[task_name] = task_stats.get(task_name, 0) + 1
                
                log_audit("CD2联动", "任务命中", f"匹配到 STRM 任务: {task_name}", details=f"本地路径: {local_file_path}")
                
                enqueued = MonitorManager.enqueue_file(task.get("id"), local_file_path)
                
                if enqueued:
                    await log_task(task_id_ref, f"✅ 匹配 [{task_name}] -> 已加入后台队列")
                    processed_count += 1
                else:
                    await log_task(task_id_ref, f"⚡ 匹配 [{task_name}] -> 正在实时处理...")
                    processing_tasks.append(StrmGenerator.process_single_file(local_file_path, task))
                    processed_count += 1

                matched = True
                break
        
        if not matched:
            await log_task(task_id_ref, f"⏭️ 未匹配任何任务: {filename}")
    
    if processing_tasks:
        try:
            results = await asyncio.gather(*processing_tasks, return_exceptions=True)
            valid_results = []
            for i, r in enumerate(results):
                if isinstance(r, Exception):
                    await log_task(task_id_ref, f"  ❌ 处理异常: {str(r)}", "ERROR")
                    log_audit("CD2联动", "处理异常", f"执行 STRM 任务时发生错误: {r}", level="ERROR")
                elif isinstance(r, dict):
                    valid_results.append(r)
                    status = r.get("status", "unknown")
                    rel_p = r.get("rel_path", "未知")
                    await log_task(task_id_ref, f"  ┗ 处理结果: {status} ({os.path.basename(rel_p)})")
                else:
                    await log_task(task_id_ref, f"  ⚠️ 未知返回类型: {type(r)}", "WARN")
            if valid_results:
                await NotificationManager.push_webhook_strm_notification(valid_results)
        except Exception as e:
            await log_task(task_id_ref, f"❌ 处理异常: {str(e)}", "ERROR")
            log_audit("CD2联动", "处理异常", f"执行 STRM 任务时发生错误: {e}", level="ERROR")
    
    # 汇总显示
    summary = f"🏁 完成，共处理 {processed_count} 个文件"
    if task_stats:
        task_info = ", ".join([f"{name}({count})" for name, count in task_stats.items()])
        summary += f" | 涉及任务: {task_info}"
    
    await log_task(task_id_ref, summary)
    await finish_task(task_id_ref, "completed", processed_count)
    return processed_count

@router.post("/cd2/file_notify{tail:path}", summary="CloudDrive2 文件变动回调")
async def cd2_webhook(request: Request, tail: str = ""):
    """
    接收来自外部 CD2 容器或本系统内部模拟的 Webhook 通知。
    """
    # 尝试获取 JSON 负载
    try:
        payload = await request.json()
    except:
        # 可能是 mount_notify 等不带 body 的请求
        query_params = dict(request.query_params)
        log_audit("CD2联动", "非数据通知", f"收到 CD2 信号 (无数据体)", details=f"后缀: {tail} | 参数: {query_params}")
        return {"status": "success", "message": "Notification received"}

    data = payload.get("data")
    if not data:
        return {"status": "ignored", "reason": "empty_data"}

    # 识别调用来源 (如果是 127.0.0.1 则是内部模拟，否则是外部 CD2)
    client_host = request.client.host if request.client else "unknown"
    source_desc = "原生 Webhook" if client_host not in ["127.0.0.1", "localhost"] else "内部监控"
    
    triggered = await process_cd2_notification(data, source_desc)
                
    return {"status": "success", "source": source_desc, "triggered": triggered}


@router.post("/emby", summary="Emby Webhook")
async def emby_webhook(request: Request):
    """
    接收 Emby 的 Webhook 通知。
    支持入库通知推送和删除事件通知。
    """
    try:
        # Emby 的 Webhook 格式有时是 multipart/form-data (payload 字段)
        content_type = request.headers.get("content-type", "")
        if "multipart/form-data" in content_type:
            form = await request.form()
            payload_str = form.get("payload")
            payload = json.loads(payload_str) if payload_str else {}
        else:
            payload = await request.json()
    except Exception as e:
        logger.error(f"Failed to parse Emby webhook: {e}")
        return {"status": "error", "reason": "invalid_payload"}

    event = payload.get("Event")
    item_title = payload.get("Item", {}).get("Name", "未知")
    logger.info(f"Received Emby event: {event} for {item_title}")

    if event == "library.new":
        log_audit("Webhook", "Emby入库", f"收到新媒体入库通知: {item_title}")
        # 异步执行通知，不阻塞响应
        asyncio.create_task(NotificationManager.push_library_new_notification(payload))
        return {"status": "success", "action": "notification_sent"}

    # 处理深度删除事件 (deep.delete)
    if event == "deep.delete":
        description = payload.get("Description", "")
        log_audit("Webhook", "Emby深度删除", f"收到深度删除通知: {item_title}")
        # 异步执行删除通知
        asyncio.create_task(NotificationManager.push_emby_delete_notification(payload))
        return {"status": "success", "action": "delete_notification_sent"}

    # 处理其他删除事件格式
    data = payload.get("data", [])
    if data and isinstance(data, list):
        delete_items = []
        for item in data:
            if item.get("action") == "delete":
                delete_items.append(item)
        
        if delete_items:
            log_audit("Webhook", "Emby删除", f"收到删除通知，共 {len(delete_items)} 项")
            # 异步执行删除通知
            asyncio.create_task(NotificationManager.push_emby_delete_notification(delete_items))
            return {"status": "success", "action": "delete_notification_sent"}

    return {"status": "ignored", "event": event}
