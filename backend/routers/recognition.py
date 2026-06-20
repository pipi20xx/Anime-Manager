from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Tuple, Dict, Any
from recognition.recognizer import MovieRecognizer
from recognition.ai_helper import AIHelper
from config_manager import ConfigManager
from logger import log_audit
from task_history import start_task, log_task, finish_task
import uuid

router = APIRouter(tags=["媒体识别"], prefix="")

class AiTestRequest(BaseModel):
    filename: str
    custom_regex: Optional[str] = None
    group_index: Optional[int] = 1

class RecognizeRequest(BaseModel):
    filename: str
    force_filename: bool = False
    forced_tmdb_id: Optional[str] = None
    forced_type: Optional[str] = None
    forced_season: Optional[str] = None
    forced_episode: Optional[str] = None
    # 策略覆盖
    anime_priority: Optional[bool] = None
    offline_priority: Optional[bool] = None
    bangumi_priority: Optional[bool] = None
    bangumi_failover: Optional[bool] = None
    series_fingerprint: Optional[bool] = None # 智能指纹覆盖
    batch_enhancement: Optional[bool] = None # 合集增强覆盖
    description: Optional[str] = None # 副标题描述 (PT站副标题/RSS description)
    # 临时调试规则 (Debug Sandbox)
    temp_noise: Optional[List[str]] = None
    temp_groups: Optional[List[str]] = None
    temp_render: Optional[List[str]] = None
    temp_privilege: Optional[List[str]] = None

@router.post("/api/recognize", summary="全链路识别接口")
async def recognize(req: RecognizeRequest):
    """
    执行全链路识别流程：
    1. 指纹判定
    2. 内核解析 (L1)
    3. 数据对撞 (L2)
    4. 字段补全与本地覆盖
    5. 规则渲染
    """
    display_name = req.filename if req.force_filename else req.filename.split('/')[-1]
    
    log_audit("识别", "识别标题", display_name)
    
    task_id = f"recog_{uuid.uuid4().hex[:12]}"
    try:
        await start_task(task_id, "识别", display_name)
    except Exception:
        task_id = None

    config = ConfigManager.get_config()
    
    anime_priority = req.anime_priority if req.anime_priority is not None else config.get("anime_priority", True)
    offline_priority = req.offline_priority if req.offline_priority is not None else config.get("offline_priority", True)
    bangumi_priority = req.bangumi_priority if req.bangumi_priority is not None else config.get("bangumi_priority", False)
    bangumi_failover = req.bangumi_failover if req.bangumi_failover is not None else config.get("bangumi_failover", True)

    try:
        result_data, logs = await MovieRecognizer.recognize_full(
            req.filename, 
            all_noise=req.temp_noise, 
            all_groups=req.temp_groups, 
            api_key=None, 
            anime_priority=anime_priority,
            offline_priority=offline_priority,
            bangumi_priority=bangumi_priority,
            bangumi_failover=bangumi_failover,
            series_fingerprint=req.series_fingerprint,
            batch_enhancement=req.batch_enhancement,
            all_render=req.temp_render,
            all_privilege=req.temp_privilege,
            force_filename=req.force_filename,
            forced_tmdb_id=req.forced_tmdb_id,
            forced_type=req.forced_type,
            forced_season=req.forced_season,
            forced_episode=req.forced_episode,
            description=req.description
        )

        if task_id:
            for log_msg in logs:
                level = "ERROR" if "❌" in log_msg or "[ERROR]" in log_msg else "WARN" if "⚠️" in log_msg else "INFO"
                await log_task(task_id, log_msg, level)

        final = result_data.get("final_result", {})
        success = result_data.get("success", False)
        
        stats = {}
        if final.get("title"):
            stats["title"] = final["title"]
        if final.get("tmdb_id"):
            stats["tmdb_id"] = final["tmdb_id"]
        if final.get("category"):
            stats["category"] = final["category"]
        if final.get("season"):
            stats["season"] = final["season"]
        if final.get("episode"):
            stats["episode"] = final["episode"]

        status = "completed" if success else "error"
        if task_id:
            try:
                await finish_task(task_id, status, stats=stats if stats else None)
            except Exception:
                pass
        
        if success:
            log_audit("识别", "识别完成", f"{final.get('title', display_name)} (ID: {final.get('tmdb_id', '-')}) S{final.get('season', '?')}E{final.get('episode', '?')}")

        return result_data
    except Exception as e:
        if task_id:
            try:
                await log_task(task_id, f"❌ 识别异常: {str(e)}", "ERROR")
                await finish_task(task_id, "error")
            except Exception:
                pass
        raise

@router.get("/api/tmdb/search", summary="TMDB 关键词搜索", operation_id="tmdb_search_recognition")
async def search_tmdb_endpoint(query: str, type: str = "tv", year: str = None):
    """
    直接调用 TMDB API 搜索作品，用于强制手动识别时的关键词匹配。
    """
    config = ConfigManager.get_config()
    api_key = config.get("tmdb_api_key")
    if not api_key:
        raise HTTPException(status_code=400, detail="未配置 TMDB API Key")
    
    proxy = ConfigManager.get_proxy("tmdb")
    proxy_info = f" [代理: {proxy}]" if proxy else " [直连]"
    log_audit("TMDB", "搜索", f"关键词: {query} (类型: {type}){proxy_info}")
        
    logs = []        
    import httpx
    base_url = "https://api.themoviedb.org/3"
    search_type = "movie" if type == "movie" else "tv"
    params = {"api_key": api_key, "query": query, "language": "zh-CN", "include_adult": "false"}
    if year: params["year" if search_type == "movie" else "first_air_date_year"] = year
    
    async with httpx.AsyncClient(proxy=proxy, timeout=10) as client:
        try:
            resp = await client.get(f"{base_url}/search/{search_type}", params=params)
            data = resp.json()
            results = data.get("results", [])
            formatted = []
            for item in results:
                formatted.append({
                    "id": item.get("id"),
                    "title": item.get("title") or item.get("name"),
                    "original_title": item.get("original_title") or item.get("original_name"),
                    "year": (item.get("release_date") or item.get("first_air_date") or "")[:4],
                    "overview": item.get("overview"),
                    "poster_path": item.get('poster_path')
                })
            return {"results": formatted}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/tmdb/tv/{tmdb_id}", summary="获取剧集季度详情")
async def get_tmdb_tv_details(tmdb_id: str):
    """
    根据 TMDB ID 获取指定剧集的季度信息，包括每季的集数和播出日期。主要用于追剧订阅时的自动填充。
    """
    config = ConfigManager.get_config()
    api_key = config.get("tmdb_api_key")
    if not api_key:
        raise HTTPException(status_code=400, detail="未配置 TMDB API Key")
    
    proxy = ConfigManager.get_proxy("tmdb")
    
    import httpx
    base_url = "https://api.themoviedb.org/3"
    params = {"api_key": api_key, "language": "zh-CN"}
    
    async with httpx.AsyncClient(proxy=proxy, timeout=10) as client:
        try:
            resp = await client.get(f"{base_url}/tv/{tmdb_id}", params=params)
            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail="TMDB 详情获取失败")
            data = resp.json()
            return {
                "id": data.get("id"),
                "name": data.get("name"),
                "seasons": [
                    {
                        "season_number": s.get("season_number"),
                        "episode_count": s.get("episode_count"),
                        "name": s.get("name"),
                        "air_date": s.get("air_date")
                    } for s in data.get("seasons", []) if s.get("season_number") > 0
                ]
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/ai/test", summary="AI 实验室：语义解析测试")
async def test_ai_parsing(request: AiTestRequest):
    """
    仅测试 AI 模型对文件名的理解能力，不涉及 TMDB 数据库对撞。
    """
    filename = request.filename
    if not filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")
    
    log_audit("AI", "实验室测试", f"开始 AI 语义解析测试: {filename}")
    
    ai = AIHelper()
    if not ai.is_available():
        log_audit("AI", "测试失败", "AI 引擎未就绪", level="ERROR")
        return {"status": "error", "message": "AI 引擎不可用 (请检查日志/模型)"}
        
    try:
        result = ai.parse_filename(filename)
        if not result:
            return {"status": "error", "message": "AI 解析未返回有效数据 (可能是配置错误或模型无响应)"}
            
        log_audit("AI", "测试成功", f"解析结论: {result.get('title')} S{result.get('season','-')}E{result.get('episode','-')}")
        return {"status": "success", "result": result}
    except Exception as e:
        log_audit("AI", "测试崩溃", str(e), level="ERROR")
        return {"status": "error", "message": str(e)}

@router.post("/api/privilege/test", summary="特权集数锁定测试")
async def test_privilege_lock(request: AiTestRequest):
    """
    针对特定字幕组（如 LoliHouse）的特权规则提取测试。
    支持传入自定义正则进行调试。
    """
    from recognition_engine.special_episode_handler import SpecialEpisodeHandler
    import regex as re
    
    filename = request.filename
    if not filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")
    
    # 1. 如果有自定义正则，优先走自定义路径
    if request.custom_regex:
        try:
            match = re.search(request.custom_regex, filename, re.IGNORECASE)
            if match:
                val_str = match.group(request.group_index or 1)
                return {
                    "hit": True,
                    "episode": int(val_str),
                    "logs": [f"[Custom] 匹配成功: {match.group(0)} -> E{val_str}"],
                    "match_detail": {
                        "full": match.group(0),
                        "groups": match.groups()
                    }
                }
            return {"hit": False, "logs": ["自定义正则未命中"], "episode": None}
        except Exception as e:
            return {"hit": False, "logs": [f"正则语法错误: {str(e)}"], "episode": None, "error": True}

    # 2. 否则走系统内置规则
    spec_group, spec_title, spec_ep, spec_raw, spec_logs, _ = SpecialEpisodeHandler.extract(filename)
    return {
        "hit": spec_ep is not None,
        "episode": spec_ep,
        "logs": spec_logs
    }

@router.get("/api/privilege/rules", summary="获取内置特权规则列表")
async def get_privilege_rules():
    """
    返回系统当前硬编码在 SpecialEpisodeHandler 中的特权正则规则。
    """
    from recognition_engine.special_episode_handler import SpecialEpisodeHandler
    rules = []
    for pattern, group_idx, desc in SpecialEpisodeHandler.RULES:
        rules.append({
            "pattern": pattern,
            "group_index": group_idx,
            "description": desc
        })
    return rules