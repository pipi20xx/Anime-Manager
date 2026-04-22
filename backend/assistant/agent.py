import json
import logging
import asyncio
from typing import Dict, List, Optional, Any, AsyncGenerator, Callable
from dataclasses import dataclass, field
import httpx

from .tools import ToolRegistry, ToolResult
from .skill_engine import SkillEngine

logger = logging.getLogger(__name__)


@dataclass
class AgentMessage:
    role: str
    content: str
    tool_calls: List[Dict] = field(default_factory=list)
    tool_call_id: str = ""
    name: str = ""


@dataclass
class AgentConfig:
    base_url: str
    api_key: str
    model: str
    provider: str = "openai"
    temperature: float = 0.7
    max_tokens: int = 4096
    max_iterations: int = 10


class Agent:
    def __init__(self, config: AgentConfig):
        self.config = config
        self.messages: List[Dict] = []
        self.tool_results: List[Dict] = []
        self.iteration_count = 0
        self.on_tool_call: Optional[Callable] = None
        self.on_tool_result: Optional[Callable] = None
        self.on_thinking: Optional[Callable] = None
        
    def _get_system_prompt(self) -> str:
        tools_desc = ToolRegistry.get_tools_description()
        skills_desc = SkillEngine.get_all_skills_description()
        
        return f"""你是番剧管家的智能助手，一个强大的动漫资源管理 AI Agent。

## 核心能力

你不仅能回答问题，还能通过调用工具来执行实际操作：
- 搜索和查询媒体信息（TMDB、Bangumi）
- 管理订阅任务（添加、删除、查询）
- 执行文件整理和重命名
- 搜索和下载资源
- 查询系统状态和配置

## 工作原则

1. **理解用户意图**：分析用户请求，确定需要执行的操作
2. **选择合适工具**：根据需求选择正确的工具
3. **执行并反馈**：调用工具执行操作，向用户报告结果
4. **迭代优化**：如果结果不满意，可以尝试其他方法

## 重要规则

- 在执行修改操作前，先确认用户意图
- 工具调用失败时，向用户解释原因并提供替代方案
- 保持回复简洁，但包含关键信息
- 使用中文回复

{tools_desc}

{skills_desc}

## 当前时间
请根据用户的请求选择合适的工具执行操作。
"""

    def _get_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.config.provider == "openai" and self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers

    def _get_endpoint(self) -> str:
        base_url = self.config.base_url.strip().rstrip("/").rstrip(",")
        if "v1" in base_url or "chat/completions" in base_url:
            return f"{base_url}/chat/completions".replace("//chat", "/chat")
        return f"{base_url}/v1/chat/completions"

    async def _call_llm(self, stream: bool = False) -> Dict:
        endpoint = self._get_endpoint()
        headers = self._get_headers()
        
        tools = ToolRegistry.get_openai_tools()
        
        payload = {
            "model": self.config.model,
            "messages": self.messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        
        logger.info(f"[Agent] 调用 LLM: {endpoint}, model: {self.config.model}")
        logger.debug(f"[Agent] Messages: {json.dumps(self.messages[-3:], ensure_ascii=False)[:500]}")
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(endpoint, headers=headers, json=payload)
            
            if response.status_code != 200:
                error_text = response.text
                logger.error(f"[Agent] LLM 错误: {response.status_code} - {error_text}")
                raise Exception(f"LLM 调用失败: {error_text}")
            
            return response.json()

    async def _execute_tool(self, tool_name: str, arguments: Dict) -> ToolResult:
        tool_def = ToolRegistry.get(tool_name)
        if not tool_def:
            return ToolResult(success=False, error=f"工具 {tool_name} 不存在")
        
        logger.info(f"[Agent] 执行工具: {tool_name}, 参数: {arguments}")
        
        try:
            func = tool_def.func
            result = await func(**arguments)
            return result
        except Exception as e:
            logger.error(f"[Agent] 工具执行失败: {tool_name} - {e}", exc_info=True)
            return ToolResult(success=False, error=str(e))

    async def run(
        self,
        user_message: str,
        context: Optional[Dict] = None
    ) -> AsyncGenerator[Dict, None]:
        self.messages = [
            {"role": "system", "content": self._get_system_prompt()},
            {"role": "user", "content": user_message}
        ]
        
        matched_skill = SkillEngine.match_skill(user_message)
        if matched_skill:
            skill_prompt = SkillEngine.get_skill_prompt(matched_skill.id)
            self.messages[0]["content"] += f"\n\n{skill_prompt}"
            yield {
                "type": "skill",
                "skill_id": matched_skill.id,
                "skill_name": matched_skill.name,
                "message": f"检测到技能: {matched_skill.name}"
            }
        
        self.iteration_count = 0
        
        while self.iteration_count < self.config.max_iterations:
            self.iteration_count += 1
            
            try:
                response = await self._call_llm()
            except Exception as e:
                yield {"type": "error", "message": str(e)}
                return
            
            logger.debug(f"[Agent] LLM 响应: {json.dumps(response, ensure_ascii=False)[:1000]}")
            
            choice = response.get("choices", [{}])[0]
            message = choice.get("message", {})
            
            content = message.get("content", "") or ""
            tool_calls = message.get("tool_calls", [])
            
            finish_reason = choice.get("finish_reason", "")
            logger.info(f"[Agent] finish_reason: {finish_reason}, content长度: {len(content)}, tool_calls数量: {len(tool_calls)}")
            
            if content:
                yield {
                    "type": "thinking",
                    "content": content
                }
            
            if tool_calls:
                assistant_message = {
                    "role": "assistant",
                    "content": content,
                    "tool_calls": []
                }
                
                for tool_call in tool_calls:
                    tool_call_id = tool_call.get("id", "")
                    function = tool_call.get("function", {})
                    tool_name = function.get("name", "")
                    
                    try:
                        arguments = json.loads(function.get("arguments", "{}"))
                    except:
                        arguments = {}
                    
                    assistant_message["tool_calls"].append({
                        "id": tool_call_id,
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "arguments": function.get("arguments", "{}")
                        }
                    })
                    
                    yield {
                        "type": "tool_call",
                        "tool_name": tool_name,
                        "arguments": arguments,
                        "message": f"正在调用工具: {tool_name}"
                    }
                    
                    result = await self._execute_tool(tool_name, arguments)
                    
                    yield {
                        "type": "tool_result",
                        "tool_name": tool_name,
                        "result": result.to_dict(),
                        "success": result.success,
                        "message": result.message or ("执行成功" if result.success else f"执行失败: {result.error}")
                    }
                    
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "name": tool_name,
                        "content": result.to_json()
                    })
                
                self.messages.append(assistant_message)
                continue
            
            if content:
                yield {
                    "type": "response",
                    "content": content
                }
                break
            
            if not tool_calls and not content:
                logger.warning(f"[Agent] LLM 返回空响应，尝试继续")
                yield {
                    "type": "thinking",
                    "content": "让我重新整理一下信息..."
                }
                self.messages.append({
                    "role": "user",
                    "content": "请根据之前的工具调用结果，给出你的回答。"
                })
                continue
            
            break
        
        if self.iteration_count >= self.config.max_iterations:
            yield {
                "type": "warning",
                "message": "已达到最大迭代次数，请简化请求或分步执行"
            }

    async def run_simple(self, user_message: str) -> str:
        final_response = ""
        async for event in self.run(user_message):
            if event["type"] == "response":
                final_response = event.get("content", "")
            elif event["type"] == "error":
                final_response = f"错误: {event.get('message', '未知错误')}"
        
        return final_response


async def create_agent(config: Optional[Dict] = None) -> Agent:
    from config_manager import ConfigManager
    
    if config is None:
        config = ConfigManager.get_config().get("assistant_config", {})
    
    agent_config = AgentConfig(
        base_url=config.get("base_url", ""),
        api_key=config.get("api_key", ""),
        model=config.get("model", ""),
        provider=config.get("provider", "openai"),
        temperature=config.get("temperature", 0.7),
        max_tokens=config.get("max_tokens", 64) * 1000,
        max_iterations=config.get("max_iterations", 10)
    )
    
    return Agent(agent_config)
