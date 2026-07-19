"""通知系统包 —— 数据与表现分离的规范化通知架构。

架构分层：
    业务代码 → 创建 Notification 对象（只发数据）
    Manager  → 接收，决定用哪个样式（default/detailed）
    Renderer → 加图标、排版、格式化（生成最终文本）
    TelegramNotifier → 转 HTML、加按钮、调用 Bot API

公共导出：
    Notification          标准通知数据对象
    NotificationEvent     事件类型枚举
    NotificationPriority  优先级枚举
    notification_manager  全局实例（业务代码唯一入口）

使用方式：
    from notification import notification_manager

    await notification_manager.notify_organize_complete(final_res)
    await notification_manager.notify_sub_added(sub)
"""
from .models import Notification, NotificationEvent, NotificationPriority
from .renderer import NotificationRenderer
from .notifier import TelegramNotifier
from .manager import NotificationManager, notification_manager

__all__ = [
    "Notification",
    "NotificationEvent",
    "NotificationPriority",
    "NotificationRenderer",
    "TelegramNotifier",
    "NotificationManager",
    "notification_manager",
]
