from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional
import httpx
import asyncio
from metadata.meta_cache import MetaCacheManager
from recognition_engine.tmdb_matcher.logic import TMDBMatcher
from logger import log_audit
from config_manager import ConfigManager

router = APIRouter(prefix="/sytmdb", tags=["SYTMDB 同步"])

def _build_url(addr: str) -> str:
    addr = addr.rstrip("/")
    if addr and not addr.startswith("http"):
        return f"http://{addr}:8121/api/items/override/metadata"
    return f"{addr}/api/items/override/metadata"

def _build_episode_group_url(addr: str, series_id: str) -> str:
    addr = addr.rstrip("/")
    if addr and not addr.startswith("http"):
        return f"http://{addr}:8121/api/tv/{series_id}/episodegroup"
    return f"{addr}/api/tv/{series_id}/episodegroup"

def _get_sytmdb_config() -> tuple[str, str]:
    config = ConfigManager.get_config()
    return config.get("sytmdb_host", ""), config.get("sytmdb_token", "")

async def _do_sytmdb_sync(addr: str, token: str):
    """后台执行 SYTMDB 同步"""
    url = _build_url(addr)
    
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
        log_audit("SYTMDB", "认证", "已配置 API Token", level="INFO")
    else:
        log_audit("SYTMDB", "认证", "未配置 Token，使用匿名访问", level="WARN")
    
    async with httpx.AsyncClient() as client:
        try:
            log_audit("SYTMDB", "请求", f"正在获取: {url}", level="INFO")
            resp = await client.get(url, headers=headers, timeout=30)
            resp.raise_for_status()
            items = resp.json()
            log_audit("SYTMDB", "响应", f"获取到 {len(items)} 条元数据", level="INFO")
        except httpx.HTTPStatusError as e:
            err_msg = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
            log_audit("SYTMDB", "请求失败", err_msg, level="ERROR")
            return
        except Exception as e:
            log_audit("SYTMDB", "请求失败", str(e), level="ERROR")
            return
    
    from asyncio import Semaphore, gather
    sem = Semaphore(20)
    
    success_count = 0
    fail_count = 0
    
    async def process_item(item):
        nonlocal success_count, fail_count
        async with sem:
            try:
                normalized = TMDBMatcher.normalize(item)
                
                if not normalized.get("id") or not normalized.get("title") or normalized.get("type") == "unknown":
                    fail_count += 1
                    return False
                    
                normalized["is_custom"] = True
                
                key = f"{normalized['type']}:{normalized['id']}"
                await MetaCacheManager.update(key, normalized)
                success_count += 1
                return True
            except Exception as e:
                fail_count += 1
                return False

    tasks = [process_item(item) for item in items]
    await gather(*tasks)
    
    log_audit("SYTMDB", "同步完成", f"成功: {success_count} 条, 跳过/失败: {fail_count} 条", level="SUCCESS")


@router.post("/sync", summary="从 SYTMDB 同步元数据")
async def sync_sytmdb(payload: Dict[str, Any] = None):
    """
    从 SYTMDB (另一款元数据服务) 拉取并同步手动修正过的元数据快照。
    任务在后台执行，请通过实时日志查看进度。
    
    如果前端未提供地址和 Token，则从系统配置中读取。
    """
    config = ConfigManager.get_config()
    
    if payload is None:
        payload = {}
    
    addr = payload.get("address") or payload.get("ip") or config.get("sytmdb_host", "")
    token = payload.get("token") or config.get("sytmdb_token", "")
    
    if not addr:
        log_audit("SYTMDB", "同步失败", "未提供地址", level="ERROR")
        raise HTTPException(status_code=400, detail="需要提供地址 (IP:Port) 或在系统设置中配置 SYTMDB Host")
    
    url = _build_url(addr)
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            items = resp.json()
        except httpx.HTTPStatusError as e:
            err_msg = f"HTTP {e.response.status_code}"
            log_audit("SYTMDB", "连接失败", err_msg, level="ERROR")
            raise HTTPException(status_code=400, detail=f"SYTMDB 服务返回错误: {err_msg}")
        except httpx.ConnectError:
            log_audit("SYTMDB", "连接失败", f"无法连接到 {url}", level="ERROR")
            raise HTTPException(status_code=400, detail=f"无法连接到 SYTMDB 服务，请检查地址是否正确")
        except httpx.TimeoutException:
            log_audit("SYTMDB", "连接超时", f"连接 {url} 超时", level="ERROR")
            raise HTTPException(status_code=400, detail="连接 SYTMDB 服务超时，请检查网络或服务是否正常运行")
        except Exception as e:
            log_audit("SYTMDB", "连接失败", str(e), level="ERROR")
            raise HTTPException(status_code=400, detail=f"连接 SYTMDB 服务失败: {str(e)}")
    
    log_audit("SYTMDB", "开始同步", f"目标地址: {addr}，共 {len(items)} 条元数据", level="START")
    
    asyncio.create_task(_do_sytmdb_sync(addr, token))
            
    return {
        "status": "started", 
        "message": f"同步任务已在后台启动，共 {len(items)} 条元数据待同步，请查看实时日志了解进度"
    }


@router.get("/episodegroup/{series_id}", summary="获取剧集组信息")
async def get_episode_group(series_id: str):
    """
    从 SYTMDB 获取指定剧集的剧集组信息。
    剧集组用于将 TMDB 的单季拆分为多季显示。
    
    返回格式:
    {
        "id": "216272",
        "description": "",
        "groups": [
            {
                "name": "第 1 季",
                "order": 1,
                "episodes": [
                    {"episode_number": 1, "season_number": 1, "order": 0},
                    ...
                ]
            }
        ]
    }
    """
    addr, token = _get_sytmdb_config()
    
    if not addr:
        log_audit("SYTMDB", "剧集组", f"TMDB ID {series_id}: 未配置SYTMDB地址，跳过剧集组查询")
        return {"id": series_id, "description": "", "groups": []}
    
    url = _build_episode_group_url(addr, series_id)
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            groups_count = len(data.get("groups", []))
            if groups_count > 0:
                log_audit("SYTMDB", "剧集组", f"TMDB ID {series_id}: 查询成功，共 {groups_count} 个剧集组")
            else:
                log_audit("SYTMDB", "剧集组", f"TMDB ID {series_id}: 查询成功，无剧集组定义")
            return data
        except httpx.ConnectError:
            log_audit("SYTMDB", "剧集组", f"TMDB ID {series_id}: 无法连接到SYTMDB服务", level="WARNING")
            return {"id": series_id, "description": "", "groups": []}
        except httpx.TimeoutException:
            log_audit("SYTMDB", "剧集组", f"TMDB ID {series_id}: 连接SYTMDB超时", level="WARNING")
            return {"id": series_id, "description": "", "groups": []}
        except Exception as e:
            log_audit("SYTMDB", "剧集组", f"TMDB ID {series_id}: 查询失败 - {str(e)[:50]}", level="WARNING")
            return {"id": series_id, "description": "", "groups": []}
