import asyncio
import logging
import httpx
import json
import re
from typing import Optional, Dict, List, Any
from config_manager import ConfigManager
from logger import log_audit

logger = logging.getLogger("TelegramBot")

# 每页显示的条目数
ITEMS_PER_PAGE = 10


class TelegramBot:
    _instance: Optional["TelegramBot"] = None
    _running: bool = False
    _task: Optional[asyncio.Task] = None
    _last_update_id: int = 0
    _user_sessions: Dict[int, List[Dict]] = {}
    # 存储每个 chat 的分页列表数据：{chat_id: {"items": [...], "title": "...", "page": 0, "total": N, "msg_id": 123}}
    _paginated_lists: Dict[int, Dict[str, Any]] = {}
    
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

    async def _send_message(self, client: httpx.AsyncClient, bot_token: str, chat_id: int, text: str, reply_to: int = None, reply_markup: Dict = None) -> bool:
        """
        发送消息，自动处理超长消息分片。
        Telegram sendMessage 单条消息限制 4096 字符，超过时按行拆分依次发送。
        :param reply_markup: 可选的 inline keyboard
        :return: 全部分片发送成功返回 True，任一失败返回 False
        """
        if not text:
            return True

        chunks = self._split_long_message(text, self.TELEGRAM_MSG_LIMIT)

        if len(chunks) == 1:
            return await self._send_single_message(client, bot_token, chat_id, chunks[0], reply_to, reply_markup)

        logger.info(f"[TG Bot] 消息过长({len(text)}字符)，拆分为 {len(chunks)} 条发送")
        all_success = True
        for idx, chunk in enumerate(chunks):
            # 只有第一条回复用户原消息，避免多条消息都@原消息造成刷屏
            chunk_reply_to = reply_to if idx == 0 else None
            # 只有第一条附带 reply_markup（翻页按钮）
            chunk_markup = reply_markup if idx == 0 else None
            if not await self._send_single_message(client, bot_token, chat_id, chunk, chunk_reply_to, chunk_markup):
                all_success = False
            # 避免发送过快触发 Telegram 速率限制
            await asyncio.sleep(0.3)

        return all_success

    async def _send_single_message(self, client: httpx.AsyncClient, bot_token: str, chat_id: int, text: str, reply_to: int = None, reply_markup: Dict = None) -> bool:
        """发送单条消息（不超过 4096 字符）"""
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        
        if reply_to:
            payload["reply_to_message_id"] = reply_to

        if reply_markup:
            payload["reply_markup"] = reply_markup
        
        try:
            resp = await client.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                return True
            else:
                logger.error(f"[TG Bot] 发送消息失败: {resp.status_code} - {resp.text}")
        except Exception as e:
            logger.error(f"[TG Bot] 发送消息异常: {e}")
        
        return False

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

    async def _try_send_as_paginated(self, client: httpx.AsyncClient, bot_token: str, chat_id: int, text: str, reply_to: int = None) -> bool:
        """
        尝试将 Agent 返回的长列表消息转为带翻页按钮的消息。
        如果消息不包含编号列表或不够长，返回 False 走普通发送。
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

    async def _edit_message(self, client: httpx.AsyncClient, bot_token: str, chat_id: int, message_id: int, text: str, reply_markup: Dict = None) -> bool:
        """编辑已发送的消息"""
        url = f"https://api.telegram.org/bot{bot_token}/editMessageText"
        payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": "HTML"
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup

        try:
            resp = await client.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                return True
            else:
                logger.error(f"[TG Bot] 编辑消息失败: {resp.status_code} - {resp.text}")
        except Exception as e:
            logger.error(f"[TG Bot] 编辑消息异常: {e}")
        
        return False

    # ==================== Agent 调用 ====================

    async def _call_agent(self, chat_id: int, text: str) -> tuple:
        """调用 Agent，返回 (response_text, list_data) 元组"""
        try:
            from assistant.agent import Agent, AgentConfig
            from routers.assistant import get_assistant_config, init_assistant
            
            init_assistant()
            
            config = get_assistant_config()
            
            if not config.get("base_url") or not config.get("model"):
                return "❌ 智能体未配置，请先在 AI 实验室中配置模型。", None
            
            agent_config = AgentConfig(
                base_url=config.get("base_url", ""),
                api_key=config.get("api_key", ""),
                model=config.get("model", ""),
                provider=config.get("provider", "openai"),
                temperature=config.get("temperature", 0.7),
                max_tokens=config.get("max_tokens", 64) * 1000,
                max_iterations=config.get("max_iterations", 10)
            )
            
            existing_messages = self._user_sessions.get(chat_id, [])
            
            agent = Agent(agent_config, existing_messages.copy() if existing_messages else None)
            
            result = await agent.run_simple(text)
            
            self._user_sessions[chat_id] = agent.messages[-20:]
            
            # 获取 Agent 捕获的结构化列表数据
            list_data = agent.last_list_data
            
            if result:
                return result, list_data
            else:
                return "❌ 智能体返回空响应", None
                
        except ImportError as e:
            logger.error(f"[TG Bot] 导入智能体模块失败: {e}")
            return f"❌ 系统错误：无法加载智能体模块", None
        except Exception as e:
            logger.error(f"[TG Bot] 调用智能体失败: {e}", exc_info=True)
            return f"❌ 智能体调用失败: {str(e)}", None
    
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
        
        logger.info(f"[TG Bot] 收到消息 [{chat_id}]: {text[:50]}...")
        log_audit("TG Bot", "收到消息", f"[{chat_id}] {text[:50]}")
        
        if text.startswith("/"):
            response = await self._handle_command(chat_id, text)
            await self._send_message(client, bot_token, chat_id, response, reply_to=message_id)
        else:
            response, list_data = await self._call_agent(chat_id, text)
            
            # 优先使用结构化列表数据（带订阅按钮）
            if list_data and list_data.get("items"):
                sent = await self._send_list_with_buttons(client, bot_token, chat_id, list_data, reply_to=message_id)
                if not sent:
                    await self._send_message(client, bot_token, chat_id, response, reply_to=message_id)
            else:
                # 回退：尝试从文本解析列表进行分页
                sent = await self._try_send_as_paginated(client, bot_token, chat_id, response, reply_to=message_id)
                if not sent:
                    # 不是可分页列表，走普通发送
                    await self._send_message(client, bot_token, chat_id, response, reply_to=message_id)

    async def _handle_command(self, chat_id: int, command: str) -> str:
        cmd = command.lower().strip()
        
        if cmd == "/start":
            return (
                "👋 你好！我是番剧管家智能助手\n\n"
                "你可以直接发送消息与我对话，我可以帮你：\n"
                "• 搜索和订阅番剧\n"
                "• 查询系统状态\n"
                "• 整理文件\n"
                "• 回答动漫相关问题\n\n"
                "发送 /help 查看更多命令"
            )
        elif cmd == "/help":
            return (
                "📖 可用命令\n\n"
                "/start - 开始对话\n"
                "/help - 显示帮助\n"
                "/clear - 清除对话历史\n"
                "/status - 查看系统状态"
            )
        elif cmd == "/clear":
            if chat_id in self._user_sessions:
                del self._user_sessions[chat_id]
            # 同时清除分页数据
            if chat_id in self._paginated_lists:
                del self._paginated_lists[chat_id]
            return "✅ 对话历史已清除"
        elif cmd == "/status":
            return await self._get_system_status()
        else:
            return f"❓ 未知命令: {command}\n发送 /help 查看可用命令"
    
    async def _get_system_status(self) -> str:
        try:
            from database import get_db_session
            from models import Subscription
            
            with get_db_session() as session:
                sub_count = session.query(Subscription).filter(Subscription.status == "active").count()
            
            config = ConfigManager.get_config()
            assistant_config = config.get("assistant_config", {})
            
            return (
                "📊 系统状态\n\n"
                f"• 活跃订阅: {sub_count} 个\n"
                f"• 智能体模型: {assistant_config.get('model', '未配置')}\n"
                f"• Telegram Bot: 运行中 ✅"
            )
        except Exception as e:
            return f"❌ 获取状态失败: {e}"
    
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
