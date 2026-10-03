"""Telegram 发送层 —— 只负责调用 Bot API，把文本/图片/按钮发出去。

不关心业务语义，不做配置开关判断（开关由 Manager 负责）。
保留原系统的 httpx + 代理 + log_audit 审计日志，以及三元组返回值契约
``(success: bool, message: str, message_id: int | None)``。
"""
import asyncio
import logging
from typing import Optional, Dict, List, Tuple

import httpx

from config_manager import ConfigManager
from logger import log_audit

from .models import Notification
from .renderer import NotificationRenderer

logger = logging.getLogger("Notification")

# Telegram 消息长度限制（留余量：emoji 等字符按 UTF-16 计数会略多于 Python len）
TG_TEXT_LIMIT = 4000
TG_CAPTION_LIMIT = 960


def _split_text(text: str, limit: int) -> List[str]:
    """按行边界把文本切成不超 limit 的块。

    项目内模板的 HTML 标签均为行内闭合，按行切分不会把标签切断；
    单行超限时对该行硬切兜底。
    """
    text = text.strip()
    if len(text) <= limit:
        return [text]

    chunks: List[str] = []
    buf: List[str] = []
    buf_len = 0
    for line in text.split("\n"):
        line_len = len(line) + 1  # 含换行
        if buf_len + line_len > limit and buf:
            chunks.append("\n".join(buf))
            buf, buf_len = [], 0
        if len(line) > limit:
            # 单行超限：硬切
            for i in range(0, len(line), limit):
                piece = line[i:i + limit]
                if buf:
                    chunks.append("\n".join(buf))
                    buf, buf_len = [], 0
                chunks.append(piece)
            continue
        buf.append(line)
        buf_len += line_len
    if buf:
        chunks.append("\n".join(buf))
    return [c for c in chunks if c.strip()]


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

        自动处理 Telegram 长度限制：
        - 纯文本按 TG_TEXT_LIMIT 分片逐条发送；
        - 带图片时 caption 受 TG_CAPTION_LIMIT 限制，第一片作 caption，
          其余片段转纯文本消息继续发送；
        - 429 限流按 retry_after 等待后重试一次；
        - 400（HTML 解析失败）时去掉 parse_mode 以纯文本重试，保证消息不丢。

        保留与原 ``NotificationManager.send_telegram_message`` 一致的行为与返回值。
        """
        limit = TG_CAPTION_LIMIT if photo_url else TG_TEXT_LIMIT
        chunks = _split_text(text, limit)

        try:
            async with httpx.AsyncClient(proxy=self.proxy, timeout=10.0) as client:
                first_message_id: Optional[int] = None
                overall_ok = True
                err_msg = "Success"

                for i, chunk in enumerate(chunks):
                    is_caption = bool(photo_url) and i == 0
                    if photo_url and i == 0:
                        url = f"{self.base_url}/sendPhoto"
                        payload = {
                            "chat_id": self.chat_id,
                            "photo": photo_url,
                            "caption": chunk,
                            "parse_mode": "HTML",
                        }
                    else:
                        url = f"{self.base_url}/sendMessage"
                        payload = {
                            "chat_id": self.chat_id,
                            "text": chunk,
                            "parse_mode": "HTML",
                        }
                        if i == 0 and buttons:
                            payload["reply_markup"] = {"inline_keyboard": buttons}

                    ok, msg, message_id = await self._post_with_retry(client, url, payload)
                    if i == 0:
                        first_message_id = message_id
                        overall_ok, err_msg = ok, msg
                    elif not ok:
                        overall_ok = False
                        err_msg = msg

                    if i == 0 and pin and first_message_id:
                        await self.pin_chat_message(self.chat_id, first_message_id, client=client)

                    if i < len(chunks) - 1:
                        # 分片间稍作间隔，避免触发限流
                        await asyncio.sleep(0.6)

                if overall_ok:
                    log_audit("通知", "发送成功", f"Telegram 消息发送成功（{len(chunks)} 片）", level="DEBUG")
                return overall_ok, err_msg, first_message_id

        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            log_audit("通知", "发送异常", f"Telegram 发送异常: {str(e)}", level="ERROR")
            return False, str(e), None

    async def _post_with_retry(
        self,
        client: httpx.AsyncClient,
        url: str,
        payload: Dict,
    ) -> Tuple[bool, str, Optional[int]]:
        """发送单条请求：429 按 retry_after 等待重试一次；400 时去 parse_mode 重发一次。"""
        for attempt in range(2):
            resp = await client.post(url, json=payload)

            if resp.status_code == 200:
                message_id = resp.json().get("result", {}).get("message_id")
                return True, "Success", message_id

            if resp.status_code == 429 and attempt == 0:
                try:
                    retry_after = float(resp.json().get("parameters", {}).get("retry_after", 3))
                except Exception:
                    retry_after = 3.0
                logger.warning(f"Telegram 限流，{retry_after}s 后重试")
                await asyncio.sleep(retry_after + 0.5)
                continue

            if resp.status_code == 400 and payload.get("parse_mode") and attempt == 0:
                # HTML 实体解析失败（如分片切坏了标签）：退化为纯文本重发，避免消息丢失
                logger.warning(f"Telegram HTML 解析失败，尝试纯文本重发: {resp.text[:200]}")
                fallback = {k: v for k, v in payload.items() if k != "parse_mode"}
                resp = await client.post(url, json=fallback)
                if resp.status_code == 200:
                    message_id = resp.json().get("result", {}).get("message_id")
                    return True, "Success", message_id

            break

        err_msg = f"Telegram API Error: {resp.status_code} - {resp.text}"
        logger.error(err_msg)
        log_audit("通知", "发送失败", f"Telegram 发送失败: {resp.status_code}", level="ERROR")
        return False, err_msg, None

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
