"""
通用事件 WebSocket 推送中心
仿照 LogBroadcaster 的 asyncio.Queue 发布-订阅模式，
用于向前端推送任务状态、服务状态等实时事件，替代前端轮询。
"""
import asyncio
import json
import logging
from typing import Set, Any

logger = logging.getLogger(__name__)


class EventBroadcaster:
    """通用事件 WebSocket 推送中心"""
    _subscribers: Set[asyncio.Queue] = set()

    @classmethod
    def subscribe(cls) -> asyncio.Queue:
        """订阅事件流，返回一个 asyncio.Queue"""
        q: asyncio.Queue = asyncio.Queue(maxsize=256)
        cls._subscribers.add(q)
        logger.debug(f"[EventBroadcaster] 新订阅者，当前连接数: {len(cls._subscribers)}")
        return q

    @classmethod
    def unsubscribe(cls, q: asyncio.Queue):
        """取消订阅"""
        cls._subscribers.discard(q)
        logger.debug(f"[EventBroadcaster] 订阅者离开，当前连接数: {len(cls._subscribers)}")

    @classmethod
    async def broadcast(cls, event_type: str, data: Any):
        """
        向所有订阅者推送一个事件。
        :param event_type: 事件类型，如 "background_tasks", "task_record", "services_status"
        :param data: 事件数据（会被 JSON 序列化）
        """
        if not cls._subscribers:
            return

        msg = json.dumps({"type": event_type, "data": data}, ensure_ascii=False, default=str)

        for q in list(cls._subscribers):
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                # 慢客户端：丢弃最旧的消息，放入最新的
                try:
                    q.get_nowait()
                    q.put_nowait(msg)
                except Exception:
                    pass
            except Exception as e:
                logger.warning(f"[EventBroadcaster] 推送失败: {e}")

    @classmethod
    async def broadcast_background_tasks(cls, tasks: Any):
        """推送后台整理任务列表"""
        await cls.broadcast("background_tasks", tasks)

    @classmethod
    async def broadcast_task_record(cls, record: Any):
        """推送单条任务记录变更"""
        await cls.broadcast("task_record", record)

    @classmethod
    async def broadcast_services_status(cls, status: Any):
        """推送服务状态"""
        await cls.broadcast("services_status", status)

    @classmethod
    async def broadcast_task_log(cls, task_id: str, log_entry: Any):
        """推送单条实时任务日志（任务运行中）"""
        await cls.broadcast("task_log", {"task_id": task_id, "log": log_entry})

    @classmethod
    async def broadcast_warmup_progress(cls, status: Any):
        """推送 Bangumi 缓存预热进度"""
        await cls.broadcast("warmup_progress", status)

    @classmethod
    async def broadcast_subscriptions_changed(cls, data: Any = None):
        """推送订阅列表变更通知"""
        await cls.broadcast("subscriptions_changed", data)
