import asyncio
import logging
import httpx
import json
import os
import re
import time
from typing import Optional, Dict, List, Any, Tuple
from config_manager import ConfigManager
from logger import log_audit

logger = logging.getLogger("TelegramBot")

# 每页显示的条目数
ITEMS_PER_PAGE = 10

# 会话状态持久化文件（对话历史 + 工具模式设置，重启不丢）
TG_STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tg_bot_state.json")


class TelegramBot:
    _instance: Optional["TelegramBot"] = None
    _running: bool = False
    _task: Optional[asyncio.Task] = None
    _last_update_id: int = 0
    _user_sessions: Dict[int, List[Dict]] = {}
    # 存储每个 chat 的分页列表数据：{chat_id: {"items": [...], "title": "...", "page": 0, "total": N, "msg_id": 123}}
    _paginated_lists: Dict[int, Dict[str, Any]] = {}
    # 每个 chat 正在执行的 AI 任务：{chat_id: asyncio.Task}
    _chat_tasks: Dict[int, asyncio.Task] = {}
    # 每个 chat 的会话级设置：{chat_id: {"use_tools": bool | None}}，None 表示跟随全局配置
    _chat_settings: Dict[int, Dict[str, Any]] = {}
    # Bot 身份（getMe），用于群聊里判断 @提及 / 回复机器人
    _bot_id: int = 0
    _bot_username: str = ""
    
    @classmethod
    def get_instance(cls) -> "TelegramBot":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def _get_bot_config(self) -> Dict:
        config = ConfigManager.get_config()
        return {
            "enabled": config.get("telegram_bot_enabled", False),
            "bot_token": config.get("telegram", {}).get("bot_token", ""),
            "allowed_chats": config.get("telegram_allowed_chats", []),
            "proxy": ConfigManager.get_proxy("telegram")
        }
    
    async def _get_updates(self, client: httpx.AsyncClient, bot_token: str, proxy: str = None) -> List[Dict]:
        url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
        params = {
            "timeout": 30,
            "offset": self._last_update_id + 1
        }
        
        try:
            resp = await client.get(url, params=params, timeout=35)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("ok"):
                    return data.get("result", [])
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"[TG Bot] 获取更新失败: {e}")
        
        return []
    
    # Telegram sendMessage 单条消息字符数上限
    TELEGRAM_MSG_LIMIT = 4096

    async def _send_message(self, client: httpx.AsyncClient, bot_token: str, chat_id: int, text: str, reply_to: int = None, reply_markup: Dict = None, parse_html: bool = True) -> bool:
        """
        发送消息，自动处理超长消息分片。
        Telegram sendMessage 单条消息限制 4096 字符，超过时按行拆分依次发送。
        :param reply_markup: 可选的 inline keyboard
        :param parse_html: 按 Telegram HTML 发送；解析失败会自动回退纯文本
        :return: 全部分片发送成功返回 True，任一失败返回 False
        """
        if not text:
            return True

        chunks = self._split_long_message(text, self.TELEGRAM_MSG_LIMIT)

        if len(chunks) == 1:
            return await self._send_single_message(client, bot_token, chat_id, chunks[0], reply_to, reply_markup, parse_html) is not None

        logger.info(f"[TG Bot] 消息过长({len(text)}字符)，拆分为 {len(chunks)} 条发送")
        all_success = True
        for idx, chunk in enumerate(chunks):
            # 只有第一条回复用户原消息，避免多条消息都@原消息造成刷屏
            chunk_reply_to = reply_to if idx == 0 else None
            # 只有第一条附带 reply_markup（翻页按钮）
            chunk_markup = reply_markup if idx == 0 else None
            sent = await self._send_single_message(client, bot_token, chat_id, chunk, chunk_reply_to, chunk_markup, parse_html)
            if sent is None:
                all_success = False
            # 避免发送过快触发 Telegram 速率限制
            await asyncio.sleep(0.3)

        return all_success

    async def _send_single_message(self, client: httpx.AsyncClient, bot_token: str, chat_id: int, text: str, reply_to: int = None, reply_markup: Dict = None, parse_html: bool = True) -> Optional[int]:
        """
        发送单条消息（不超过 4096 字符）。
        :return: 成功返回 message_id，失败返回 None
        """
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
        }

        if parse_html:
            payload["parse_mode"] = "HTML"

        if reply_to:
            payload["reply_to_message_id"] = reply_to

        if reply_markup:
            payload["reply_markup"] = reply_markup

        for attempt in range(2):
            try:
                resp = await client.post(url, json=payload, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("result", {}).get("message_id")
                # HTML 实体解析失败（模型输出常含特殊字符），去掉格式化回退纯文本重试一次
                if attempt == 0 and parse_html and resp.status_code == 400:
                    logger.warning(f"[TG Bot] HTML 解析失败，回退纯文本重发: {resp.text[:200]}")
                    payload = {k: v for k, v in payload.items() if k != "parse_mode"}
                    payload["text"] = self._html_to_plain(text)
                    continue
                logger.error(f"[TG Bot] 发送消息失败: {resp.status_code} - {resp.text}")
                return None
            except Exception as e:
                logger.error(f"[TG Bot] 发送消息异常: {e}")
                return None

        return None

    @staticmethod
    def _split_long_message(text: str, limit: int) -> List[str]:
        """
        将超长文本拆分成多条，优先按行分割避免在行中间截断。
        对于单行超过 limit 的情况，退化为按字符硬切。
        """
        if len(text) <= limit:
            return [text]

        chunks: List[str] = []
        lines = text.split('\n')
        current = ""

        for line in lines:
            # 候选内容 = 当前块 + 换行 + 新行
            candidate = line if not current else current + '\n' + line
            if len(candidate) <= limit:
                current = candidate
            else:
                # 当前行放不下，先把当前块存起来
                if current:
                    chunks.append(current)
                    current = ""
                # 处理单行本身就超过 limit 的情况：按字符硬切
                while len(line) > limit:
                    chunks.append(line[:limit])
                    line = line[limit:]
                current = line

        if current:
            chunks.append(current)

        return chunks

    # ==================== Markdown → Telegram HTML ====================

    @staticmethod
    def _escape_html(text: str) -> str:
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    @staticmethod
    def _html_to_plain(text: str) -> str:
        """HTML 回退纯文本：去标签并还原转义"""
        text = re.sub(r"<[^>]+>", "", text)
        return text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")

    def _md_to_telegram_html(self, text: str) -> str:
        """
        模型输出的 Markdown 转 Telegram 支持的 HTML 子集（b/i/s/code/pre/a）。
        Telegram 不支持任意 HTML，直接发送原始 Markdown 会解析失败或原样显示符号。
        """
        if not text:
            return ""
        out: List[str] = []
        segments = text.split("```")
        for i, seg in enumerate(segments):
            if i % 2 == 1:
                # 代码块：第一行是语言标识
                lines = seg.split("\n", 1)
                lang = lines[0].strip() if len(lines) > 1 else ""
                body = (lines[1] if len(lines) > 1 else seg).rstrip("\n")
                inner = self._escape_html(body)
                if lang:
                    out.append(f'<pre><code class="language-{self._escape_html(lang)}">{inner}</code></pre>')
                else:
                    out.append(f"<pre>{inner}</pre>")
            else:
                out.append(self._convert_block_md(seg))
        return "".join(out).replace("\x00", "")

    def _convert_block_md(self, block: str) -> str:
        """逐行转换非代码块的 Markdown：标题/引用/表格/普通行"""
        lines_out: List[str] = []
        in_table = False
        for line in block.split("\n"):
            stripped = line.strip()

            # 表格：分隔行跳过；数据行转成「cell ｜ cell」可读文本，表头加粗
            if stripped.startswith("|"):
                if re.match(r"^\|[\s:\-|]+\|$", stripped):
                    continue
                cells = [c.strip() for c in stripped.strip("|").split("|") if c.strip()]
                if cells:
                    joined = " ｜ ".join(self._convert_inline_md(c) for c in cells)
                    lines_out.append(f"<b>{joined}</b>" if not in_table else joined)
                    in_table = True
                continue

            in_table = False
            m = re.match(r"^#{1,6}\s+(.*)$", stripped)
            if m:
                lines_out.append(f"<b>{self._convert_inline_md(m.group(1))}</b>")
                continue
            m = re.match(r"^>\s?(.*)$", stripped)
            if m:
                lines_out.append(f"<i>{self._convert_inline_md(m.group(1))}</i>")
                continue
            lines_out.append(self._convert_inline_md(line))
        return "\n".join(lines_out)

    def _convert_inline_md(self, text: str) -> str:
        """行内 Markdown 转换：行内代码先摘除，避免其中的符号被二次转换"""
        codes: List[str] = []

        def _stash(m):
            codes.append(m.group(1))
            return f"\x00{len(codes) - 1}\x00"

        text = re.sub(r"`([^`\n]+)`", _stash, text)
        text = self._escape_html(text)
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
        text = re.sub(r"__(.+?)__", r"<b>\1</b>", text)
        text = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"<i>\1</i>", text)
        text = re.sub(r"~~(.+?)~~", r"<s>\1</s>", text)
        text = re.sub(r"\[([^\]]+)\]\((https?://[^\s)]+)\)", r'<a href="\2">\1</a>', text)

        def _restore(m):
            idx = int(m.group(1))
            if 0 <= idx < len(codes):
                return f"<code>{self._escape_html(codes[idx])}</code>"
            return ""

        return re.sub(r"\x00(\d+)\x00", _restore, text)

    # ==================== 分页列表功能 ====================

    def _build_paginated_keyboard(self, current_page: int, total_pages: int, list_id: str) -> Dict:
        """构建翻页 inline keyboard（旧版，仅翻页按钮）"""
        buttons = []

        row = []
        if current_page > 0:
            row.append({"text": "⬅️ 上一页", "callback_data": f"page:{list_id}:{current_page - 1}"})
        row.append({"text": f"{current_page + 1}/{total_pages}", "callback_data": f"noop:{list_id}"})
        if current_page < total_pages - 1:
            row.append({"text": "下一页 ➡️", "callback_data": f"page:{list_id}:{current_page + 1}"})
        buttons.append(row)

        return {"inline_keyboard": buttons}

    # ==================== 结构化列表分页（带订阅按钮）====================

    def _build_list_keyboard(self, page_data: Dict, page: int) -> Dict:
        """构建带订阅按钮的分页 inline keyboard"""
        items = page_data["items"]
        list_type = page_data.get("type", "")
        total_pages = page_data.get("total_pages", 1)
        subscribed = page_data.get("subscribed", set())

        start = page * ITEMS_PER_PAGE
        end = min(start + ITEMS_PER_PAGE, len(items))

        buttons = []

        for i in range(start, end):
            item = items[i]
            num = i + 1
            title = item.get("title", "未知")
            # Telegram 按钮文本限制约 64 字节，截断长标题
            if len(title) > 35:
                title = title[:33] + "…"

            if i in subscribed:
                btn_text = f"✅ {num}. {title}"
            elif list_type == "subscription":
                btn_text = f"🗑️ {num}. {title}"
            else:
                btn_text = f"📥 {num}. {title}"

            buttons.append([{
                "text": btn_text,
                "callback_data": f"sub:{i}"
            }])

        # 翻页行
        nav_row = []
        if page > 0:
            nav_row.append({"text": "⬅️ 上一页", "callback_data": f"page:{page - 1}"})
        nav_row.append({"text": f"{page + 1}/{total_pages}", "callback_data": "noop:0"})
        if page < total_pages - 1:
            nav_row.append({"text": "下一页 ➡️", "callback_data": f"page:{page + 1}"})
        buttons.append(nav_row)

        return {"inline_keyboard": buttons}

    def _format_list_message(self, page_data: Dict, page: int) -> str:
        """从结构化数据格式化指定页的消息文本"""
        items = page_data["items"]
        title = page_data.get("title", "列表")
        list_type = page_data.get("type", "")
        total = len(items)
        start = page * ITEMS_PER_PAGE
        end = min(start + ITEMS_PER_PAGE, total)

        lines = [f"📺 <b>{title}</b>\n"]

        for i in range(start, end):
            item = items[i]
            num = i + 1
            name = item.get("title", "未知")
            subtitle = item.get("subtitle", "")
            line = f"{num}. <b>{name}</b>"
            if subtitle:
                line += f"  <i>({subtitle})</i>"
            lines.append(line)

        total_pages = (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
        lines.append(f"\n📊 共 {total} 项，第 {page + 1}/{total_pages} 页")

        if list_type in ("bangumi", "tmdb"):
            lines.append("💡 点击下方按钮可直接订阅")
        elif list_type == "subscription":
            lines.append("💡 点击下方按钮可删除订阅")

        return "\n".join(lines)

    async def _send_list_with_buttons(
        self, client: httpx.AsyncClient, bot_token: str, chat_id: int,
        list_data: Dict, reply_to: int = None
    ) -> bool:
        """使用结构化列表数据发送带订阅按钮的分页消息"""
        items = list_data.get("items", [])
        if not items:
            return False

        list_type = list_data.get("type", "")
        # 根据列表类型构建标题
        if list_type == "bangumi":
            title = "番剧列表"
        elif list_type == "tmdb":
            title = "影视列表"
        elif list_type == "subscription":
            title = "订阅列表"
        else:
            title = "列表"

        total_pages = (len(items) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
        page_data = {
            "type": list_type,
            "items": items,
            "title": title,
            "total_pages": total_pages,
            "page": 0,
            "subscribed": set(),
        }

        # 如果不超过一页，也发送按钮（方便直接点击订阅）
        page_text = self._format_list_message(page_data, 0)
        keyboard = self._build_list_keyboard(page_data, 0)

        # 存储分页数据
        self._paginated_lists[chat_id] = page_data

        return await self._send_single_message(client, bot_token, chat_id, page_text, reply_to, keyboard)

    async def _execute_subscribe(
        self, client: httpx.AsyncClient, bot_token: str,
        chat_id: int, message_id: int, callback_id: str, item_index: int
    ):
        """执行订阅按钮回调"""
        page_data = self._paginated_lists.get(chat_id)
        if not page_data:
            await self._answer_callback(client, bot_token, callback_id, "数据已过期，请重新搜索")
            return

        items = page_data["items"]
        if item_index < 0 or item_index >= len(items):
            await self._answer_callback(client, bot_token, callback_id, "无效的编号")
            return

        item = items[item_index]
        list_type = page_data.get("type", "")

        success = False
        message = ""

        try:
            from assistant.tools import ToolRegistry

            if list_type == "bangumi":
                bgm_id = item.get("id")
                if not bgm_id:
                    message = "缺少 Bangumi ID"
                else:
                    tool = ToolRegistry.get("subscribe_by_bangumi_id")
                    result = await tool.func(bangumi_id=int(bgm_id))
                    success = result.success
                    message = result.message or ("✅ 订阅成功" if success else f"❌ {result.error}")

            elif list_type == "tmdb":
                tmdb_id = item.get("id")
                title = item.get("title", "")
                media_type = item.get("media_type", "tv")
                if not tmdb_id:
                    message = "缺少 TMDB ID"
                else:
                    tool = ToolRegistry.get("add_subscription")
                    result = await tool.func(
                        title=title,
                        tmdb_id=str(tmdb_id),
                        media_type=media_type,
                        season=1
                    )
                    success = result.success
                    message = result.message or ("✅ 订阅成功" if success else f"❌ {result.error}")

            elif list_type == "subscription":
                # 用数据库订阅 ID 精准删除，避免删除后位置错位导致后续按钮失效
                sub_id = item.get("id")
                if not sub_id:
                    message = "缺少订阅ID，无法删除"
                else:
                    from rss_core.subscription_manager import SubscriptionManager
                    await SubscriptionManager.delete_subscription(int(sub_id))
                    success = True
                    message = f"✅ 已删除订阅: {item.get('title', '未知')}"

            else:
                message = "不支持的列表类型"

        except Exception as e:
            logger.error(f"[TG Bot] 订阅执行失败: {e}", exc_info=True)
            message = f"❌ 执行失败: {e}"

        # 应答回调，显示结果
        await self._answer_callback(client, bot_token, callback_id, message[:200])

        # 更新按钮状态
        if success:
            if list_type == "subscription":
                # 删除成功后从缓存列表移除该项，避免索引错位
                if 0 <= item_index < len(items):
                    items.pop(item_index)
                # 重新计算总页数
                total_pages = max(1, (len(items) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
                page_data["total_pages"] = total_pages
                # 若当前页因删除变空（删的是最后一页最后一项），回退一页
                current_page = page_data.get("page", 0)
                if current_page >= total_pages:
                    current_page = total_pages - 1
                    page_data["page"] = current_page
                # 列表清空时给个提示，不再显示按钮
                if not items:
                    await self._edit_message(
                        client, bot_token, chat_id, message_id, "📭 订阅列表已清空"
                    )
                    logger.info(f"[TG Bot] 订阅列表已清空: chat={chat_id}")
                    return
            else:
                # bangumi/tmdb 订阅成功，标记已订阅状态
                page_data.setdefault("subscribed", set()).add(item_index)
            current_page = page_data.get("page", 0)
            keyboard = self._build_list_keyboard(page_data, current_page)
            page_text = self._format_list_message(page_data, current_page)
            await self._edit_message(client, bot_token, chat_id, message_id, page_text, keyboard)
            logger.info(f"[TG Bot] 按钮操作成功: chat={chat_id}, item={item_index}, type={list_type}")

    def _format_paginated_message(self, page_data: Dict, page: int) -> str:
        """格式化指定页的内容"""
        items = page_data["items"]
        title = page_data.get("title", "列表")
        total = len(items)
        start = page * ITEMS_PER_PAGE
        end = min(start + ITEMS_PER_PAGE, total)

        lines = [f"📺 {title}\n"]

        for i in range(start, end):
            item = items[i]
            num = i + 1
            name = item.get("title", "未知")
            extra = item.get("extra", "")
            line = f"{num}. {name}"
            if extra:
                line += f" ({extra})"
            lines.append(line)

        lines.append(f"\n📊 共 {total} 项，第 {page + 1}/{(total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE} 页")
        lines.append("💡 输入编号可订阅对应作品")

        return "\n".join(lines)

    async def _try_send_as_paginated(self, client: httpx.AsyncClient, bot_token: str, chat_id: int, text: str, reply_to: int = None) -> Optional[int]:
        """
        尝试将 Agent 返回的长列表消息转为带翻页按钮的消息。
        如果消息不包含编号列表或不够长，返回 None 走普通发送。
        """
        parsed = self._parse_list_from_text(text)
        if not parsed:
            return False

        items, title = parsed
        if len(items) <= ITEMS_PER_PAGE:
            return False

        # 存储分页数据
        list_id = f"list_{chat_id}_{len(self._paginated_lists)}"
        total_pages = (len(items) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
        page_data = {
            "items": items,
            "title": title,
            "total_pages": total_pages,
        }
        self._paginated_lists[chat_id] = page_data

        page_text = self._format_paginated_message(page_data, 0)
        keyboard = self._build_paginated_keyboard(0, total_pages, list_id)

        return await self._send_single_message(client, bot_token, chat_id, page_text, reply_to, keyboard)

    def _parse_list_from_text(self, text: str) -> Optional[tuple]:
        """
        从 Agent 返回的文本中解析编号列表。
        支持 Markdown 表格格式和普通编号列表格式。
        返回 (items, title) 或 None
        """
        if not text or len(text) < 50:
            return None

        # 检测是否包含编号列表
        # 格式1: "1. 标题" 或 "1. 标题 (信息)"
        # 格式2: Markdown 表格 "| 1 | 标题 | ..."
        lines = text.split('\n')

        # 尝试提取标题（第一行）
        title_match = re.match(r'^[📺🔍🎬📋❌📁]+\s*\*{0,2}(.+?)\*{0,2}\s*$', lines[0].strip()) if lines else None
        title = title_match.group(1) if title_match else "列表"

        items = []

        # 尝试解析 Markdown 表格格式
        table_pattern = re.compile(r'^\|\s*(\d+)\s*\|\s*(.+?)\s*\|')
        for line in lines:
            m = table_pattern.match(line.strip())
            if m:
                idx = int(m.group(1))
                # 提取表格中的标题（第二列）和其他信息
                cols = [c.strip() for c in line.strip().split('|')[1:-1]]
                item_title = cols[1] if len(cols) > 1 else f"项目{idx}"
                # 尝试从表格列中提取 bangumi_id 或额外信息
                extra_parts = cols[2:] if len(cols) > 2 else []
                extra = " ".join(extra_parts) if extra_parts else ""
                items.append({"title": item_title, "extra": extra, "index": idx})

        # 如果表格解析失败，尝试普通编号列表
        if not items:
            list_pattern = re.compile(r'^(\d+)[.、)]\s+(.+)')
            for line in lines:
                m = list_pattern.match(line.strip())
                if m:
                    idx = int(m.group(1))
                    content = m.group(2).strip()
                    # 去掉 Markdown 加粗
                    content = re.sub(r'\*{1,2}(.+?)\*{1,2}', r'\1', content)
                    items.append({"title": content, "extra": "", "index": idx})

        if len(items) < ITEMS_PER_PAGE + 1:
            return None

        # 去重（按 index）
        seen = set()
        unique_items = []
        for item in items:
            if item["index"] not in seen:
                seen.add(item["index"])
                unique_items.append(item)

        return (unique_items, title) if unique_items else None

    async def _handle_callback_query(self, client: httpx.AsyncClient, bot_token: str, callback_query: Dict, allowed_chats: List):
        """处理 inline keyboard 按钮回调"""
        callback_id = callback_query.get("id")
        data = callback_query.get("data", "")
        message = callback_query.get("message")
        
        if not message:
            await self._answer_callback(client, bot_token, callback_id, "")
            return

        chat_id = message.get("chat", {}).get("id")
        message_id = message.get("message_id")

        if allowed_chats and chat_id not in allowed_chats:
            await self._answer_callback(client, bot_token, callback_id, "无权限")
            return

        # 解析回调数据
        parts = data.split(":")
        if len(parts) < 2:
            await self._answer_callback(client, bot_token, callback_id, "")
            return

        action = parts[0]

        if action == "sub":
            # 订阅按钮 - 不先应答，由 _execute_subscribe 应答结果
            try:
                item_index = int(parts[1])
            except (ValueError, IndexError):
                await self._answer_callback(client, bot_token, callback_id, "无效的回调数据")
                return
            await self._execute_subscribe(client, bot_token, chat_id, message_id, callback_id, item_index)

        elif action == "page":
            # 翻页 - 支持新旧两种格式
            # 新格式: page:{page_num}  旧格式: page:{list_id}:{page_num}
            if len(parts) >= 3:
                target_page = int(parts[2])
                list_id = parts[1]
            else:
                target_page = int(parts[1])
                list_id = ""

            page_data = self._paginated_lists.get(chat_id)
            if not page_data:
                await self._answer_callback(client, bot_token, callback_id, "数据已过期，请重新搜索")
                return

            total_pages = page_data.get("total_pages", 1)
            if target_page < 0 or target_page >= total_pages:
                await self._answer_callback(client, bot_token, callback_id, "")
                return

            page_data["page"] = target_page

            # 检查是结构化数据还是旧版文本解析数据
            if "type" in page_data:
                # 新版结构化数据（带订阅按钮）
                page_text = self._format_list_message(page_data, target_page)
                keyboard = self._build_list_keyboard(page_data, target_page)
            else:
                # 旧版文本解析数据
                page_text = self._format_paginated_message(page_data, target_page)
                keyboard = self._build_paginated_keyboard(target_page, total_pages, list_id)

            await self._answer_callback(client, bot_token, callback_id, "")
            await self._edit_message(client, bot_token, chat_id, message_id, page_text, keyboard)

        elif action == "noop":
            # 无操作（如点击页码）
            await self._answer_callback(client, bot_token, callback_id, "")

        else:
            await self._answer_callback(client, bot_token, callback_id, "")

    async def _answer_callback(self, client: httpx.AsyncClient, bot_token: str, callback_id: str, text: str = ""):
        """应答 callback query"""
        url = f"https://api.telegram.org/bot{bot_token}/answerCallbackQuery"
        payload = {"callback_query_id": callback_id}
        if text:
            payload["text"] = text
        try:
            await client.post(url, json=payload, timeout=10)
        except Exception as e:
            logger.debug(f"[TG Bot] 应答回调失败: {e}")

    async def _edit_message(self, client: httpx.AsyncClient, bot_token: str, chat_id: int, message_id: int, text: str, reply_markup: Dict = None, parse_html: bool = True) -> bool:
        """编辑已发送的消息（HTML 解析失败自动回退纯文本）"""
        url = f"https://api.telegram.org/bot{bot_token}/editMessageText"
        payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
        }
        if parse_html:
            payload["parse_mode"] = "HTML"
        if reply_markup:
            payload["reply_markup"] = reply_markup

        for attempt in range(2):
            try:
                resp = await client.post(url, json=payload, timeout=10)
                if resp.status_code == 200:
                    return True
                if attempt == 0 and parse_html and resp.status_code == 400:
                    logger.warning(f"[TG Bot] 编辑消息 HTML 解析失败，回退纯文本: {resp.text[:200]}")
                    payload = {k: v for k, v in payload.items() if k != "parse_mode"}
                    payload["text"] = self._html_to_plain(text)
                    continue
                logger.error(f"[TG Bot] 编辑消息失败: {resp.status_code} - {resp.text}")
                return False
            except Exception as e:
                logger.error(f"[TG Bot] 编辑消息异常: {e}")
                return False

        return False

    async def _delete_message(self, client: httpx.AsyncClient, bot_token: str, chat_id: int, message_id: int) -> bool:
        """删除已发送的消息（用于撤回进度占位消息）"""
        url = f"https://api.telegram.org/bot{bot_token}/deleteMessage"
        payload = {"chat_id": chat_id, "message_id": message_id}
        try:
            resp = await client.post(url, json=payload, timeout=10)
            return resp.status_code == 200
        except Exception as e:
            logger.debug(f"[TG Bot] 删除消息失败: {e}")
            return False

    async def _send_chat_action(self, client: httpx.AsyncClient, bot_token: str, chat_id: int, action: str = "typing"):
        """发送聊天状态动作（typing 只持续 5 秒，由 _typing_loop 周期性重发）"""
        url = f"https://api.telegram.org/bot{bot_token}/sendChatAction"
        payload = {"chat_id": chat_id, "action": action}
        try:
            await client.post(url, json=payload, timeout=10)
        except Exception as e:
            logger.debug(f"[TG Bot] 发送 chat action 失败: {e}")

    async def _typing_loop(self, client: httpx.AsyncClient, bot_token: str, chat_id: int):
        """AI 处理期间持续显示「输入中…」状态"""
        while True:
            await self._send_chat_action(client, bot_token, chat_id)
            await asyncio.sleep(4.5)

    async def _set_my_commands(self, client: httpx.AsyncClient, bot_token: str):
        """注册 Bot 命令菜单（Telegram 输入框左侧的菜单按钮）"""
        url = f"https://api.telegram.org/bot{bot_token}/setMyCommands"
        payload = {
            "commands": [
                {"command": "status", "description": "查看系统状态"},
                {"command": "skills", "description": "查看可用技能"},
                {"command": "tools", "description": "查看/切换工具调用模式"},
                {"command": "stop", "description": "停止当前 AI 任务"},
                {"command": "clear", "description": "清空对话历史"},
                {"command": "help", "description": "显示帮助"},
            ]
        }
        try:
            resp = await client.post(url, json=payload, timeout=10)
            if resp.status_code != 200:
                logger.warning(f"[TG Bot] 注册命令菜单失败: {resp.text[:200]}")
        except Exception as e:
            logger.warning(f"[TG Bot] 注册命令菜单异常: {e}")

    # ==================== Agent 调用 ====================

    def _get_effective_tool_mode(self, chat_id: int) -> bool:
        """本会话的工具模式：未手动设置时跟随全局配置"""
        settings = self._chat_settings.get(chat_id, {})
        current = settings.get("use_tools")
        if current is not None:
            return bool(current)
        try:
            from routers.assistant import get_assistant_config
            return bool(get_assistant_config().get("use_tools", True))
        except Exception:
            return True

    async def _run_agent_with_progress(
        self, client: httpx.AsyncClient, bot_token: str,
        chat_id: int, text: str, status_msg_id: Optional[int]
    ) -> Tuple[str, Optional[Dict]]:
        """
        以事件方式运行 Agent，把工具调用进度实时编辑到占位消息上。
        返回 (最终文本, 结构化列表数据)。
        """
        from assistant.agent import Agent
        from routers.assistant import get_assistant_config, init_assistant, _build_agent_config

        init_assistant()

        config = get_assistant_config()
        if not config.get("base_url") or not config.get("model"):
            return "❌ 智能体未配置，请先在 AI 实验室中配置模型。", None

        agent_config = _build_agent_config(config)

        existing_messages = self._user_sessions.get(chat_id, [])
        agent = Agent(agent_config, existing_messages.copy() if existing_messages else None)

        status_lines: List[str] = []
        last_edit = 0.0

        async def refresh(force: bool = False):
            """把当前进度编辑到占位消息（限频 2 秒，force 跳过）"""
            nonlocal last_edit
            if not status_msg_id:
                return
            now = time.monotonic()
            if not force and now - last_edit < 2.0:
                return
            last_edit = now
            body = "\n".join(status_lines[-4:]) if status_lines else "思考中…"
            await self._edit_message(
                client, bot_token, chat_id, status_msg_id,
                "🤔 " + self._escape_html(body)
            )

        final_text = ""
        try:
            async for event in agent.run(text):
                event_type = event.get("type")
                if event_type == "skill":
                    status_lines.append(f"⚡ 技能: {event.get('skill_name', '')}")
                    await refresh(force=True)
                elif event_type == "tool_call":
                    status_lines.append(f"🔧 {event.get('tool_name', '')} …")
                    await refresh(force=True)
                elif event_type == "tool_result":
                    if status_lines:
                        mark = "✅" if event.get("success") else "❌"
                        status_lines[-1] = f"🔧 {event.get('tool_name', '')} {mark}"
                    await refresh()
                elif event_type == "warning":
                    status_lines.append(f"⚠️ {event.get('message', '')}")
                    await refresh()
                elif event_type == "response":
                    final_text = event.get("content", "")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"[TG Bot] 调用智能体失败: {e}", exc_info=True)
            final_text = f"❌ 智能体调用失败: {e}"

        self._user_sessions[chat_id] = agent.messages[-20:]
        self._save_state()

        if not final_text:
            final_text = "❌ 智能体返回空响应"

        return final_text, agent.last_list_data

    async def _call_simple_chat(self, chat_id: int, text: str) -> Tuple[str, None]:
        """纯对话模式（不走工具调用），直接请求 LLM 并维护会话历史"""
        from fastapi import HTTPException
        from routers.assistant import get_assistant_config, init_assistant, _simple_chat, ChatMessage

        init_assistant()

        config = get_assistant_config()
        if not config.get("base_url") or not config.get("model"):
            return "❌ 智能体未配置，请先在 AI 实验室中配置模型。", None

        history = self._user_sessions.get(chat_id, [])
        msgs = [
            ChatMessage(role=m["role"], content=m["content"])
            for m in history if m.get("role") in ("user", "assistant") and m.get("content")
        ]
        msgs.append(ChatMessage(role="user", content=text))

        try:
            data = await _simple_chat(msgs, config)
            content = ""
            choices = data.get("choices") or []
            if choices:
                content = (choices[0].get("message") or {}).get("content", "")
            content = (content or "").strip() or "❌ 智能体返回空响应"
            self._user_sessions[chat_id] = (
                history + [{"role": "user", "content": text}, {"role": "assistant", "content": content}]
            )[-20:]
            self._save_state()
            return content, None
        except HTTPException as e:
            detail = e.detail if isinstance(e.detail, str) else str(e.detail)
            return f"❌ 请求失败: {detail}", None
        except Exception as e:
            logger.error(f"[TG Bot] 纯对话调用失败: {e}", exc_info=True)
            return f"❌ 请求失败: {e}", None

    async def _process_ai_message(self, client: httpx.AsyncClient, bot_token: str, chat_id: int, text: str, reply_to: int = None):
        """
        完整处理一条 AI 对话消息：
        发送占位消息 → 持续 typing 状态 → 实时更新工具进度 → 完成后替换为最终回复。
        任务可被 /stop 取消。
        """
        status_msg_id: Optional[int] = None
        typing_task: Optional[asyncio.Task] = None
        final_text = ""
        list_data = None

        try:
            status_msg_id = await self._send_single_message(
                client, bot_token, chat_id, "🤔 思考中…", reply_to=reply_to
            )
            typing_task = asyncio.create_task(self._typing_loop(client, bot_token, chat_id))

            if self._get_effective_tool_mode(chat_id):
                final_text, list_data = await self._run_agent_with_progress(
                    client, bot_token, chat_id, text, status_msg_id
                )
            else:
                final_text, list_data = await self._call_simple_chat(chat_id, text)
        except asyncio.CancelledError:
            logger.info(f"[TG Bot] AI 任务被取消: chat={chat_id}")
            if status_msg_id:
                await self._edit_message(client, bot_token, chat_id, status_msg_id, "⏹️ 已停止")
            raise
        finally:
            if typing_task:
                typing_task.cancel()
            if self._chat_tasks.get(chat_id) is asyncio.current_task():
                self._chat_tasks.pop(chat_id, None)

        # ---- 发送最终结果（未被取消才会走到这里） ----
        if list_data and list_data.get("items"):
            # 结构化列表：撤掉进度占位，发送带订阅按钮的列表
            if status_msg_id:
                await self._delete_message(client, bot_token, chat_id, status_msg_id)
            sent = await self._send_list_with_buttons(client, bot_token, chat_id, list_data, reply_to=reply_to)
            if not sent:
                await self._send_message(client, bot_token, chat_id, final_text, reply_to=reply_to)
            return

        # 尝试把长列表文本转为分页消息
        if len(final_text) > 200 and await self._try_send_as_paginated(client, bot_token, chat_id, final_text, reply_to=reply_to):
            if status_msg_id:
                await self._delete_message(client, bot_token, chat_id, status_msg_id)
            return

        # 普通回复：把占位消息编辑为最终内容，超出部分作为新消息追加
        html = self._md_to_telegram_html(final_text)
        chunks = self._split_long_message(html, self.TELEGRAM_MSG_LIMIT)
        if status_msg_id:
            await self._edit_message(client, bot_token, chat_id, status_msg_id, chunks[0])
            rest = chunks[1:]
        else:
            rest = chunks
        for chunk in rest:
            await self._send_single_message(client, bot_token, chat_id, chunk)
            await asyncio.sleep(0.3)
    
    # ==================== 更新处理 ====================

    async def _handle_update(self, client: httpx.AsyncClient, bot_token: str, update: Dict, allowed_chats: List):
        update_id = update.get("update_id", 0)
        self._last_update_id = max(self._last_update_id, update_id)
        
        # 处理 callback query（inline keyboard 按钮点击）
        callback_query = update.get("callback_query")
        if callback_query:
            await self._handle_callback_query(client, bot_token, callback_query, allowed_chats)
            return

        # 处理普通消息
        message = update.get("message")
        if not message:
            return
        
        chat_id = message.get("chat", {}).get("id")
        text = message.get("text", "")
        message_id = message.get("message_id")
        
        if not text:
            return
        
        if allowed_chats and chat_id not in allowed_chats:
            logger.warning(f"[TG Bot] 未授权的 chat_id: {chat_id}")
            await self._send_message(client, bot_token, chat_id, "❌ 你没有权限使用此 Bot")
            return

        # 群聊门槛：私聊有必应；群聊只响应 /命令、@机器人、或回复机器人消息，
        # 避免群里每条闲聊文本都触发一次 AI 调用
        chat_type = (message.get("chat") or {}).get("type", "private")
        if chat_type in ("group", "supergroup") and not text.startswith("/"):
            mentioned = bool(self._bot_username) and f"@{self._bot_username}".lower() in text.lower()
            reply_from = ((message.get("reply_to_message") or {}).get("from") or {})
            reply_to_bot = reply_from.get("id") == self._bot_id
            if not (mentioned or reply_to_bot):
                return
            # 去掉 @提及 再交给 AI，避免模型看到无意义的 @xxx
            if self._bot_username and mentioned:
                text = re.sub(f"@{re.escape(self._bot_username)}\\s*", "", text, flags=re.IGNORECASE).strip() or text

        logger.info(f"[TG Bot] 收到消息 [{chat_id}]: {text[:50]}...")
        log_audit("TG Bot", "收到消息", f"[{chat_id}] {text[:50]}")
        
        if text.startswith("/"):
            response = await self._handle_command(chat_id, text)
            await self._send_message(client, bot_token, chat_id, response, reply_to=message_id)
        else:
            # AI 任务按 chat 隔离：同 chat 上一条没处理完时提示，避免交错
            task = self._chat_tasks.get(chat_id)
            if task and not task.done():
                await self._send_message(
                    client, bot_token, chat_id,
                    "⏳ 上一条消息还在处理中，请稍候…\n发送 /stop 可取消当前任务",
                    reply_to=message_id,
                )
                return
            # 独立任务运行，不阻塞轮询循环（其他命令/其他 chat 不受影响）
            self._chat_tasks[chat_id] = asyncio.create_task(
                self._process_ai_message(client, bot_token, chat_id, text, message_id)
            )

    async def _handle_command(self, chat_id: int, command: str) -> str:
        cmd = command.lower().strip()
        # 群聊中命令可能带 @BotName 后缀（如 /status@MyBot），剥掉再匹配
        cmd = re.sub(r"^(/\w+)@\w+", r"\1", cmd)

        if cmd == "/start":
            return (
                "👋 你好！我是番剧管家智能助手\n\n"
                "直接发消息即可对话，我可以帮你：\n"
                "• 搜索和订阅番剧（搜索结果带按钮，点击直接订阅）\n"
                "• 查询订阅、下载、整理、系统状态\n"
                "• 自动匹配技能完成复杂任务\n\n"
                "试试发送：查看我的订阅 或 推荐新番\n\n"
                "发送 /help 查看全部命令"
            )
        elif cmd == "/help":
            return (
                "📖 可用命令\n\n"
                "/status - 查看系统状态\n"
                "/skills - 查看可用技能\n"
                "/tools - 查看/切换工具调用模式\n"
                "/stop - 停止当前 AI 任务\n"
                "/clear - 清空对话历史\n"
                "/help - 显示帮助\n\n"
                "💡 对话过程中会实时显示正在调用的工具，随时可以 /stop 中断。"
            )
        elif cmd == "/clear":
            if chat_id in self._user_sessions:
                del self._user_sessions[chat_id]
            # 同时清除分页数据
            if chat_id in self._paginated_lists:
                del self._paginated_lists[chat_id]
            self._save_state()
            return "✅ 对话历史已清除"
        elif cmd == "/stop":
            task = self._chat_tasks.get(chat_id)
            if task and not task.done():
                task.cancel()
                return "⏹️ 正在停止当前任务…"
            return "当前没有正在执行的 AI 任务"
        elif cmd == "/skills":
            return await self._get_skills_text()
        elif cmd == "/tools" or cmd.startswith("/tools "):
            return self._handle_tools_command(chat_id, cmd)
        elif cmd == "/status":
            return await self._get_system_status(chat_id)
        else:
            return f"❓ 未知命令: {self._escape_html(command)}\n发送 /help 查看可用命令"

    def _handle_tools_command(self, chat_id: int, cmd: str) -> str:
        """/tools 查看或切换本会话的工具调用模式"""
        parts = cmd.split(maxsplit=1)
        arg = parts[1].strip().lower() if len(parts) > 1 else ""
        settings = self._chat_settings.setdefault(chat_id, {})

        if arg in ("on", "off"):
            settings["use_tools"] = (arg == "on")
            self._save_state()
        elif arg:
            return "用法：/tools on 开启，/tools off 关闭，/tools 查看当前状态"

        current = settings.get("use_tools")
        global_mode = True
        try:
            from routers.assistant import get_assistant_config
            global_mode = bool(get_assistant_config().get("use_tools", True))
        except Exception:
            pass
        effective = global_mode if current is None else current
        source = "跟随全局配置" if current is None else "本会话手动设置"
        hint = "" if arg in ("on", "off") else "\n\n发送 /tools on 或 /tools off 可切换"

        return (
            f"🛠 工具调用模式：{'开启' if effective else '关闭'}\n"
            f"（{source}，全局默认：{'开启' if global_mode else '关闭'}）{hint}\n\n"
            "开启后 AI 可调用订阅、整理、系统管理等工具；关闭则为纯对话模式。"
        )

    async def _get_skills_text(self) -> str:
        """/skills 列出已启用的技能"""
        try:
            from routers.assistant import init_assistant
            from assistant.skill_engine import SkillEngine

            init_assistant()
            skills = SkillEngine.list_skills()
            if not skills:
                return "暂无可用技能，可在 Web 端 AI 实验室中管理。"

            lines = ["⚡ 可用技能\n"]
            for s in skills:
                name = self._escape_html(s.name or s.id)
                desc = self._escape_html((s.description or "").strip())
                lines.append(f"• <b>{name}</b> - {desc}")
            lines.append("\n💬 对话中会按内容自动匹配技能；技能的启停管理在 Web 端 AI 实验室。")
            return "\n".join(lines)
        except Exception as e:
            logger.error(f"[TG Bot] 获取技能列表失败: {e}", exc_info=True)
            return f"❌ 获取技能失败: {e}"

    async def _get_system_status(self, chat_id: int) -> str:
        try:
            from database import get_db_session
            from models import Subscription

            with get_db_session() as session:
                sub_count = session.query(Subscription).filter(Subscription.status == "active").count()

            config = ConfigManager.get_config()
            assistant_config = config.get("assistant_config", {})
            effective_mode = self._get_effective_tool_mode(chat_id)
            history_count = len(self._user_sessions.get(chat_id, []))

            return (
                "📊 系统状态\n\n"
                f"• 活跃订阅: {sub_count} 个\n"
                f"• 智能体模型: {self._escape_html(str(assistant_config.get('model', '未配置')))}\n"
                f"• 工具模式: {'开启' if effective_mode else '关闭'}\n"
                f"• 会话消息: {history_count} 条\n"
                f"• Telegram Bot: 运行中 ✅"
            )
        except Exception as e:
            return f"❌ 获取状态失败: {e}"
    
    # ==================== 状态持久化 ====================

    def _load_state(self):
        """启动时恢复对话历史和会话设置"""
        try:
            if not os.path.exists(TG_STATE_FILE):
                return
            with open(TG_STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            sessions = data.get("sessions") or {}
            self._user_sessions = {
                int(k): v for k, v in sessions.items()
                if isinstance(v, list) and v
            }
            settings = data.get("settings") or {}
            self._chat_settings = {
                int(k): v for k, v in settings.items() if isinstance(v, dict)
            }
            logger.info(f"[TG Bot] 已恢复 {len(self._user_sessions)} 个会话历史")
        except Exception as e:
            logger.warning(f"[TG Bot] 加载会话状态失败: {e}")

    def _save_state(self):
        """对话历史/设置变更后落盘"""
        try:
            data = {
                "sessions": {str(k): v[-20:] for k, v in self._user_sessions.items()},
                "settings": {str(k): v for k, v in self._chat_settings.items()},
            }
            tmp = TG_STATE_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            os.replace(tmp, TG_STATE_FILE)
        except Exception as e:
            logger.warning(f"[TG Bot] 保存会话状态失败: {e}")

    async def _fetch_bot_identity(self, client: httpx.AsyncClient, bot_token: str):
        """获取 Bot 身份，用于群聊中识别 @提及 和 回复机器人"""
        url = f"https://api.telegram.org/bot{bot_token}/getMe"
        try:
            resp = await client.post(url, json={}, timeout=10)
            data = resp.json()
            if resp.status_code == 200 and data.get("ok"):
                result = data.get("result", {})
                self._bot_id = result.get("id") or 0
                self._bot_username = result.get("username") or ""
                logger.info(f"[TG Bot] Bot 身份: @{self._bot_username}")
        except Exception as e:
            logger.warning(f"[TG Bot] 获取 Bot 身份失败: {e}")

    async def _poll_loop(self):
        bot_config = self._get_bot_config()
        bot_token = bot_config["bot_token"]
        allowed_chats = bot_config["allowed_chats"]
        proxy = bot_config.get("proxy")
        
        if not bot_token:
            logger.error("[TG Bot] 未配置 Bot Token")
            return
        
        logger.info(f"[TG Bot] 开始长轮询，allowed_chats: {allowed_chats or '无限制'}")
        log_audit("TG Bot", "启动", "长轮询模式")

        async with httpx.AsyncClient(proxy=proxy, timeout=35.0) as client:
            # 注册 Bot 命令菜单（输入框左侧菜单按钮）+ 获取 Bot 身份
            await self._set_my_commands(client, bot_token)
            await self._fetch_bot_identity(client, bot_token)
            while self._running:
                try:
                    updates = await self._get_updates(client, bot_token, proxy)
                    
                    for update in updates:
                        await self._handle_update(client, bot_token, update, allowed_chats)
                        
                except asyncio.CancelledError:
                    logger.info("[TG Bot] 轮询任务被取消")
                    break
                except Exception as e:
                    logger.error(f"[TG Bot] 轮询异常: {e}")
                    await asyncio.sleep(5)
        
        logger.info("[TG Bot] 轮询已停止")
        log_audit("TG Bot", "停止", "长轮询结束")
    
    def start(self):
        if self._running:
            logger.warning("[TG Bot] 已经在运行中")
            return

        bot_config = self._get_bot_config()
        if not bot_config["enabled"]:
            logger.info("[TG Bot] 功能未启用")
            return

        if not bot_config["bot_token"]:
            logger.error("[TG Bot] 未配置 Bot Token")
            return

        self._load_state()
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("[TG Bot] 已启动")
    
    def stop(self):
        if not self._running:
            return

        self._running = False

        if self._task:
            self._task.cancel()
            self._task = None

        # 取消所有进行中的 AI 对话任务
        for chat_task in self._chat_tasks.values():
            chat_task.cancel()
        self._chat_tasks.clear()

        self._save_state()
        logger.info("[TG Bot] 已停止")
    
    def is_running(self) -> bool:
        return self._running
    
    def restart(self):
        self.stop()
        self.start()


async def start_telegram_bot():
    bot = TelegramBot.get_instance()
    bot.start()


async def stop_telegram_bot():
    bot = TelegramBot.get_instance()
    bot.stop()


async def restart_telegram_bot():
    bot = TelegramBot.get_instance()
    bot.restart()
