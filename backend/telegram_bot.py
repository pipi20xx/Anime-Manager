import asyncio
import logging
import httpx
from typing import Optional, Dict, List
from config_manager import ConfigManager
from notification import NotificationManager
from logger import log_audit

logger = logging.getLogger("TelegramBot")


class TelegramBot:
    _instance: Optional["TelegramBot"] = None
    _running: bool = False
    _task: Optional[asyncio.Task] = None
    _last_update_id: int = 0
    _user_sessions: Dict[int, List[Dict]] = {}
    
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
    
    async def _send_message(self, client: httpx.AsyncClient, bot_token: str, chat_id: int, text: str, reply_to: int = None) -> bool:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        
        if reply_to:
            payload["reply_to_message_id"] = reply_to
        
        try:
            resp = await client.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                return True
            else:
                logger.error(f"[TG Bot] 发送消息失败: {resp.status_code} - {resp.text}")
        except Exception as e:
            logger.error(f"[TG Bot] 发送消息异常: {e}")
        
        return False
    
    async def _call_agent(self, chat_id: int, text: str) -> str:
        try:
            from assistant.agent import Agent, AgentConfig
            from routers.assistant import get_assistant_config, init_assistant
            
            init_assistant()
            
            config = get_assistant_config()
            
            if not config.get("base_url") or not config.get("model"):
                return "❌ 智能体未配置，请先在 AI 实验室中配置模型。"
            
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
            
            if result:
                return result
            else:
                return "❌ 智能体返回空响应"
                
        except ImportError as e:
            logger.error(f"[TG Bot] 导入智能体模块失败: {e}")
            return f"❌ 系统错误：无法加载智能体模块"
        except Exception as e:
            logger.error(f"[TG Bot] 调用智能体失败: {e}", exc_info=True)
            return f"❌ 智能体调用失败: {str(e)}"
    
    async def _handle_update(self, client: httpx.AsyncClient, bot_token: str, update: Dict, allowed_chats: List):
        update_id = update.get("update_id", 0)
        self._last_update_id = max(self._last_update_id, update_id)
        
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
        else:
            response = await self._call_agent(chat_id, text)
        
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
