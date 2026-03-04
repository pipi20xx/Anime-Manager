from typing import Optional, Dict, Any, List
from tmdbmatefull.manager import TmdbMateFullManager
from metadata.meta_cache import MetaCacheManager

class OfflineDAO:
    """
    Data Access Object for the Offline Full Metadata Database (TmdbMateFull).
    """

    @staticmethod
    async def resolve(cn_name: Optional[str], en_name: Optional[str], year: Optional[str], media_type: Optional[str], anime_priority: bool, logs: Any) -> Optional[Dict[str, Any]]:
        """
        Resolve recognition using the offline database with dual-title support.
        """
        def _log(msg):
            if hasattr(logs, "log"): logs.log(msg)
            elif isinstance(logs, list): logs.append(msg)

        # 尝试优先级：中文名 -> 英文名
        queries = [q for q in [cn_name, en_name] if q]
        if not queries: return None

        _log(f"┃ [数据中心] 🔍 正在检索离线索引...")
        
        for q in queries:
            match = await TmdbMateFullManager.resolve_recognition(
                title=q,
                year=year,
                media_type=media_type,
                anime_priority=anime_priority
            )
            if match:
                _log(f"┣ 🎯 [数据中心] 命中索引: {match['title']} (ID: {match['id']})")
                match["source"] = "offline_hit"
                return match
        
        _log(f"┣ ⏩ [数据中心] 未能通过标题索引直接定位目标")
        return None

    @staticmethod
    async def get_deep_meta(tmdb_id: str, media_type: str) -> Optional[Any]:
        """
        [Unified] 调取深度档案。
        不再区分数据中心还是缓存，统一从 MetaCacheManager 获取合并后的字典。
        """
        key = f"{media_type}:{tmdb_id}"
        return await MetaCacheManager.get(key)

    @staticmethod
    async def fetch_and_ingest(tmdb_id: str, media_type: str, logs: List[str]):
        """
        从 TMDB 获取全量数据并补全离线索引。
        """
        logs.append(f"[数据中心] 💉 正在离线化存储档案...")
        await TmdbMateFullManager.fetch_and_ingest(tmdb_id, media_type)

    @staticmethod
    async def calculate_secondary_category(tmdb_id: str, media_type: str) -> str:
        """
        计算作品的二级分类 (例如: 动画, 纪录片)。
        """
        return await TmdbMateFullManager.calculate_secondary_categories(
            tmdb_id, 
            media_type, 
            await TmdbMateFullManager.load_secondary_rules()
        )

    @staticmethod
    def convert_to_cache_payload(deep_obj: Any, secondary_category: Optional[str] = None) -> Dict[str, Any]:
        """
        [Obsolete] 此适配器已废弃，直接使用 MetaCacheManager.get 返回的标准字典即可。
        """
        if isinstance(deep_obj, dict): return deep_obj
        return {}
