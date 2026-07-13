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

            # [Guard] 检查指纹有效性：过于简单的指纹（如 S#E#）会导致不同剧集误匹配
            if not self._is_fingerprint_valid(fingerprint, filename):
                logs.append(f"[智能记忆] ⏭️ 跳过记录: 指纹 '{fingerprint}' 过于简单，缺乏区分度")
                return

            fingerprint_data = {
                "id": tmdb_data['id'],
                "type": tmdb_data['type'],
                "title": tmdb_data.get('title') or tmdb_data.get('name')
            }
            await MetaCacheManager.save_fingerprint(fingerprint, fingerprint_data)
            logs.append(f"[智能记忆] 💾 更新记忆特征: ID:{tmdb_data['id']} | 标题:{fingerprint_data['title']}")
        except Exception as e:
            logs.append(f"[智能记忆] ❌ 更新失败: {e}")

    def _is_fingerprint_valid(self, fingerprint: str, original_filename: str) -> bool:
        """
        检查指纹是否足够有效，避免过于简单的指纹导致误匹配。

        无效指纹示例：
        - S#E#.mkv (只有季集模式)
        - S##E#.mkv
        - 第#话.mkv
        - E#.mkv
        - #.mkv (只有集数)

        有效指纹示例：
        - [LoliHouse] Spy x Family - # [####].mkv (包含标题和制作组)
        - 间谍过家家 S#E#.mkv (包含标题)
        """
        # 1. 移除所有数字占位符 # 后，检查是否有实质内容
        stripped = fingerprint.replace('#', '')

        # 2. 移除常见的季集模式标记（S、E、第、话、集、EP 等）
        # 这些标记本身不能区分不同剧集
        season_ep_patterns = [
            r'[Ss]#?',           # S# 或 S
            r'[Ee][Pp]?#?',      # E#、EP#、E 或 EP
            r'第\s*#?\s*[集话回話]?',  # 第#集、第#话、第集、第话
            r'[Vv][Oo][Ll]\.?\s*#?',  # Vol.#、Vol#
        ]
        clean_fingerprint = stripped
        for pattern in season_ep_patterns:
            clean_fingerprint = re.sub(pattern, '', clean_fingerprint, flags=re.IGNORECASE)

        # 3. 移除文件扩展名和技术规格标记
        clean_fingerprint = re.sub(r'\.\w{2,4}$', '', clean_fingerprint)  # 移除扩展名
        clean_fingerprint = re.sub(r'[\[\]【】()]', '', clean_fingerprint)  # 移除括号
        clean_fingerprint = clean_fingerprint.strip()

        # 4. 移除纯技术规格词（如 mkv、mp4、1080p 等，这些已在第3步处理扩展名）
        tech_words = ['mkv', 'mp4', 'avi', 'ts', 'flv', 'mov', 'webm']
        for word in tech_words:
            clean_fingerprint = clean_fingerprint.replace(word, '')

        # 5. 最终检查：剩余内容是否足够（至少包含标题相关信息）
        # 要求至少有2个连续的非空白字符（可能是标题的一部分）
        has_title_content = bool(re.search(r'[a-zA-Z\u4e00-\u9fa5\u3040-\u309f\u30a0-\u30ff]{2,}', clean_fingerprint))

        # 6. 特殊情况：如果原始文件名很短（<10字符），通常也不值得记录
        is_filename_short = len(original_filename.strip()) < 10

        return has_title_content and not is_filename_short

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
