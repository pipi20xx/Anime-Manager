import os
import json
import logging
from typing import List, Dict, Optional
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from config_manager import ConfigManager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/assistant", tags=["Assistant"])

def _get_skills_dir() -> str:
    possible_paths = [
        "/app/skills",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "skills"),
        os.path.join(os.getcwd(), "skills"),
    ]
    for path in possible_paths:
        if os.path.exists(path):
            return path
    return "/app/skills"

SKILLS_DIR = _get_skills_dir()

_initialized = False

def init_assistant():
    global _initialized
    if _initialized:
        return
    
    try:
        from assistant.tools import register_builtin_tools
        register_builtin_tools()
    except Exception as e:
        logger.error(f"[Assistant] 工具注册失败: {e}", exc_info=True)
    
    try:
        from assistant.skill_engine import SkillEngine
        SkillEngine.load_skills(SKILLS_DIR)
    except Exception as e:
        logger.error(f"[Assistant] 技能加载失败: {e}", exc_info=True)
    
    _initialized = True
    logger.info("[Assistant] 智能助手初始化完成")


class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    stream: bool = False
    use_tools: bool = True

class ConfigUpdate(BaseModel):
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    max_iterations: Optional[int] = None

def get_assistant_config() -> Dict:
    config = ConfigManager.get_config()
    return config.get("assistant_config", {
        "base_url": "",
        "api_key": "",
        "model": "",
        "provider": "openai",
        "temperature": 0.7,
        "max_tokens": 64,
        "max_iterations": 10
    })

def save_assistant_config(new_config: Dict):
    current_config = ConfigManager.get_config()
    if "assistant_config" not in current_config:
        current_config["assistant_config"] = {}
    
    if "base_url" in new_config and new_config["base_url"]:
        new_config["base_url"] = new_config["base_url"].strip().rstrip("/").rstrip(",")
    
    current_config["assistant_config"].update(new_config)
    ConfigManager.update_config({"assistant_config": current_config["assistant_config"]})

@router.get("/config")
async def get_config():
    return get_assistant_config()

@router.post("/config")
async def update_config(config: ConfigUpdate):
    config_dict = config.dict(exclude_none=True)
    save_assistant_config(config_dict)
    return {"success": True, "message": "配置已保存"}

@router.post("/chat")
async def chat(request: ChatRequest):
    init_assistant()
    
    config = get_assistant_config()
    
    if not config.get("base_url") or not config.get("model"):
        raise HTTPException(status_code=400, detail="请先配置模型地址和模型名称")
    
    if not request.use_tools:
        return await _simple_chat(request.messages, config)
    
    messages = [{"role": m.role, "content": m.content} for m in request.messages]
    
    if request.stream:
        return await _agent_chat_stream(messages, config)
    else:
        return await _agent_chat(messages, config)

async def _simple_chat(messages: List[ChatMessage], config: Dict):
    import httpx
    
    base_url = config.get("base_url", "").strip().rstrip("/").rstrip(",")
    target_url = f"{base_url}/v1/chat/completions" if "v1" not in base_url else f"{base_url}/chat/completions"
    
    headers = {"Content-Type": "application/json"}
    if config.get("provider") == "openai" and config.get("api_key"):
        headers["Authorization"] = f"Bearer {config['api_key']}"
    
    system_prompt = """你是番剧管家的智能助手，帮助用户管理动漫资源。

你可以帮助用户：
1. 分析识别失败的资源并提供解决方案
2. 推荐订阅新番剧
3. 解答关于番剧管家功能的问题
4. 协助配置和优化系统

请用中文回复，保持简洁友好。"""
    
    full_messages = [{"role": "system", "content": system_prompt}]
    full_messages.extend([{"role": m.role, "content": m.content} for m in messages])
    
    payload = {
        "model": config.get("model"),
        "messages": full_messages,
        "temperature": config.get("temperature", 0.7),
        "max_tokens": config.get("max_tokens", 64) * 1000,
    }
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(target_url, headers=headers, json=payload)
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.text)
        return response.json()

async def _agent_chat(messages: List[Dict], config: Dict):
    try:
        from assistant.agent import Agent, AgentConfig
    except ImportError as e:
        logger.error(f"[Assistant] 导入 Agent 失败: {e}", exc_info=True)
        return {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": f"系统错误：无法加载智能助手模块 ({e})"
                }
            }],
            "events": [{"type": "error", "message": str(e)}]
        }
    
    agent_config = AgentConfig(
        base_url=config.get("base_url", ""),
        api_key=config.get("api_key", ""),
        model=config.get("model", ""),
        provider=config.get("provider", "openai"),
        temperature=config.get("temperature", 0.7),
        max_tokens=config.get("max_tokens", 64) * 1000,
        max_iterations=config.get("max_iterations", 10)
    )
    
    agent = Agent(agent_config, messages=messages[:-1])
    
    user_message = messages[-1].get("content", "") if messages else ""
    
    events = []
    final_content = ""
    
    try:
        async for event in agent.run(user_message):
            events.append(event)
            if event["type"] == "response":
                final_content = event.get("content", "")
            elif event["type"] == "error":
                final_content = f"错误: {event.get('message', '未知错误')}"
    except Exception as e:
        logger.error(f"[Assistant] Agent 运行失败: {e}", exc_info=True)
        events.append({"type": "error", "message": str(e)})
        final_content = f"执行错误: {str(e)}"
    
    return {
        "choices": [{
            "message": {
                "role": "assistant",
                "content": final_content
            }
        }],
        "events": events
    }

async def _agent_chat_stream(messages: List[Dict], config: Dict):
    from assistant.agent import Agent, AgentConfig
    
    agent_config = AgentConfig(
        base_url=config.get("base_url", ""),
        api_key=config.get("api_key", ""),
        model=config.get("model", ""),
        provider=config.get("provider", "openai"),
        temperature=config.get("temperature", 0.7),
        max_tokens=config.get("max_tokens", 64) * 1000,
        max_iterations=config.get("max_iterations", 10)
    )
    
    agent = Agent(agent_config, messages=messages[:-1])
    
    user_message = messages[-1].get("content", "") if messages else ""
    
    async def generate():
        try:
            async for event in agent.run(user_message):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@router.get("/tools")
async def list_tools():
    init_assistant()
    
    from assistant.tools import ToolRegistry
    
    tools = []
    for tool_def in ToolRegistry.list_all():
        tools.append({
            "name": tool_def.name,
            "description": tool_def.description,
            "category": tool_def.category,
            "parameters": [
                {
                    "name": p.name,
                    "type": p.type,
                    "description": p.description,
                    "required": p.required
                }
                for p in tool_def.parameters
            ]
        })
    
    return tools

@router.get("/tools/categories")
async def list_tool_categories():
    init_assistant()
    
    from assistant.tools import ToolRegistry
    
    categories = {}
    for category, tool_names in ToolRegistry._categories.items():
        categories[category] = [
            {"name": name, "description": ToolRegistry.get(name).description}
            for name in tool_names
        ]
    
    return categories

@router.get("/skills")
async def list_skills():
    init_assistant()
    
    from assistant.skill_engine import SkillEngine
    
    skills = []
    for skill in SkillEngine.list_skills():
        skills.append({
            "id": skill.id,
            "name": skill.name,
            "version": skill.version,
            "description": skill.description,
            "triggers": skill.triggers,
            "path": skill.path
        })
    
    return skills

@router.get("/skills/{skill_id}")
async def get_skill(skill_id: str):
    init_assistant()
    
    from assistant.skill_engine import SkillEngine
    
    skill = SkillEngine.get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="技能不存在")
    
    return {
        "id": skill.id,
        "name": skill.name,
        "version": skill.version,
        "description": skill.description,
        "content": skill.content,
        "triggers": skill.triggers,
        "tools_needed": skill.tools_needed,
        "path": skill.path
    }

@router.post("/skills/{skill_id}/execute")
async def execute_skill(skill_id: str, request: Request):
    init_assistant()
    
    from assistant.skill_engine import SkillEngine
    
    skill = SkillEngine.get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="技能不存在")
    
    body = await request.json()
    params = body.get("params", {})
    user_message = body.get("message", f"执行技能: {skill.name}")
    
    config = get_assistant_config()
    if not config.get("base_url") or not config.get("model"):
        raise HTTPException(status_code=400, detail="请先配置模型地址和模型名称")
    
    from assistant.agent import Agent, AgentConfig
    
    agent_config = AgentConfig(
        base_url=config.get("base_url", ""),
        api_key=config.get("api_key", ""),
        model=config.get("model", ""),
        provider=config.get("provider", "openai"),
        temperature=config.get("temperature", 0.7),
        max_tokens=config.get("max_tokens", 64) * 1000,
        max_iterations=config.get("max_iterations", 10)
    )
    
    agent = Agent(agent_config)
    
    skill_prompt = SkillEngine.get_skill_prompt(skill_id)
    enhanced_message = f"{skill_prompt}\n\n用户请求: {user_message}"
    
    events = []
    async for event in agent.run(enhanced_message):
        events.append(event)
    
    return {
        "skill_id": skill_id,
        "skill_name": skill.name,
        "events": events
    }

@router.post("/tools/{tool_name}/execute")
async def execute_tool_directly(tool_name: str, request: Request):
    init_assistant()
    
    from assistant.tools import ToolRegistry
    
    tool_def = ToolRegistry.get(tool_name)
    if not tool_def:
        raise HTTPException(status_code=404, detail=f"工具 {tool_name} 不存在")
    
    body = await request.json()
    arguments = body.get("arguments", {})
    
    try:
        func = tool_def.func
        result = await func(**arguments)
        
        if hasattr(result, 'to_dict'):
            return result.to_dict()
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"[Assistant] 工具执行失败: {tool_name} - {e}")
        return {"success": False, "error": str(e)}
