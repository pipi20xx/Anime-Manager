from fastapi import APIRouter, HTTPException, Query
from typing import Optional, Dict, Any
from metadata.meta_cache import MetaCacheManager
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
