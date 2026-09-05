"""
空间回收调度任务 —— 编排层。

职责：
1. 读取系统配置中的空间回收规则
2. 遍历所有 QB 客户端，获取种子列表
3. 调用 space_cleanup 引擎进行分组和选择
4. 执行删除操作
5. 记录任务历史 + 发送通知

被 monitor.py 的 APScheduler 调用，也可由 router 手动触发。
"""
import asyncio
import uuid
import logging
import time
from typing import Dict, Any, List, Optional

from config_manager import ConfigManager
from clients.manager import ClientManager
from clients.qbittorrent import QBClient
from clients.space_cleanup import (
    group_torrents_by_path,
    select_torrents_for_deletion,
    format_size,
    GB,
)
from task_history import start_task, log_task, finish_task

logger = logging.getLogger("SpaceCleanup")

# 导入通知（延迟导入避免循环依赖）
async def _notify_space_cleanup(summary: Dict[str, Any]):
    """发送空间回收完成通知。"""
    try:
        from notification import notification_manager, Notification, NotificationEvent
        await notification_manager.send(Notification(
            event_type=NotificationEvent.RAW,
            title="💾 磁盘空间自动回收",
            message=(
                f"检查了 {summary.get('total_clients', 0)} 个客户端\n"
                f"触发规则: {summary.get('rules_triggered', 0)} 条\n"
                f"删除种子: {summary.get('total_deleted', 0)} 个\n"
                f"释放空间: {format_size(summary.get('total_freed_bytes', 0))}"
            ),
        ))
    except Exception as e:
        logger.warning(f"发送空间回收通知失败: {e}")


async def run_space_cleanup(
    task_id: Optional[str] = None,
    manual: bool = False,
    rule_index: Optional[int] = None,
) -> Dict[str, Any]:
    """
    执行空间回收任务。

    :param task_id: 外部传入的 task_id（手动触发时用），为 None 时自动生成
    :param manual: 是否为手动触发
    :param rule_index: 指定规则索引（从 0 开始），为 None 时执行所有规则
    :return: 汇总统计
    """
    config = ConfigManager.get_config()
    all_rules = config.get("space_cleanup_rules", [])
    enabled = config.get("space_cleanup_enabled", False)

    if not enabled and not manual:
        return {"skipped": True, "reason": "disabled"}

    if not all_rules:
        return {"skipped": True, "reason": "no_rules"}

    # ── 如果指定了 rule_index，只执行单条规则 ──
    if rule_index is not None:
        if rule_index < 0 or rule_index >= len(all_rules):
            return {"skipped": True, "reason": f"invalid rule_index: {rule_index}"}
        rules = [all_rules[rule_index]]
        single_rule_label = f"规则 #{rule_index + 1}"
    else:
        rules = all_rules
        single_rule_label = None

    # ── 创建任务记录 ──
    if not task_id:
        task_id = f"space_cleanup_{uuid.uuid4().hex[:8]}"

    await start_task(task_id, "空间回收", "磁盘空间自动清理")
    prefix = "🔧 [手动]" if manual else "🤖 [自动]"
    if single_rule_label:
        await log_task(task_id, f"{prefix} 开始磁盘空间回收 ({single_rule_label})")
    else:
        await log_task(task_id, f"{prefix} 开始磁盘空间回收检查")
    await log_task(task_id, f"📋 规则数量: {len(rules)}")
    await log_task(task_id, "──────────────────")

    client_configs = ClientManager.get_all_clients()
    total_deleted = 0
    total_freed = 0
    rules_triggered = 0
    qb_count = 0

    for conf in client_configs:
        try:
            client = ClientManager.get_client(conf.get("id"))
            if not client:
                continue

            if not isinstance(client, QBClient):
                continue

            qb_count += 1
            client_name = client.name

            # ── 获取种子列表 ──
            torrents = await asyncio.to_thread(client.get_torrents, "all")
            if not torrents:
                await log_task(task_id, f"📁 {client_name}: 无任务")
                continue

            await log_task(
                task_id,
                f"📁 {client_name}: {len(torrents)} 个种子，开始检查..."
            )

            # ── 分组统计（传入 client_id 以过滤规则） ──
            groups = group_torrents_by_path(torrents, rules, client_id=conf.get("id"))

            for group in groups:
                rule = group["rule"]
                rule_path = group["path"]
                max_gb = group["max_size_gb"]
                total_gb = group["total_size_gb"]
                over = group["over_limit"]

                if not over:
                    await log_task(
                        task_id,
                        f"  ✅ [{rule_path}] {total_gb} GB / {max_gb} GB — 未超限"
                    )
                    continue

                rules_triggered += 1
                over_gb = group["over_by_gb"]
                await log_task(
                    task_id,
                    f"  ⚠️ [{rule_path}] {total_gb} GB / {max_gb} GB — 超出 {over_gb} GB"
                )

                # ── 选择需要删除的种子 ──
                to_delete = select_torrents_for_deletion(group)
                if not to_delete:
                    await log_task(
                        task_id,
                        f"    ℹ️ 无可删除种子 (可能全部受保护或正在下载)"
                    )
                    continue

                delete_files = bool(rule.get("delete_files", True))

                await log_task(
                    task_id,
                    f"    🗑️ 计划删除 {len(to_delete)} 个种子 (删除文件: {'是' if delete_files else '否'})"
                )

                # ── 逐个删除 ──
                deleted_count = 0
                freed_bytes = 0

                for t in to_delete:
                    name = t.get("name", "Unknown")
                    size = int(t.get("size", 0) or t.get("total_size", 0) or 0)
                    hash_str = str(t.get("hash", "")).lower()
                    added_on = float(t.get("added_on", 0) or 0)

                    try:
                        success = await asyncio.to_thread(
                            client.delete_torrent, hash_str, delete_files=delete_files
                        )
                        if success:
                            deleted_count += 1
                            freed_bytes += size
                            await log_task(
                                task_id,
                                f"    ✅ 已删除: {name} ({format_size(size)})"
                            )
                        else:
                            await log_task(
                                task_id,
                                f"    ❌ 删除失败: {name}",
                                "ERROR"
                            )
                    except Exception as e:
                        await log_task(
                            task_id,
                            f"    ❌ 删除异常: {name} - {e}",
                            "ERROR"
                        )

                total_deleted += deleted_count
                total_freed += freed_bytes

                await log_task(
                    task_id,
                    f"    📊 本规则: 删除 {deleted_count} 个，释放 {format_size(freed_bytes)}"
                )

        except Exception as e:
            logger.error(f"检查客户端 {conf.get('name', '未知')} 失败: {e}")
            await log_task(
                task_id,
                f"❌ 检查 {conf.get('name', '未知')} 失败: {e}",
                "ERROR"
            )

    # ── 汇总 ──
    await log_task(task_id, "──────────────────")
    await log_task(
        task_id,
        f"🏁 空间回收完成: 检查 {qb_count} 个客户端, 触发 {rules_triggered} 条规则, "
        f"删除 {total_deleted} 个种子, 释放 {format_size(total_freed)}"
    )

    stats = {
        "total_clients": qb_count,
        "rules_triggered": rules_triggered,
        "total_deleted": total_deleted,
        "total_freed_bytes": total_freed,
        "total_freed_display": format_size(total_freed),
    }

    await finish_task(task_id, "completed", total_deleted, stats)

    # ── 发送通知 ──
    if total_deleted > 0:
        await _notify_space_cleanup(stats)

    logger.info(
        f"[空间回收] 完成: 删除 {total_deleted} 个种子, 释放 {format_size(total_freed)}"
    )

    return stats
