from fastapi import APIRouter, HTTPException, Query
from typing import Optional, Dict, Any
import httpx
import asyncio
from metadata.meta_cache import MetaCacheManager
from recognition.data_provider.tmdb import TMDBClient
from recognition_engine.tmdb_matcher.logic import TMDBMatcher
from logger import log_audit

router = APIRouter(tags=["本地元数据缓存"])

@router.get("", summary="获取缓存列表")
async def list_cache(page: int = 1, size: int = 24, q: Optional[str] = None):
    """
    分页获取本地已保存的 TMDB 元数据快照，支持模糊搜索标题。
    """
    return await MetaCacheManager.get_paginated(page, size, q or "")

@router.post("", summary="更新/手动添加缓存")
async def update_cache(item: Dict[str, Any]):
    """
    手动向数据库插入或更新一条元数据记录。
    """
    m_id = item.get("id") or item.get("tmdb_id")
    m_type = item.get("type") or "tv"
    if not m_id: raise HTTPException(400, "缺少 'id' 字段")
    
    key = f"{m_type}:{m_id}"
    await MetaCacheManager.update(key, item)
    return {"status": "success", "message": f"已缓存 {key}"}

@router.delete("/{m_type}/{tmdb_id}", summary="删除特定缓存")
async def delete_cache(m_type: str, tmdb_id: str):
    """
    通过 类型和 ID 从数据库中删除指定的元数据记录。
    """
    key = f"{m_type}:{tmdb_id}"
    await MetaCacheManager.delete(key)
    return {"status": "success", "message": f"已删除 {key}"}

@router.post("/clear", summary="清空全部元数据缓存")
async def clear_all_cache():
    """
    危险操作：彻底清空 meta_cache_v2 表中的所有内容。
    """
    await MetaCacheManager.clear_all()
    return {"status": "success", "message": "所有缓存已清空"}

@router.post("/clear_fingerprints", summary="清空智能记忆库")
async def clear_fingerprints():
    """
    清空智能记忆库，会导致下次识别时重新进行云端搜索。
    """
    try:
        count = await MetaCacheManager.clear_fingerprints()
        return {"status": "success", "message": f"已清空 {count} 条记忆记录"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/clear_blacklist", summary="清空下载黑名单")
async def clear_blacklist():
    """
    清空下载黑名单，允许之前判定为死锁的资源重新被尝试下载。
    """
    try:
        count = await MetaCacheManager.clear_blacklist()
        return {"status": "success", "message": f"已清空 {count} 条黑名单记录"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def _do_sytmdb_sync(addr: str, token: str):
    """后台执行 SYTMDB 同步"""
    if addr and not addr.startswith("http"):
        url = f"http://{addr}:8121/api/items/override/metadata"
    else:
        url = f"{addr}/api/items/override/metadata"
    
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


@router.post("/sytmdb_sync", summary="从 SYTMDB 同步元数据")
async def sync_sytmdb(payload: Dict[str, Any]):
    """
    从 SYTMDB (另一款元数据服务) 拉取并同步手动修正过的元数据快照。
    任务在后台执行，请通过实时日志查看进度。
    """
    addr = payload.get("address") or payload.get("ip")
    token = payload.get("token") or ""
    
    if not addr:
        log_audit("SYTMDB", "同步失败", "未提供地址", level="ERROR")
        raise HTTPException(status_code=400, detail="需要提供地址 (IP:Port)")
    
    log_audit("SYTMDB", "开始同步", f"目标地址: {addr}", level="START")
    
    asyncio.create_task(_do_sytmdb_sync(addr, token))
            
    return {
        "status": "started", 
        "message": "同步任务已在后台启动，请查看实时日志了解进度"
    }
