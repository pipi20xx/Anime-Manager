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
    def __init__(self, config: AgentConfig, messages: List[Dict] = None):
        self.config = config
        self.messages: List[Dict] = messages if messages else []
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

- 工具调用后，你会在 tool 消息中收到真实的执行结果，请根据结果回答用户
- 不要说"没有实际执行"或"模拟输出"，工具确实执行了，结果就在 tool 消息中
- **主动完成任务**：如果用户说"帮我订阅"，你应该搜索作品、确认正确条目、然后执行订阅，而不是只返回搜索结果
- **完整执行流程**：不要在中间步骤停下来等用户确认，直接完成整个操作流程
- **订阅时优先使用 TMDB**：当用户要订阅番剧时，使用 search_tmdb 搜索，然后用 add_subscription 订阅
- **智能匹配季度**：当用户指定「第二季」「S2」时，在搜索结果中找到对应的条目
- 工具调用失败时，向用户解释原因并提供替代方案
- 保持回复简洁，但包含关键信息
- 使用中文回复

## 交互格式规范

### 订阅列表格式
显示订阅列表时，直接告诉用户如何操作：
```
📋 订阅列表
1. 日常 (S1, 1-43集) ✅
2. 孤独摇滚 (S1, 1-12集) ✅

💡 输入「序号+操作」如「1删除」「2禁用」
   操作：删除/禁用/启用/补全
```

### 操作选择格式
当用户选择某个订阅后，直接列出操作并等待用户输入：
```
「日常」操作：
1.删除  2.禁用  3.启用  4.补全

请输入数字。
```

### 重要规则
- 用户输入「1删除」或「删除1」时，直接调用 operate_subscription 工具执行删除
- 用户输入「1」后再输入「1」时，第二次输入视为操作选择，直接执行
- 不要反复询问，用户确认后立即执行
- 执行操作后显示结果，不要再说"您选择了..."

## 订阅流程

用户：「帮我订阅 XXX」
1. 调用 `search_tmdb("XXX", "tv")` 搜索作品
2. 从结果中找到最匹配的条目（注意季度匹配）
3. 调用 `add_subscription(title, tmdb_id, media_type="tv", season)` 订阅
4. 返回订阅成功消息

{tools_desc}

{skills_desc}

## 当前时间
请根据用户的请求选择合适的工具执行操作。
"""

    def _get_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers

    def _get_endpoint(self) -> str:
        base_url = self.config.base_url.strip().rstrip("/").rstrip(",")
        
        if base_url.endswith("/chat/completions"):
            return base_url
        
        if "/v1/chat/completions" in base_url:
            return base_url
        
        if "bigmodel.cn" in base_url or "zhipuai" in base_url:
            return f"{base_url}/chat/completions"
        
        if base_url.endswith("/v1"):
            return f"{base_url}/chat/completions"
        
        if "/v1/" in base_url:
            return f"{base_url}/chat/completions"
        
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
    
    def _try_parse_tool_call(self, content: str) -> Optional[Dict]:
        """
        尝试从文本中解析工具调用（用于不支持 function calling 的模型）
        支持格式：
        - 调用 search_tmdb("xxx")
        - search_tmdb("xxx")
        - 调用 `search_tmdb("xxx")`
        """
        if not content:
            return None
        
        import re
        
        patterns = [
            r'(?:调用\s*)?`?(\w+)\s*\(\s*(.+?)\s*\)`?',
            r'(?:调用\s*)?`?(\w+)\s*\(\s*["\'](.+?)["\']\s*\)`?',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                tool_name = match.group(1)
                args_str = match.group(2)
                
                if not ToolRegistry.get(tool_name):
                    continue
                
                arguments = {}
                
                if args_str:
                    try:
                        if args_str.startswith('{') or args_str.startswith('['):
                            arguments = json.loads(args_str)
                        else:
                            args_str_clean = args_str.strip('\'"')
                            first_param = ToolRegistry.get(tool_name)
                            if first_param and first_param.parameters:
                                param_name = first_param.parameters[0].name
                                arguments[param_name] = args_str_clean
                            else:
                                arguments["query"] = args_str_clean
                    except:
                        param_name = "query"
                        if ToolRegistry.get(tool_name) and ToolRegistry.get(tool_name).parameters:
                            param_name = ToolRegistry.get(tool_name).parameters[0].name
                        arguments[param_name] = args_str.strip('\'"')
                
                logger.info(f"[Agent] 从文本解析到工具调用: {tool_name}({arguments})")
                return {"name": tool_name, "arguments": arguments}
        
        return None

    async def run(
        self,
        user_message: str,
        context: Optional[Dict] = None
    ) -> AsyncGenerator[Dict, None]:
        if not self.messages:
            self.messages = [
                {"role": "system", "content": self._get_system_prompt()}
            ]
        elif not any(m.get("role") == "system" for m in self.messages):
            self.messages.insert(0, {"role": "system", "content": self._get_system_prompt()})
        
        self.messages.append({"role": "user", "content": user_message})
        
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
                
                tool_results_messages = []
                has_formatted_output = False
                
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
                    
                    if result.formatted_message:
                        has_formatted_output = True
                        yield {
                            "type": "response",
                            "content": result.formatted_message
                        }
                        assistant_message["content"] = result.formatted_message
                    
                    tool_results_messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "name": tool_name,
                        "content": result.to_json()
                    })
                
                self.messages.append(assistant_message)
                self.messages.extend(tool_results_messages)
                
                if has_formatted_output:
                    return
                
                continue
            
            parsed_tool_call = self._try_parse_tool_call(content)
            if parsed_tool_call:
                tool_name = parsed_tool_call.get("name")
                arguments = parsed_tool_call.get("arguments", {})
                
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
                    "role": "assistant",
                    "content": content
                })
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": f"parsed_{tool_name}",
                    "name": tool_name,
                    "content": result.to_json()
                })
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
