import os
import json
import httpx
import logging
from typing import List, Dict, Optional
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from config_manager import ConfigManager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/assistant", tags=["Assistant"])

SKILLS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "skills")

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    stream: bool = False

class ConfigUpdate(BaseModel):
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None

def get_assistant_config() -> Dict:
    config = ConfigManager.get_config()
    return config.get("assistant_config", {
        "base_url": "",
        "api_key": "",
        "model": "",
        "provider": "ollama",
        "temperature": 0.7,
        "max_tokens": 64
    })

def save_assistant_config(new_config: Dict):
    current_config = ConfigManager.get_config()
    if "assistant_config" not in current_config:
        current_config["assistant_config"] = {}
    current_config["assistant_config"].update(new_config)
    ConfigManager.update_config({"assistant_config": current_config["assistant_config"]})

async def call_llm(messages: List[Dict[str, str]], stream: bool = False):
    config = get_assistant_config()
    
    base_url = config.get("base_url", "").strip().strip('`').strip()
    api_key = config.get("api_key", "").strip()
    model = config.get("model", "").strip()
    provider = config.get("provider", "ollama")
    
    if not base_url or not model:
        raise HTTPException(status_code=400, detail="请先配置模型地址和模型名称")
    
    target_url = f"{base_url.rstrip('/')}/chat/completions"
    if "v1" not in base_url and "chat/completions" not in base_url:
        target_url = f"{base_url.rstrip('/')}/v1/chat/completions"
    
    logger.info(f"[Assistant] 请求模型: {target_url}, model: {model}")
    
    headers = {
        "Content-Type": "application/json"
    }
    
    if provider == "openai" and api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    
    payload = {
        "model": model,
        "messages": messages,
        "temperature": config.get("temperature", 0.7),
        "max_tokens": config.get("max_tokens", 64) * 1000,
    }
    
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            if stream:
                async def generate():
                    try:
                        async with client.stream("POST", target_url, headers=headers, json=payload) as response:
                            if response.status_code != 200:
                                error_text = await response.aread()
                                yield f"data: {json.dumps({'error': error_text.decode()})}\n\n"
                                return
                            async for chunk in response.aiter_text():
                                yield chunk
                    except httpx.ConnectError:
                        yield f"data: {json.dumps({'error': '无法连接到模型服务，请检查 Base URL 是否正确'})}\n\n"
                    except httpx.TimeoutException:
                        yield f"data: {json.dumps({'error': '请求超时，请稍后重试'})}\n\n"
                return StreamingResponse(generate(), media_type="text/event-stream")
            else:
                response = await client.post(target_url, headers=headers, json=payload)
                if response.status_code != 200:
                    logger.error(f"[Assistant] 模型返回错误: {response.status_code} - {response.text}")
                    raise HTTPException(status_code=response.status_code, detail=response.text)
                result = response.json()
                logger.info(f"[Assistant] 模型返回: {json.dumps(result, ensure_ascii=False)[:500]}")
                return result
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="无法连接到模型服务，请检查 Base URL 是否正确")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="请求超时，请稍后重试")

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
    messages = [{"role": m.role, "content": m.content} for m in request.messages]
    
    system_prompt = """你是番剧管家的智能助手，帮助用户管理动漫资源。

你可以帮助用户：
1. 分析识别失败的资源并提供解决方案
2. 推荐订阅新番剧
3. 解答关于番剧管家功能的问题
4. 协助配置和优化系统

请用中文回复，保持简洁友好。"""
    
    full_messages = [{"role": "system", "content": system_prompt}] + messages
    
    if request.stream:
        return await call_llm(full_messages, stream=True)
    else:
        result = await call_llm(full_messages, stream=False)
        return result

@router.get("/skills")
async def list_skills():
    skills = []
    if not os.path.exists(SKILLS_DIR):
        return skills
    
    for skill_name in os.listdir(SKILLS_DIR):
        skill_path = os.path.join(SKILLS_DIR, skill_name)
        if os.path.isdir(skill_path):
            skill_md = os.path.join(skill_path, "SKILL.md")
            if os.path.exists(skill_md):
                try:
                    with open(skill_md, "r", encoding="utf-8") as f:
                        content = f.read()
                        name = skill_name
                        description = ""
                        for line in content.split("\n"):
                            if line.startswith("name:"):
                                name = line.split(":", 1)[1].strip()
                            elif line.startswith("description:"):
                                description = line.split(":", 1)[1].strip()
                                break
                        skills.append({
                            "id": skill_name,
                            "name": name,
                            "description": description,
                            "path": skill_path
                        })
                except Exception as e:
                    logger.warning(f"读取技能 {skill_name} 失败: {e}")
    
    return skills

@router.get("/skills/{skill_id}")
async def get_skill(skill_id: str):
    skill_path = os.path.join(SKILLS_DIR, skill_id)
    if not os.path.exists(skill_path):
        raise HTTPException(status_code=404, detail="技能不存在")
    
    skill_md = os.path.join(skill_path, "SKILL.md")
    if os.path.exists(skill_md):
        with open(skill_md, "r", encoding="utf-8") as f:
            return {"content": f.read(), "path": skill_path}
    
    raise HTTPException(status_code=404, detail="技能文档不存在")

@router.post("/skills/{skill_id}/execute")
async def execute_skill(skill_id: str, request: Request):
    skill_path = os.path.join(SKILLS_DIR, skill_id)
    if not os.path.exists(skill_path):
        raise HTTPException(status_code=404, detail="技能不存在")
    
    body = await request.json()
    params = body.get("params", {})
    
    return {"message": f"技能 {skill_id} 执行请求已接收", "params": params}
