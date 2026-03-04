import regex as re
from typing import List, Optional, Dict, Any
from metadata.meta_cache import MetaCacheManager
from logger import log_audit
from recognition_engine.constants import MediaType

class LocalCacheDAO:
    """
    Data Access Object for Local Metadata Cache and Series Fingerprints.
    Unified to use PostgreSQL Super Table.
    """
    
    async def get_fingerprint_match(self, filename: str, logs: List[str]) -> Optional[Dict[str, Any]]:
        """
        根据文件名指纹查找系列匹配。
        """
        fingerprint = re.sub(r'\d+', '#', filename)
        fp_info = await MetaCacheManager.get_fingerprint(fingerprint)
        
        if fp_info:
            fp_info['id'] = fp_info.get('tmdb_id')
            logs.append(f"[智能记忆] ⚡ 命中加速: {fp_info.get('title')} (ID: {fp_info.get('tmdb_id')})")
            return fp_info
        return None

    async def save_fingerprint(self, filename: str, tmdb_data: Dict[str, Any], logs: List[str]):
        """
        保存指纹。
        """
        try:
            fingerprint = re.sub(r'\d+', '#', filename)
            fingerprint_data = {
                "id": tmdb_data['id'],
                "type": tmdb_data['type'],
                "title": tmdb_data.get('title') or tmdb_data.get('name')
            }
            await MetaCacheManager.save_fingerprint(fingerprint, fingerprint_data)
            logs.append(f"[智能记忆] 💾 更新记忆特征: ID:{tmdb_data['id']} | 标题:{fingerprint_data['title']}")
        except Exception as e:
            logs.append(f"[智能记忆] ❌ 更新失败: {e}")

    async def get_metadata(self, tmdb_id: str, media_type: str, logs: List[str]) -> Optional[Dict[str, Any]]:
        """
        [Unified] 从数据中心获取完整元数据。
        """
        key = f"{media_type}:{tmdb_id}"
        cached = await MetaCacheManager.get(key)
        
        if cached:
            prefix = "[数据中心] 🛡️ 命中固定存档" if cached.get("is_custom") else "[数据中心] ⚡ 命中离线索引"
            logs.append(f"{prefix}: {cached.get('title')} (ID: {tmdb_id})")
            cached["source"] = "archive_hit"
            return cached
        return None

    async def save_metadata(self, tmdb_id: str, media_type: str, data: Dict[str, Any], logs: List[str]):
        """
        [Unified] 保存/更新元数据到数据中心。
        """
        key = f"{media_type}:{tmdb_id}"
        await MetaCacheManager.update(key, data)
        if data.get("manual") or data.get("is_custom"):
            logs.append(f"[数据中心] 🛡️ 发现已有锁定记录 (ID: {tmdb_id})，正在覆盖数据...")
        else:
            logs.append(f"[数据中心] 💾 同步最新档案 (ID: {key})")
