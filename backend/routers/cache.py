from fastapi import APIRouter, HTTPException, Query
from typing import Optional, Dict, Any, List
from metadata.meta_cache import MetaCacheManager
from logger import log_audit
import regex as re

router = APIRouter(tags=["本地元数据缓存"])


def _is_fingerprint_valid(fingerprint: str) -> bool:
    """
    检查指纹是否足够有效，避免过于简单的指纹导致误匹配。
    (与 local_cache.py 中的逻辑保持一致)
    """
    # 1. 移除所有数字占位符 # 后，检查是否有实质内容
    stripped = fingerprint.replace('#', '')

    # 2. 移除常见的季集模式标记
    season_ep_patterns = [
        r'[Ss]#?',
        r'[Ee][Pp]?#?',
        r'第\s*#?\s*[集话回話]?',
        r'[Vv][Oo][Ll]\.?\s*#?',
    ]
    clean_fingerprint = stripped
    for pattern in season_ep_patterns:
        clean_fingerprint = re.sub(pattern, '', clean_fingerprint, flags=re.IGNORECASE)

    # 3. 移除文件扩展名和括号
    clean_fingerprint = re.sub(r'\.\w{2,4}$', '', clean_fingerprint)
    clean_fingerprint = re.sub(r'[\[\]【】()]', '', clean_fingerprint)
    clean_fingerprint = clean_fingerprint.strip()

    # 4. 移除技术规格词
    tech_words = ['mkv', 'mp4', 'avi', 'ts', 'flv', 'mov', 'webm']
    for word in tech_words:
        clean_fingerprint = clean_fingerprint.replace(word, '')

    # 5. 检查是否有标题内容
    has_title_content = bool(re.search(r'[a-zA-Z\u4e00-\u9fa5\u3040-\u309f\u30a0-\u30ff]{2,}', clean_fingerprint))

    # 6. 检查原始文件名长度（从指纹推断：如果去掉#后很短，说明原文件名也短）
    is_filename_short = len(fingerprint.replace('#', '').strip()) < 10

    return has_title_content and not is_filename_short

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

@router.post("/cleanup_invalid_fingerprints", summary="智能清理无效记忆记录")
async def cleanup_invalid_fingerprints():
    """
    智能清理无效的指纹记录（如只有季集模式、缺乏标题内容的简单指纹）。
    保留有效的记忆记录，避免误匹配。
    """
    try:
        all_fingerprints = await MetaCacheManager.get_all_fingerprints()
        invalid_items = []
        deleted_count = 0

        for fp in all_fingerprints:
            fingerprint_str = fp.get("fingerprint", "")
            if not _is_fingerprint_valid(fingerprint_str):
                invalid_items.append({
                    "fingerprint": fingerprint_str,
                    "tmdb_id": fp.get("tmdb_id"),
                    "title": fp.get("title")
                })
                await MetaCacheManager.delete_fingerprint(fingerprint_str)
                deleted_count += 1

        return {
            "status": "success",
            "message": f"已清理 {deleted_count} 条无效记录，保留 {len(all_fingerprints) - deleted_count} 条有效记录",
            "deleted_count": deleted_count,
            "total_count": len(all_fingerprints),
            "invalid_items": invalid_items[:20]  # 只返回前20条作为示例
        }
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
