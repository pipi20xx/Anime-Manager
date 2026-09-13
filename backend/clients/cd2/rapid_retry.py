"""
CD2 秒传重试队列。

整理任务 local→CD2 开启秒传模式后，秒传未命中（网盘哈希库没有该文件）时
不真实上传，而是入队等待：网盘哈希库可能随后续他人上传而命中，
由后台定时任务按配置的间隔重试秒传；重试次数用尽后按模式决定
是否回退为真实上传（rapid_then_upload）或标记失败（rapid_only）。
"""
import asyncio
import logging
import os
from datetime import datetime, timedelta

from sqlmodel import select

from database import db
from logger import log_audit

logger = logging.getLogger(__name__)


class RapidUploadRetryManager:
    _processing = asyncio.Lock()

    # ---------- 入队 ----------
    @staticmethod
    async def enqueue(client_id: str, local_path: str, cloud_path: str,
                      action_type: str, rapid_mode: str,
                      retry_interval: int, max_retries: int,
                      meta: dict = None):
        """秒传未命中的文件加入重试队列（同一文件只保留一条待重试记录）"""
        from models import RapidUploadRetry
        now = datetime.now()
        async with db.session_scope():
            stmt = select(RapidUploadRetry).where(
                RapidUploadRetry.local_path == local_path,
                RapidUploadRetry.status.in_(["pending", "running"]),
            )
            existing = await db.first(RapidUploadRetry, stmt)
            if existing:
                # 整理任务本次运行刚发生的未命中也是一次真实尝试，计入次数（封顶于上限）
                existing.attempts = min((existing.attempts or 0) + 1, max_retries)
                existing.cloud_path = cloud_path
                existing.action_type = action_type
                existing.rapid_mode = rapid_mode
                existing.retry_interval = retry_interval
                existing.max_retries = max_retries
                if existing.attempts >= max_retries:
                    # 次数已用尽：安排立即处理，worker 将直接回退真实上传/放弃
                    existing.message = f"秒传次数已用尽（{existing.attempts}/{max_retries}），待回退处理"
                    existing.next_retry_at = now + timedelta(minutes=1)
                else:
                    existing.message = f"整理任务秒传未命中，已计入重试（第 {existing.attempts}/{max_retries} 次）"
                    existing.next_retry_at = now + timedelta(minutes=retry_interval)
                existing.meta = meta
                existing.updated_at = now
                await db.save(existing, audit=False)
            else:
                record = RapidUploadRetry(
                    client_id=client_id,
                    local_path=local_path,
                    cloud_path=cloud_path,
                    action_type=action_type,
                    rapid_mode=rapid_mode,
                    retry_interval=retry_interval,
                    max_retries=max_retries,
                    attempts=1,  # 首次未命中即第 1 次
                    next_retry_at=now + timedelta(minutes=retry_interval),
                    status="pending",
                    message=f"秒传未命中（第 1/{max_retries} 次）",
                    meta=meta,
                )
                await db.save(record, audit=False)
        log_audit("CD2秒传", "加入重试队列",
                  f"{local_path} → {cloud_path} (每 {retry_interval} 分钟重试一次，最多 {max_retries} 次)")

    # ---------- 定时轮询 ----------
    @classmethod
    async def run_due_jobs(cls):
        """扫描到期任务逐个重试（由 APScheduler 每分钟调度，单实例互斥）"""
        from models import RapidUploadRetry
        if not cls._processing.locked():
            async with cls._processing:
                await cls._run_due_jobs_unlocked()

    @classmethod
    async def _run_due_jobs_unlocked(cls):
        from models import RapidUploadRetry
        now = datetime.now()
        async with db.session_scope():
            stmt = select(RapidUploadRetry).where(
                RapidUploadRetry.status == "pending",
                RapidUploadRetry.next_retry_at <= now,
            )
            due_ids = [r.id for r in (await db.all(RapidUploadRetry, stmt)) or []]

        # 注：running 记录不在此处恢复——真实上传可能超过 30 分钟，
        # 进程中断遗留的 running 记录由启动时 recover_stale_running 统一复位

        for rid in due_ids:
            try:
                await cls._process(rid)
            except Exception as e:
                logger.error(f"秒传重试任务 {rid} 执行异常: {e}")
                await cls._mark(rid, status="pending",
                                message=f"重试执行异常: {e}",
                                next_retry_at=datetime.now() + timedelta(minutes=5))

    @classmethod
    async def recover_stale_running(cls):
        """启动时恢复：进程重启遗留的 running 记录全部复位为待重试（下次轮询即处理）"""
        from models import RapidUploadRetry
        async with db.session_scope():
            stmt = select(RapidUploadRetry).where(RapidUploadRetry.status == "running")
            rows = (await db.all(RapidUploadRetry, stmt)) or []
            now = datetime.now()
            for r in rows:
                r.status = "pending"
                r.message = "进程重启，已自动恢复重试"
                r.next_retry_at = now
                r.updated_at = now
                await db.save(r, audit=False)
        if rows:
            logger.info(f"[CD2秒传] 已恢复 {len(rows)} 条因重启中断的重试记录")

    # ---------- 单个任务处理 ----------
    @classmethod
    async def _process(cls, record_id: int):
        from models import RapidUploadRetry
        from clients.manager import ClientManager

        async with db.session_scope():
            record = await db.session.get(RapidUploadRetry, record_id)
            if not record or record.status != "pending":
                return
            record.status = "running"
            record.updated_at = datetime.now()
            await db.save(record, audit=False)
            # 拷贝标量字段，避免 session 关闭后访问 ORM 属性
            snap = {
                "client_id": record.client_id,
                "local_path": record.local_path,
                "cloud_path": record.cloud_path,
                "action_type": record.action_type,
                "rapid_mode": record.rapid_mode,
                "retry_interval": record.retry_interval,
                "max_retries": record.max_retries,
                "attempts": record.attempts,
                "meta": record.meta,
            }

        local_path = snap["local_path"]
        cloud_path = snap["cloud_path"]

        # 本地源文件已被移走/删除：任务失去意义
        if not os.path.exists(local_path):
            await cls._mark(record_id, status="failed", message="本地源文件已不存在")
            log_audit("CD2秒传", "失败", f"{local_path}: 本地源文件已不存在，取消重试")
            return

        client = ClientManager.get_client(snap["client_id"])
        if not client or (client.config or {}).get("type") != "cd2":
            await cls._mark(record_id, status="failed", message="CD2 客户端不存在或已删除")
            return
        if not client.logged_in:
            ok = await asyncio.to_thread(client.login)
            if not ok:
                await cls._reschedule(record_id, snap, "CD2 登录失败")
                return

        # 目标已存在（如之前真实上传已完成）：视为完成，仅做源文件收尾
        browser = client._file_browser
        if await asyncio.to_thread(browser.path_exists, cloud_path):
            await cls._finalize_success(record_id, snap, cloud_path, note="目标已存在")
            return

        attempts = snap["attempts"]

        # 次数已用尽（整理任务重复入队可能把计数顶到上限）：不再尝试秒传，直接按模式处理
        if attempts >= snap["max_retries"]:
            log_audit("CD2秒传", "回退上传",
                      f"{local_path}: 秒传次数已用尽（{attempts}/{snap['max_retries']}），不再尝试秒传")
            return await cls._fallback_or_giveup(record_id, snap, client, attempts)

        # 重试秒传：rapid_only 模式下服务端一要数据即取消
        from clients.cd2.remote_upload import RemoteUploadManager
        result = await asyncio.to_thread(
            RemoteUploadManager.get_instance().upload_local_file_sync,
            client._conn, local_path, cloud_path, None, "rapid_only",
        )

        if result.get("success"):
            await cls._finalize_success(record_id, snap, cloud_path)
            return

        if result.get("rapid_miss"):
            attempts = snap["attempts"] + 1
            if attempts < snap["max_retries"]:
                await cls._mark(record_id, attempts=attempts, status="pending",
                                message=f"第 {attempts}/{snap['max_retries']} 次秒传未命中",
                                next_retry_at=datetime.now() + timedelta(minutes=snap["retry_interval"]))
                log_audit("CD2秒传", "未命中",
                          f"{local_path}: 第 {attempts}/{snap['max_retries']} 次未命中，"
                          f"{snap['retry_interval']} 分钟后重试")
                return
            # 次数用尽
            snap["attempts"] = attempts
            return await cls._fallback_or_giveup(record_id, snap, client, attempts)

        # 其他上传错误（网络/服务端异常）：按普通失败重试
        await cls._reschedule(record_id, snap,
                              result.get("error") or result.get("status_text") or "上传失败")

    @classmethod
    async def _fallback_or_giveup(cls, record_id: int, snap: dict, client, attempts: int):
        """秒传次数用尽后的处理：回退真实上传（rapid_then_upload）或放弃（rapid_only）"""
        from clients.cd2.remote_upload import RemoteUploadManager
        local_path = snap["local_path"]
        cloud_path = snap["cloud_path"]

        if snap["rapid_mode"] == "rapid_then_upload":
            log_audit("CD2秒传", "回退上传", f"{local_path}: {attempts} 次秒传未命中，回退为真实上传")
            # 等待被取消的秒传会话从 CD2 上传列表中消失：取消后立刻对同路径
            # 发起新会话会被服务端忽略（任务不调度、无任何状态推送）
            for _ in range(12):
                found, _st, _m = RemoteUploadManager.get_instance()._query_upload_status(
                    client._conn, cloud_path)
                if not found:
                    break
                await asyncio.sleep(5)
            result = await asyncio.to_thread(
                RemoteUploadManager.get_instance().upload_local_file_sync,
                client._conn, local_path, cloud_path, None, "off",
            )
            if result.get("success"):
                await cls._finalize_success(record_id, snap, cloud_path,
                                            note=f"秒传 {attempts} 次未命中后真实上传")
                return
            await cls._mark(record_id, attempts=attempts, status="failed",
                            message=f"真实上传失败: {result.get('error') or result.get('status_text')}")
            return

        await cls._mark(record_id, attempts=attempts, status="failed",
                        message=f"秒传 {attempts} 次均未命中，已放弃（仅秒传模式）")
        from notification import notification_manager
        await notification_manager.notify_organize_failed(
            local_path, f"秒传 {attempts} 次均未命中，已放弃上传（仅秒传模式）")

    @classmethod
    async def _reschedule(cls, record_id: int, snap: dict, reason: str):
        """基础设施类错误：不计入秒传未命中次数，5 分钟后重试"""
        from models import RapidUploadRetry
        if snap["attempts"] >= snap["max_retries"]:
            await cls._mark(record_id, status="failed", message=f"多次尝试失败: {reason}")
            return
        await cls._mark(record_id, status="pending", message=f"暂未成功: {reason}",
                        next_retry_at=datetime.now() + timedelta(minutes=5))

    @classmethod
    async def _finalize_success(cls, record_id: int, snap: dict, cloud_path: str, note: str = None):
        """上传成功收尾：move 删源文件、写整理历史、触发 STRM webhook"""
        from models import RapidUploadRetry
        local_path = snap["local_path"]
        action_type = snap["action_type"]
        meta = snap["meta"] or {}

        # 删除本地源文件（cd2_move 语义；失败不回滚上传结果，仅记录）
        delete_error = None
        if action_type == "cd2_move":
            try:
                await asyncio.to_thread(os.remove, local_path)
                log_audit("CD2文件", "删除", f"秒传上传完成，已删除本地源文件: {local_path}")
            except Exception as e:
                delete_error = str(e)

        # 写/更新整理历史（仅视频文件）
        if meta.get("create_history"):
            await cls._save_history(meta, cloud_path, note)

        # 触发 CD2 媒体库刷新 webhook（与整理成功路径一致）
        if meta.get("create_history"):
            try:
                from organizer_core.processor import FileProcessor
                asyncio.create_task(FileProcessor._simulate_cd2_webhook(cloud_path))
            except Exception as e:
                logger.warning(f"触发 CD2 webhook 失败: {e}")

        async with db.session_scope():
            record = await db.session.get(RapidUploadRetry, record_id)
            if record:
                record.status = "done"
                record.message = note or "秒传成功"
                if delete_error:
                    record.message += f"（删除本地源文件失败: {delete_error}）"
                record.updated_at = datetime.now()
                await db.save(record, audit=False)

        log_audit("CD2秒传", "完成", f"{local_path} → {cloud_path}" + (f" ({note})" if note else ""))

    @staticmethod
    async def _save_history(meta: dict, cloud_path: str, note: str = None):
        """按 source_path 去重写出完整的成功整理历史"""
        from models import OrganizeHistory
        final = meta.get("final") or {}
        task = meta.get("task") or {}
        history = OrganizeHistory(
            source_path=meta.get("source_path"),
            target_path=cloud_path,
            source_via="local", target_via="cd2",
            filename=meta.get("filename"),
            tmdb_id=str(final.get("tmdb_id")) if final.get("tmdb_id") else None,
            title=final.get("title"), season=final.get("season"),
            episode=str(final.get("episode")) if final.get("episode") else None,
            media_type=final.get("category"),
            action_type=meta.get("action_type"),
            file_size=final.get("file_size"),
            resolution=final.get("resolution"),
            team=final.get("team"),
            video_encode=final.get("video_encode"),
            year=str(final.get("year")) if final.get("year") else None,
            status="success",
            message=note,
            rule_id=task.get("rule_id"),
            source_dir=task.get("source_dir"),
            target_dir=task.get("target_dir"),
            overwrite_mode=task.get("overwrite_mode"),
            check_emby_exists=task.get("check_emby_exists", False),
            calculate_hash=task.get("calculate_hash", False),
            clean_empty_dir=task.get("clean_empty_dir", False),
            trigger_strm=task.get("trigger_strm", False),
            task_id=meta.get("task_id"),
        )
        async with db.session_scope():
            stmt = select(OrganizeHistory).where(OrganizeHistory.source_path == history.source_path)
            existing = await db.first(OrganizeHistory, stmt)
            if existing:
                await db.delete(existing, audit=False)
            await db.save(history, audit=False)

    @staticmethod
    async def _mark(record_id: int, status: str = None, message: str = None,
                    attempts: int = None, next_retry_at: datetime = None):
        from models import RapidUploadRetry
        async with db.session_scope():
            record = await db.session.get(RapidUploadRetry, record_id)
            if not record:
                return
            if status is not None:
                record.status = status
            if message is not None:
                record.message = message
            if attempts is not None:
                record.attempts = attempts
            if next_retry_at is not None:
                record.next_retry_at = next_retry_at
            record.updated_at = datetime.now()
            await db.save(record, audit=False)
