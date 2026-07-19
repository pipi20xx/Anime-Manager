"""Telegram 发送层 —— 只负责调用 Bot API，把文本/图片/按钮发出去。

不关心业务语义，不做配置开关判断（开关由 Manager 负责）。
保留原系统的 httpx + 代理 + log_audit 审计日志，以及三元组返回值契约
``(success: bool, message: str, message_id: int | None)``。
"""
import logging
from typing import Optional, Dict, List, Tuple

import httpx

from config_manager import ConfigManager
from logger import log_audit

from .models import Notification
from .renderer import NotificationRenderer

logger = logging.getLogger("Notification")


class TelegramNotifier:
    """Telegram 通知发送器。"""

    def __init__(self, bot_token: str, chat_id: str, proxy: Optional[str] = None,
                 style: str = "default", renderer: Optional[NotificationRenderer] = None):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.proxy = proxy
        self.style = style
        self.renderer = renderer or NotificationRenderer()
        self.base_url = f"https://api.telegram.org/bot{bot_token}"

    # ────────────────────────────────────────────────────────
    # 核心发送
    # ────────────────────────────────────────────────────────

    async def send(
        self,
        notification: Notification,
        style: Optional[str] = None,
        photo_url: Optional[str] = None,
        pin: bool = False,
        buttons: Optional[List[List[Dict]]] = None,
    ) -> Tuple[bool, str, Optional[int]]:
        """渲染并发送通知。

        Args:
            notification: 标准通知对象。
            style: 渲染样式；为 None 时使用实例初始化时的 style。
            photo_url: 图片 URL，若提供则用 sendPhoto（caption=文本）。
            pin: 是否置顶消息。
            buttons: 可选的 inline_keyboard 二维数组。
        """
        effective_style = style if style is not None else self.style
        effective_photo = photo_url if photo_url is not None else notification.image_url
        text = self.renderer.render(notification, effective_style)
        return await self.send_raw(text, photo_url=effective_photo, pin=pin, buttons=buttons)

    async def send_raw(
        self,
        text: str,
        photo_url: Optional[str] = None,
        pin: bool = False,
        buttons: Optional[List[List[Dict]]] = None,
    ) -> Tuple[bool, str, Optional[int]]:
        """直接发送已格式化好的 HTML 文本（不经过渲染器）。

        保留与原 ``NotificationManager.send_telegram_message`` 完全一致的行为与返回值。
        """
        try:
            async with httpx.AsyncClient(proxy=self.proxy, timeout=10.0) as client:
                if photo_url:
                    url = f"{self.base_url}/sendPhoto"
                    payload = {
                        "chat_id": self.chat_id,
                        "photo": photo_url,
                        "caption": text,
                        "parse_mode": "HTML",
                    }
                    resp = await client.post(url, json=payload)
                else:
                    url = f"{self.base_url}/sendMessage"
                    payload = {
                        "chat_id": self.chat_id,
                        "text": text,
                        "parse_mode": "HTML",
                    }
                    if buttons:
                        payload["reply_markup"] = {"inline_keyboard": buttons}
                    resp = await client.post(url, json=payload)

                if resp.status_code == 200:
                    result = resp.json()
                    message_id = result.get("result", {}).get("message_id")
                    if pin and message_id:
                        await self.pin_chat_message(self.chat_id, message_id, client=client)
                    log_audit("通知", "发送成功", "Telegram 消息发送成功", level="DEBUG")
                    return True, "Success", message_id
                else:
                    err_msg = f"Telegram API Error: {resp.status_code} - {resp.text}"
                    logger.error(err_msg)
                    log_audit("通知", "发送失败", f"Telegram 发送失败: {resp.status_code}", level="ERROR")
                    return False, err_msg, None

        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            log_audit("通知", "发送异常", f"Telegram 发送异常: {str(e)}", level="ERROR")
            return False, str(e), None

    # ────────────────────────────────────────────────────────
    # 置顶
    # ────────────────────────────────────────────────────────

    async def pin_chat_message(
        self,
        chat_id: str,
        message_id: int,
        client: Optional[httpx.AsyncClient] = None,
    ) -> bool:
        """置顶 Telegram 消息。"""
        own_client = client is None
        if own_client:
            client = httpx.AsyncClient(proxy=self.proxy, timeout=10.0)

        try:
            url = f"{self.base_url}/pinChatMessage"
            payload = {
                "chat_id": chat_id,
                "message_id": message_id,
                "disable_notification": True,
            }
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                logger.info(f"消息 {message_id} 已置顶")
                return True
            else:
                logger.warning(f"置顶消息失败: {resp.status_code} - {resp.text}")
                return False
        except Exception as e:
            logger.error(f"置顶消息异常: {e}")
            return False
        finally:
            if own_client:
                await client.aclose()
