import os
import asyncio
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
    skill_id: Optional[str] = None
    # Agent 内部历史快照（含摘要/工具消息），作为种子回传，优于纯文本对话历史
    agent_history: Optional[List[Dict]] = None

class ConfigUpdate(BaseModel):
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    max_iterations: Optional[int] = None
    # 历史管理：条数 + token 双上限
    max_history_messages: Optional[int] = None
    max_history_tokens: Optional[int] = None
    # 思考深度：off/auto/minimal/low/medium/high/max/xhigh
    thinking_level: Optional[str] = None
    ai_fallback_enabled: Optional[bool] = None
    use_tools: Optional[bool] = None
    enable_dynamic_tools: Optional[bool] = None
    enable_llm_summary: Optional[bool] = None


class ProbeRequest(BaseModel):
    """能力探测/模型列表的可选覆盖参数（不传则用已保存的配置）"""
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None
    provider: Optional[str] = None


def get_assistant_config() -> Dict:
    config = ConfigManager.get_config()
    return config.get("assistant_config", {
        "base_url": "",
        "api_key": "",
        "model": "",
        "provider": "ollama",
        "temperature": 0.7,
        "max_tokens": 64,
        "max_iterations": 10,
        "max_history_messages": 20,
        "max_history_tokens": 24000,
        "thinking_level": "auto",
        "ai_fallback_enabled": False,
        "use_tools": True,
        "enable_dynamic_tools": True,
        "enable_llm_summary": True
    })

def _build_agent_config(config: Dict):
    """统一从 assistant_config 构造 AgentConfig（含动态工具/摘要等开关）"""
    from assistant.agent import AgentConfig

    return AgentConfig(
        base_url=config.get("base_url", ""),
        api_key=config.get("api_key", ""),
        model=config.get("model", ""),
        provider=config.get("provider", "openai"),
        temperature=config.get("temperature", 0.7),
        max_tokens=config.get("max_tokens", 64) * 1000,
        max_iterations=config.get("max_iterations", 10),
        max_history_messages=config.get("max_history_messages", 20),
        max_history_tokens=config.get("max_history_tokens", 24000),
        thinking_level=config.get("thinking_level", "auto"),
        summarize_threshold=config.get("summarize_threshold", 10),
        enable_dynamic_tools=bool(config.get("enable_dynamic_tools", True)),
        compact_tool_results=bool(config.get("compact_tool_results", True)),
        enable_llm_summary=bool(config.get("enable_llm_summary", True)),
    )

def _clean_agent_history(agent_history: Optional[List[Dict]]) -> Optional[List[Dict]]:
    """清洗前端回传的内部历史快照，非法条目直接丢弃"""
    if not agent_history:
        return None
    allowed = ("system", "user", "assistant", "tool")
    cleaned = [
        m for m in agent_history
        if isinstance(m, dict) and m.get("role") in allowed
    ]
    return cleaned[-40:] if cleaned else None

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


# ==================== 模型能力：列表 / 探测 / 缓存 ====================

def _resolve_probe_targets(override: Optional[ProbeRequest]) -> Dict[str, str]:
    """探测目标：请求体里的覆盖值优先，缺省用已保存的配置"""
    config = get_assistant_config()
    override = override or ProbeRequest()
    return {
        "base_url": (override.base_url or config.get("base_url") or "").strip(),
        "api_key": override.api_key if override.api_key is not None else (config.get("api_key") or ""),
        "model": (override.model or config.get("model") or "").strip(),
        "provider": override.provider or config.get("provider") or "openai",
    }


@router.get("/models", summary="拉取模型列表")
async def list_available_models():
    """
    拉取当前 API 地址上的模型列表（OpenAI 兼容 /v1/models；Ollama 用 /api/tags）。
    上下文长度等非标准字段能拿到就带上，拿不到就是 null —— 不做任何猜测。
    """
    import asyncio
    from assistant import llm_capabilities

    target = _resolve_probe_targets(None)
    if not target["base_url"]:
        raise HTTPException(status_code=400, detail="请先填写 API 地址")

    result = await asyncio.to_thread(
        llm_capabilities.list_models, target["base_url"], target["api_key"], target["provider"]
    )
    if not result.get("ok"):
        raise HTTPException(status_code=502, detail=f"拉取模型列表失败：{result.get('message')}")
    return result


@router.post("/probe", summary="探测模型能力（思考深度 / 上下文）")
async def probe_model_capability(override: Optional[ProbeRequest] = None):
    """
    探测当前模型支持哪种「关闭思考」的参数风格，结果按 (base_url, model) 缓存。
    顺带从 /models 里尽力补全上下文长度等元数据。
    """
    import asyncio
    from assistant import llm_capabilities

    target = _resolve_probe_targets(override)
    if not target["base_url"] or not target["model"]:
        raise HTTPException(status_code=400, detail="请先配置 API 地址与模型名称")

    result = await asyncio.to_thread(
        llm_capabilities.probe,
        target["base_url"],
        target["api_key"],
        target["model"],
        target["provider"],
    )
    if not result.get("ok"):
        detail = result.get("message") or result.get("errors") or "未知错误"
        raise HTTPException(status_code=502, detail=f"探测失败：{detail}")

    # 很多网关只在模型列表里给上下文长度，这里顺手补全并回写缓存
    try:
        models = await asyncio.to_thread(
            llm_capabilities.list_models, target["base_url"], target["api_key"], target["provider"]
        )
        if models.get("ok"):
            for item in models.get("models", []):
                if item.get("id") == target["model"]:
                    result["context_length"] = result.get("context_length") or item.get("context_length")
                    result["max_output_tokens"] = result.get("max_output_tokens") or item.get("max_output_tokens")
                    break
            llm_capabilities.save_cached(target["base_url"], target["model"], result)
    except Exception as e:
        logger.debug(f"[Assistant] 补全模型元数据失败: {e}")

    return result


@router.get("/capabilities", summary="读取已缓存的模型能力")
async def get_model_capabilities():
    from assistant import llm_capabilities

    target = _resolve_probe_targets(None)
    return {
        "cached": llm_capabilities.get_cached(target["base_url"], target["model"]),
        "levels": [
            {"value": level, "label": llm_capabilities.THINKING_LEVEL_LABELS.get(level, level)}
            for level in llm_capabilities.THINKING_LEVELS
        ],
        "styles": [
            {
                "value": key,
                "label": llm_capabilities.style_label(key),
                "levels": llm_capabilities.supported_levels(key),
            }
            for key in ("none", *llm_capabilities.PROBE_ORDER)
        ],
    }


@router.delete("/capabilities", summary="清除模型能力缓存")
async def clear_model_capabilities():
    from assistant import llm_capabilities

    removed = llm_capabilities.clear_cached()
    return {"success": True, "removed": removed}

@router.post("/chat")
async def chat(request: ChatRequest):
    init_assistant()

    config = get_assistant_config()

    if not config.get("base_url") or not config.get("model"):
        raise HTTPException(status_code=400, detail="请先配置模型地址和模型名称")

    if not request.use_tools:
        if request.stream:
            return await _simple_chat_stream(request.messages, config)
        return await _simple_chat(request.messages, config)

    messages = [{"role": m.role, "content": m.content} for m in request.messages]

    if request.stream:
        return await _agent_chat_stream(messages, config, request.skill_id, request.agent_history)
    else:
        return await _agent_chat(messages, config, request.skill_id, request.agent_history)

def _apply_skill_prompt(skill_id: Optional[str], user_message: str) -> str:
    """指定技能时把技能 prompt 包装到用户消息前（与 /skills/{id}/execute 一致）"""
    if not skill_id:
        return user_message
    try:
        from assistant.skill_engine import SkillEngine
        skill = SkillEngine.get_skill(skill_id)
        if not skill:
            return user_message
        skill_prompt = SkillEngine.get_skill_prompt(skill_id)
        return f"{skill_prompt}\n\n用户请求: {user_message}"
    except Exception as e:
        logger.warning(f"[Assistant] 包装技能提示词失败: {e}")
        return user_message

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

async def _simple_chat_stream(messages: List[ChatMessage], config: Dict):
    """纯对话模式（不走工具）的流式版本，事件类型与 Agent 保持一致"""
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
        "stream": True,
    }

    async def generate():
        final_content = ""
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream("POST", target_url, headers=headers, json=payload) as response:
                    if response.status_code != 200:
                        body = (await response.aread()).decode("utf-8", "ignore")
                        yield f"data: {json.dumps({'type': 'error', 'message': body or f'请求失败 ({response.status_code})'}, ensure_ascii=False)}\n\n"
                        return
                    async for line in response.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if not data:
                            continue
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        choices = chunk.get("choices") or []
                        delta = (choices[0].get("delta") or {}) if choices else {}
                        piece = delta.get("content")
                        if piece:
                            final_content += piece
                            yield f"data: {json.dumps({'type': 'stream', 'content': piece}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'response', 'content': final_content}, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error(f"[Assistant] 纯对话流式异常: {e}", exc_info=True)
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

async def _agent_chat(messages: List[Dict], config: Dict, skill_id: Optional[str] = None, agent_history: Optional[List[Dict]] = None):
    try:
        from assistant.agent import Agent
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

    agent_config = _build_agent_config(config)

    seed = _clean_agent_history(agent_history)
    if seed is None:
        seed = messages[:-1]
    agent = Agent(agent_config, seed)

    user_message = messages[-1].get("content", "") if messages else ""
    user_message = _apply_skill_prompt(skill_id, user_message)

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

async def _agent_chat_stream(messages: List[Dict], config: Dict, skill_id: Optional[str] = None, agent_history: Optional[List[Dict]] = None):
    from assistant.agent import Agent

    agent_config = _build_agent_config(config)

    seed = _clean_agent_history(agent_history)
    if seed is None:
        seed = messages[:-1]
    agent = Agent(agent_config, seed)

    user_message = messages[-1].get("content", "") if messages else ""
    user_message = _apply_skill_prompt(skill_id, user_message)
    
    async def generate():
        try:
            async for event in agent.run_stream(user_message):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error(f"[Assistant] 流式对话异常: {e}", exc_info=True)
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
    for skill in SkillEngine.list_skills(include_disabled=True):
        skills.append(skill.to_dict(include_content=False))
    
    return skills

@router.get("/skills/{skill_id}")
async def get_skill(skill_id: str):
    init_assistant()
    
    from assistant.skill_engine import SkillEngine
    
    skill = SkillEngine.get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="技能不存在")
    
    return skill.to_dict(include_content=True)

@router.put("/skills/{skill_id}/enabled")
async def set_skill_enabled(skill_id: str, request: Request):
    """启用或禁用技能"""
    init_assistant()
    
    from assistant.skill_engine import SkillEngine
    
    body = await request.json()
    enabled = body.get("enabled")
    if enabled is None:
        raise HTTPException(status_code=400, detail="缺少 enabled 参数")
    
    success = SkillEngine.set_skill_enabled(skill_id, bool(enabled))
    if not success:
        raise HTTPException(status_code=404, detail="技能不存在")
    
    return {"success": True, "message": f"技能已{'启用' if enabled else '禁用'}"}

@router.post("/skills/reload")
async def reload_skills():
    """重新加载所有技能（从文件系统）"""
    init_assistant()
    
    from assistant.skill_engine import SkillEngine
    
    SkillEngine.reload()
    
    return {
        "success": True,
        "message": f"已重新加载 {len(SkillEngine.list_skills())} 个技能",
        "count": len(SkillEngine.list_skills())
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
    
    from assistant.agent import Agent

    agent_config = _build_agent_config(config)

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


# ==================== 对话会话存储 ====================

@router.get("/sessions")
async def list_chat_sessions():
    """会话列表（按更新时间倒序）"""
    from assistant import chat_store

    return await chat_store.list_sessions()


@router.get("/sessions/{session_id}")
async def get_chat_session(session_id: str):
    from assistant import chat_store

    data = await chat_store.get_session(session_id)
    if not data:
        raise HTTPException(status_code=404, detail="会话不存在")
    return data


@router.put("/sessions/{session_id}")
async def save_chat_session(session_id: str, request: Request):
    """保存会话（消息由前端维护，服务端只做存取与体积控制）"""
    from assistant import chat_store

    body = await request.json()
    messages = body.get("messages") or []
    if not isinstance(messages, list) or not messages:
        raise HTTPException(status_code=400, detail="messages 不能为空")

    meta = await chat_store.save_session(
        session_id,
        messages,
        title=body.get("title") or "",
        agent_history=body.get("agent_history"),
    )
    return {"success": True, "session": meta}


@router.delete("/sessions/{session_id}")
async def delete_chat_session(session_id: str):
    from assistant import chat_store

    if not await chat_store.delete_session(session_id):
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"success": True, "message": "会话已删除"}
