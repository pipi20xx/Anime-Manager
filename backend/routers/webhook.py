from fastapi import APIRouter, Request
import os
import asyncio
import logging
import json
import time
import uuid

from strm.strm_generator import StrmGenerator
from config_manager import ConfigManager
from logger import log_audit
from notification import notification_manager
from task_history import start_task, log_task, finish_task

router = APIRouter(prefix="/api/webhook", tags=["Webhook 回调"])
logger = logging.getLogger("Webhook")

# 同一文件事件去重：原生 Webhook 与内部 gRPC 监控（CD2监控）可能对同一文件各触发一次
_EVENT_DEDUP_WINDOW = 120  # 秒
_recent_events = {}

def _is_duplicate_event(file_path: str) -> bool:
    now = time.time()
    # 清理过期记录，防止无限增长
    if len(_recent_events) > 500:
        expired = [p for p, t in _recent_events.items() if now - t >= _EVENT_DEDUP_WINDOW]
        for p in expired:
            _recent_events.pop(p, None)
    last = _recent_events.get(file_path)
    _recent_events[file_path] = now
    return last is not None and now - last < _EVENT_DEDUP_WINDOW

async def process_cd2_notification(data: list, source: str = "webhook"):
    """
    内部处理函数，可由 Webhook 路由调用，也可由系统内部直接触发。
    返回 {"triggered": 命中并处理的文件数, "deduped": 被去重忽略的事件数}
    """
    if not data:
        return {"triggered": 0, "deduped": 0}
    
    valid_items = []
    skipped_dup_count = 0
    for item in data:
        action = item.get("action")
        file_path = item.get("source_file", "").split(':')[0]

        if not file_path:
            continue
        if action != "create":
            continue
        if str(item.get("is_dir", "")).lower() == "true":
            continue
        # 跳过 .strm 输出文件：它们存在于云目录时（历史残留或反向写入）会反复触发联动
        if file_path.lower().endswith(".strm"):
            continue
        # 同一文件事件去重：原生 Webhook 与内部监控对同一文件各触发一次时，只处理先到的
        if _is_duplicate_event(file_path):
            skipped_dup_count += 1
            log_audit("CD2联动", "去重", "重复事件已忽略（同一文件刚由另一链路触发过）", details=f"来源: {source} | 路径: {file_path}")
            logger.info(f"[CD2联动] 去重: {file_path} (来源: {source})")
            continue

        valid_items.append(item)
    
    if not valid_items:
        return {"triggered": 0, "deduped": skipped_dup_count}
    
    first_filename = os.path.basename(valid_items[0].get("source_file", "").split(':')[0])
    
    module_name = source if source.startswith("CD2") else f"CD2{source}"
    task_desc = f"[{module_name}] {first_filename}" if len(valid_items) == 1 else f"[{module_name}] 共 {len(valid_items)} 个事件"
    
    task_id = f"webhook_{uuid.uuid4().hex[:8]}"
    await start_task(task_id, "Webhook联动", task_desc)
    await log_task(task_id, f"🚀 收到 CD2 联动请求 (来源: {module_name})，共 {len(valid_items)} 个事件")

    config = ConfigManager.get_config()
    strm_tasks = config.get("strm_tasks", [])
    
    all_clients = {c.get('id'): c for c in config.get("download_clients", []) if c.get("type") == "cd2"}

    processed_count = 0
    enqueued_count = 0
    processing_tasks = []
    task_id_ref = task_id
    task_stats = {}

    for item in valid_items:
        file_path = item.get("source_file", "").split(':')[0]
        action = item.get("action")
        
        filename = os.path.basename(file_path)
        await log_task(task_id_ref, f"📥 事件: {filename}")
        await log_task(task_id_ref, f"   源路径: {file_path}")
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

                # gRPC 模式 (cd2_api)：直接使用云路径坐标系，处理器原生支持
                if task.get("sync_mode") == "cd2_api":
                    process_path = clean_cloud_path
                    path_label = "云路径"
                else:
                    process_path = local_file_path
                    path_label = "本地路径"

                log_audit("CD2联动", "任务命中", f"匹配到 STRM 任务: {task_name}", details=f"{path_label}: {process_path}")

                enqueued = MonitorManager.enqueue_file(task.get("id"), process_path, origin_task_id=task_id_ref, origin_desc=task_desc)

                if enqueued:
                    enqueued_count += 1
                    await log_task(task_id_ref, f"✅ 匹配任务: [{task_name}] -> 已加入后台队列")
                    await log_task(task_id_ref, f"   {path_label}: {process_path}")
                    processed_count += 1
                else:
                    await log_task(task_id_ref, f"🎯 匹配任务: [{task_name}]")
                    await log_task(task_id_ref, f"   {path_label}: {process_path}")
                    await log_task(task_id_ref, f"⏳ 开始处理...")
                    processing_tasks.append((task_name, process_path, task, StrmGenerator.process_single_file(process_path, task)))
                    processed_count += 1

                matched = True
                # 不 break：所有源目录匹配的任务都处理（与定时扫描/实时监控行为一致）

        if not matched:
            await log_task(task_id_ref, f"⏭️ 未匹配任何任务: {filename}")
            log_audit("CD2联动", "未匹配", f"⏭️ 未命中任何 STRM 任务: {filename}", details=f"路径: {file_path}", level="WARN")
    
    if processing_tasks:
        try:
            results = await asyncio.gather(*[t[3] for t in processing_tasks], return_exceptions=True)
            valid_results = []
            for i, r in enumerate(results):
                task_name, local_file_path, task_config = processing_tasks[i][0], processing_tasks[i][1], processing_tasks[i][2]
                if isinstance(r, Exception):
                    await log_task(task_id_ref, f"  ❌ 处理异常: {str(r)}", "ERROR")
                    log_audit("CD2联动", "处理异常", f"执行 STRM 任务时发生错误: {r}", level="ERROR")
                elif isinstance(r, dict):
                    target_root = task_config.get("target_dir") or task_config.get("target_path")
                    r["task_name"] = task_name
                    r["target_root"] = target_root
                    valid_results.append(r)
                    status = r.get("status", "unknown")
                    rel_p = r.get("rel_path", "未知")
                    
                    status_icon = {"success": "✅", "skipped": "⏭️", "error": "❌"}.get(status, "❓")
                    status_text = {"success": "成功", "skipped": "跳过", "error": "失败"}.get(status, status)
                    
                    full_strm_path = os.path.join(target_root, rel_p) if target_root else rel_p
                    
                    rel_dir = os.path.dirname(full_strm_path)
                    filename = os.path.basename(full_strm_path)
                    
                    if rel_dir:
                        await log_task(task_id_ref, f"  {rel_dir}")
                        await log_task(task_id_ref, f"       └── {filename}")
                    else:
                        await log_task(task_id_ref, f"  {filename}")
                    
                    await log_task(task_id_ref, f"  {status_icon} 处理结果: {status_text}")
                else:
                    await log_task(task_id_ref, f"  ⚠️ 未知返回类型: {type(r)}", "WARN")
            if valid_results:
                await notification_manager.notify_strm_webhook(valid_results)
        except Exception as e:
            await log_task(task_id_ref, f"❌ 处理异常: {str(e)}", "ERROR")
            log_audit("CD2联动", "处理异常", f"执行 STRM 任务时发生错误: {e}", level="ERROR")
    
    # 汇总显示
    summary = f"🏁 完成，共处理 {processed_count} 个文件"
    if task_stats:
        task_info = ", ".join([f"{name}({count})" for name, count in task_stats.items()])
        summary += f" | 涉及任务: {task_info}"
    if enqueued_count:
        summary += f" | 其中 {enqueued_count} 个已入队由对应任务异步处理"
    if skipped_dup_count:
        summary += f" | 去重忽略 {skipped_dup_count} 个重复事件"
    
    await log_task(task_id_ref, summary)
    await finish_task(task_id_ref, "completed", processed_count)
    return {"triggered": processed_count, "deduped": skipped_dup_count}

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

    return {"status": "success", "source": source_desc, "triggered": triggered.get("triggered", 0), "deduped": triggered.get("deduped", 0)}


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
        asyncio.create_task(notification_manager.notify_library_new(payload))
        return {"status": "success", "action": "notification_sent"}

    # 处理深度删除事件 (deep.delete)
    if event == "deep.delete":
        log_audit("Webhook", "Emby深度删除", f"收到深度删除通知: {item_title}")
        # 异步执行 CD2 联动删除（内含 TG 通知）
        asyncio.create_task(_handle_deep_delete_cd2(payload))
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
            asyncio.create_task(notification_manager.notify_emby_deleted(delete_items))
            return {"status": "success", "action": "delete_notification_sent"}

    return {"status": "ignored", "event": event}


# ---------------------------------------------------------------------------
# Emby 深度删除 → CD2 联动删除
# ---------------------------------------------------------------------------

def _parse_mount_paths(description: str) -> list:
    """从 Emby deep.delete 的 Description 字段中解析 Mount Paths。"""
    if not description or "Mount Paths:" not in description:
        return []
    section = description.split("Mount Paths:")[1].strip()
    paths = []
    for line in section.split('\n'):
        line = line.strip()
        if line:
            paths.append(line)
    return paths


def _convert_path_via_mappings(local_path: str, mappings: list) -> str | None:
    """
    根据用户自定义路径映射规则，将 Emby 发来的路径转换为 CD2 内部路径。
    遍历 mappings，找到第一个 from 前缀匹配的规则，替换为 to + 剩余路径。
    如果没有任何规则匹配，返回 None。
    """
    for rule in mappings:
        from_prefix = (rule.get("from") or "").strip()
        to_prefix = (rule.get("to") or "").strip()
        if not from_prefix:
            continue
        if local_path.startswith(from_prefix):
            remaining = local_path[len(from_prefix):]
            # 去掉开头多余的斜杠（to_prefix 已包含必要的斜杠时）
            while remaining.startswith("/"):
                remaining = remaining[1:]
            cd2_path = to_prefix + "/" + remaining if to_prefix else "/" + remaining
            # 规范化：确保以 / 开头，消除双斜杠
            if not cd2_path.startswith("/"):
                cd2_path = "/" + cd2_path
            cd2_path = cd2_path.replace("//", "/")
            # 处理末尾可能的斜杠
            if cd2_path != "/" and cd2_path.endswith("/"):
                cd2_path = cd2_path.rstrip("/")
            return cd2_path
    return None


def _infer_folder_path_from_cd2_paths(cd2_paths: list, item_path: str = "") -> str | None:
    """
    当 Item.Path 无法通过映射规则转换时，从已映射的 CD2 文件路径中推导文件夹路径。

    策略：
    1. 取所有 CD2 文件路径的公共父目录
    2. 如果提供了 item_path，用其末尾 1-2 级目录名在公共父目录上做验证/修正
    """
    import os

    if not cd2_paths:
        return None

    # 取所有路径的公共父目录
    def parent(path: str) -> str:
        return os.path.dirname(path)

    common = parent(cd2_paths[0])
    for p in cd2_paths[1:]:
        common = os.path.commonpath([common, parent(p)])
        if not common or common == "/":
            break

    if not common or common == "/":
        return None

    # 如果有 item_path，尝试用它的末尾几级目录名来验证 common
    if item_path:
        # item_path 例: /NVME/CSXF/BT/(2020)租借女友[tmdbid=96316]/Season 1
        # 取末尾 1~2 级目录名去匹配 common 的末尾
        item_parts = [p for p in item_path.strip("/").split("/") if p]
        for depth in (min(2, len(item_parts)), 1):
            tail = "/".join(item_parts[-depth:])
            if tail and common.endswith(tail):
                return common
        # 如果末尾不匹配，仍返回 common（可能是中间某级目录名不同）
        # 但用 item_path 最后一级目录名做一次修正尝试
        if item_parts:
            last_dir = item_parts[-1]
            # 检查 common 的最后一级是否和 item_path 的最后一级不同
            common_parts = [p for p in common.strip("/").split("/") if p]
            if common_parts and common_parts[-1] != last_dir:
                # 替换最后一级（可能是 Season 1 vs Season 01 之类的差异）
                # 但这种情况不常见，保守起见还是返回 common
                pass

    return common


async def _handle_deep_delete_cd2(payload: dict):
    """
    处理 Emby deep.delete 事件的 CD2 联动删除。
    
    流程：
    1. 检查 deep_delete 配置是否启用
    2. 解析 Description 中的 Mount Paths
    3. 通过自定义路径映射规则转换为 CD2 内部路径
    4. 根据 delete_preference 决定删除文件还是文件夹
    5. 调用 CD2 API 执行删除
    6. 全程记录到任务中心
    """
    import uuid as _uuid

    # ── 启动任务中心记录 ──
    item_title_raw = payload.get("Item", {}).get("Name", "未知")
    task_id = f"deep_delete_{_uuid.uuid4().hex[:8]}"
    task_desc = f"[深度删除联动] {item_title_raw}"
    await start_task(task_id, "深度删除联动", task_desc)

    try:
        config = ConfigManager.get_config()
        deep_delete_config = config.get("deep_delete", {})

        if not deep_delete_config.get("enabled", False):
            await log_task(task_id, "⚠️ 深度删除联动未启用，跳过")
            await finish_task(task_id, "skipped")
            return

        description = payload.get("Description", "")
        mount_paths = _parse_mount_paths(description)

        if not mount_paths:
            await log_task(task_id, "⚠️ Description 中未找到 Mount Paths，跳过", "WARN")
            logger.warning("[深度删除联动] Description 中未找到 Mount Paths，跳过")
            await finish_task(task_id, "skipped")
            return

        mappings = deep_delete_config.get("path_mappings", [])
        if not mappings:
            await log_task(task_id, "⚠️ 未配置路径映射规则，跳过", "WARN")
            logger.warning("[深度删除联动] 未配置路径映射规则，跳过")
            await finish_task(task_id, "skipped")
            return

        # 根据 delete_preference 决定删除策略
        preference = deep_delete_config.get("delete_preference", "files")
        item = payload.get("Item", {})
        is_folder = item.get("IsFolder", False)
        item_type = item.get("Type", "")

        await log_task(task_id, f"📦 作品: {item_title_raw}")
        await log_task(task_id, f"📋 Emby 原始信息:")
        await log_task(task_id, f"   • Type: {item_type}")
        await log_task(task_id, f"   • IsFolder: {is_folder}")
        await log_task(task_id, f"   • Mount Paths ({len(mount_paths)} 项):")
        for p in mount_paths:
            await log_task(task_id, f"     • {p}")

        # 路径转换
        cd2_paths = []
        skipped = []
        for local_path in mount_paths:
            cd2_path = _convert_path_via_mappings(local_path, mappings)
            if cd2_path:
                cd2_paths.append(cd2_path)
            else:
                skipped.append(local_path)

        if skipped:
            await log_task(task_id, f"⚠️ {len(skipped)} 个路径未匹配任何映射规则", "WARN")
            for p in skipped:
                await log_task(task_id, f"   ✗ {p}", "WARN")
            logger.warning(f"[深度删除联动] {len(skipped)} 个路径未匹配任何映射规则")

        if not cd2_paths:
            await log_task(task_id, "⚠️ 没有有效的 CD2 路径，跳过删除", "WARN")
            logger.warning("[深度删除联动] 没有有效的 CD2 路径，跳过删除")
            await finish_task(task_id, "skipped")
            return

        paths_to_delete = cd2_paths  # 默认删除 Mount Paths 中的文件
        delete_target_type = "文件"  # 标记删除的是文件还是文件夹，用于日志展示

        if preference == "folder":
            # 尝试推导出父文件夹路径进行删除
            item_path = item.get("Path", "")
            folder_cd2_path = None
            if item_path:
                folder_cd2_path = _convert_path_via_mappings(item_path, mappings)
            if folder_cd2_path:
                paths_to_delete = [folder_cd2_path]
                delete_target_type = "文件夹"
                await log_task(task_id, f"📁 文件夹模式: 将删除文件夹")
                await log_task(task_id, f"   → {folder_cd2_path}")
            else:
                # 映射失败，尝试从已映射的 CD2 文件路径推导文件夹路径
                inferred = _infer_folder_path_from_cd2_paths(cd2_paths, item_path)
                if inferred:
                    paths_to_delete = [inferred]
                    delete_target_type = "文件夹"
                    await log_task(task_id, f"📁 文件夹模式 (自动推导): 将删除文件夹")
                    await log_task(task_id, f"   → {inferred}")
                    logger.info(f"[深度删除联动] 文件夹模式: Item.Path 映射失败，自动推导文件夹: {inferred}")
                else:
                    await log_task(task_id, f"⚠️ Item Path '{item_path}' 未匹配映射规则且无法推导文件夹，回退到文件删除", "WARN")
                    logger.warning(f"[深度删除联动] Item Path 未匹配映射规则且无法推导，回退到文件删除")
        elif preference == "auto":
            if is_folder and item_type in ("Series", "Season"):
                item_path = item.get("Path", "")
                folder_cd2_path = None
                if item_path:
                    folder_cd2_path = _convert_path_via_mappings(item_path, mappings)
                if folder_cd2_path:
                    paths_to_delete = [folder_cd2_path]
                    delete_target_type = "文件夹"
                    await log_task(task_id, f"📁 自动模式 (Type={item_type}): 将删除文件夹")
                    await log_task(task_id, f"   → {folder_cd2_path}")
                else:
                    # 映射失败，尝试从已映射的 CD2 文件路径推导文件夹路径
                    inferred = _infer_folder_path_from_cd2_paths(cd2_paths, item_path)
                    if inferred:
                        paths_to_delete = [inferred]
                        delete_target_type = "文件夹"
                        await log_task(task_id, f"📁 自动模式 (Type={item_type}, 自动推导): 将删除文件夹")
                        await log_task(task_id, f"   → {inferred}")
                        logger.info(f"[深度删除联动] 自动模式: Item.Path 映射失败，自动推导文件夹: {inferred}")
                    elif item_path:
                        await log_task(task_id, f"⚠️ 自动模式: Item.Path '{item_path}' 未匹配映射规则且无法推导，回退到文件删除", "WARN")
                    else:
                        await log_task(task_id, f"⚠️ 自动模式: Item.Path 为空 (Type={item_type})且无法推导，回退到文件删除", "WARN")
            elif is_folder:
                # IsFolder=true 但 Type 不在 Series/Season 中，仍然标注为文件夹
                await log_task(task_id, f"ℹ️ 自动模式: IsFolder=true, Type={item_type}，按文件路径删除")

        # 获取 CD2 客户端
        from clients.manager import ClientManager
        cd2_conf = next((c for c in config.get("download_clients", []) if c.get("type") == "cd2"), None)
        if not cd2_conf:
            await log_task(task_id, "⚠️ 未找到已配置的 CD2 客户端，跳过", "WARN")
            logger.warning("[深度删除联动] 未找到已配置的 CD2 客户端，跳过")
            await finish_task(task_id, "skipped")
            return

        client = ClientManager.get_client(cd2_conf.get("id"))
        if not client:
            await log_task(task_id, "⚠️ CD2 客户端初始化失败，跳过", "WARN")
            logger.warning("[深度删除联动] CD2 客户端初始化失败，跳过")
            await finish_task(task_id, "skipped")
            return

        # 读取删除偏好配置
        permanent_delete = deep_delete_config.get("permanent_delete", False)
        notify_on_delete = deep_delete_config.get("notify_on_delete", True)

        # 执行删除
        item_title = payload.get("Item", {}).get("Name", "未知")
        action_text = "永久删除" if permanent_delete else "删除到回收站"

        # 日志排版：逐行展示路径（任务中心详细记录）
        await log_task(task_id, f"🔧 准备{action_text} {len(paths_to_delete)} 项{delete_target_type}:")
        for p in paths_to_delete:
            await log_task(task_id, f"   {'📁' if delete_target_type == '文件夹' else '📄'} {p}")
        # 系统日志简化：只输出概要，不输出路径列表
        logger.info(f"[深度删除联动] 准备{action_text} {len(paths_to_delete)} 项{delete_target_type}: {item_title}")

        success, msg = await asyncio.to_thread(
            client.delete_paths, paths_to_delete, permanent_delete
        )

        if success:
            await log_task(task_id, f"✅ {action_text}成功: {len(paths_to_delete)} 项{delete_target_type}")
            log_audit(
                "深度删除联动", "删除成功",
                f"CD2 联动{action_text}完成: {item_title} ({len(paths_to_delete)} 项{delete_target_type})",
            )
            logger.info(f"[深度删除联动] {action_text}成功: {item_title}, {len(paths_to_delete)} 项{delete_target_type}")
        else:
            await log_task(task_id, f"❌ {action_text}失败: {msg}", "ERROR")
            log_audit(
                "深度删除联动", "删除失败",
                f"CD2 联动{action_text}失败: {msg}",
                level="ERROR",
            )
            logger.error(f"[深度删除联动] {action_text}失败: {msg}")

        # 发送 TG 通知
        if notify_on_delete:
            try:
                await notification_manager.notify_deep_delete_cd2(
                    item_title=item_title,
                    success=success,
                    delete_mode=preference,
                    permanently=permanent_delete,
                    deleted_count=len(paths_to_delete),
                    deleted_paths=paths_to_delete,
                    error_msg=msg if not success else "",
                )
            except Exception as notify_err:
                await log_task(task_id, f"⚠️ 发送 TG 通知失败: {notify_err}", "WARN")
                logger.warning(f"[深度删除联动] 发送 TG 通知失败: {notify_err}")

        # 完成任务
        await finish_task(task_id, "completed" if success else "failed", len(paths_to_delete))

    except Exception as e:
        logger.error(f"[深度删除联动] 处理异常: {e}", exc_info=True)
        log_audit("深度删除联动", "异常", f"处理深度删除联动时发生错误: {e}", level="ERROR")
        try:
            await log_task(task_id, f"❌ 处理异常: {e}", "ERROR")
            await finish_task(task_id, "failed")
        except Exception:
            pass
