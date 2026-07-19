"""通知数据层 —— 业务代码只创建这里的对象，不关心任何样式。

设计原则：
- 数据与表现分离：本文件只描述「发生了什么」，绝不涉及图标/HTML/排版。
- 一旦确定，永不改动字段语义（仅可追加新事件类型）。
"""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from enum import Enum


class NotificationEvent(str, Enum):
    """事件类型枚举。

    采用 ``str, Enum`` 以便序列化与日志可读。
    新增事件类型时只需在此追加，并在 ``NotificationRenderer`` 中补齐图标 / 排版。
    """

    # ── 下载相关 ──
    DOWNLOAD_COMPLETE = "download_complete"          # 下载完成
    DOWNLOAD_FAILED = "download_failed"              # 下载失败
    TORRENT_DOWNLOAD_FAILED = "torrent_download_failed"  # 种子文件下载失败

    # ── 整理相关 ──
    ORGANIZE_COMPLETE = "organize_complete"          # 整理完成（入库）
    ORGANIZE_FAILED = "organize_failed"              # 整理失败

    # ── 订阅相关 ──
    SUB_ADDED = "sub_added"                          # 新增订阅
    SUB_DELETED = "sub_deleted"                      # 删除订阅
    SUB_COMPLETED = "sub_completed"                  # 订阅完结
    SUB_MATCHED = "sub_matched"                      # 订阅命中推送
    EPISODE_AIRED = "episode_aired"                  # 新集播出提醒

    # ── 规则 ──
    RULE_MATCHED = "rule_matched"                    # 规则命中下载

    # ── STRM ──
    STRM_TASK_FINISHED = "strm_task_finished"        # STRM 任务完成
    STRM_LINK_CREATED = "strm_link_created"          # 整理联动生成 STRM
    STRM_WEBHOOK = "strm_webhook"                    # Webhook 实时监控联动

    # ── 媒体库 ──
    LIBRARY_NEW = "library_new"                      # Emby 新入库
    LIBRARY_DELETED = "library_deleted"              # Emby 深度删除

    # ── 客户端 ──
    CLIENT_ERROR = "client_error"                    # 下载客户端执行异常
    CLIENT_PUSH_FAILED = "client_push_failed"        # 推送客户端失败

    # ── RSS / 任务 ──
    RSS_UPDATED = "rss_updated"                      # RSS 更新
    TASK_STARTED = "task_started"                    # 任务开始
    TASK_COMPLETED = "task_completed"                # 任务完成

    # ── 系统 ──
    SYSTEM_STARTUP = "system_startup"                # 系统启动
    SYSTEM_HEALTH = "system_health"                  # 系统健康告警
    SYSTEM_WARNING = "system_warning"                # 系统警告

    # ── 日历 / 摘要 ──
    CALENDAR_DAILY = "calendar_daily"                # 每日播出概览
    DAILY_SUMMARY = "daily_summary"                  # 每日番剧摘要

    # ── 其它 ──
    TEST = "test"                                    # 测试通知
    RAW = "raw"                                      # 原始文本（不经过渲染排版）


class NotificationPriority(str, Enum):
    """通知优先级"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


@dataclass
class Notification:
    """标准通知对象 —— 业务代码只创建这个。

    Attributes:
        event_type: 事件类型，决定渲染器使用的图标与排版。
        title: 简短标题（如番剧名）。
        message: 主要内容（单行或多行纯文本，不含 HTML）。
        data: 扩展数据字典，渲染器按事件类型按需读取（大小/质量/站点/季集等）。
        image_url: 封面图公网 URL（可选）。若提供，将通过 sendPhoto 发送。
        priority: 优先级 "low" / "normal" / "high"，默认 "normal"。
    """

    event_type: NotificationEvent
    title: str = ""
    message: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    image_url: Optional[str] = None
    priority: str = "normal"

    def __post_init__(self):
        # 兼容直接传 None 的情况
        if self.data is None:
            self.data = {}
        # 允许用字符串构造事件类型
        if not isinstance(self.event_type, NotificationEvent):
            try:
                self.event_type = NotificationEvent(self.event_type)
            except ValueError:
                self.event_type = NotificationEvent.RAW
