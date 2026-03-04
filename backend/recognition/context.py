import time
import logging
from typing import List, Dict, Any, Optional
from recognition_engine.data_models import MetaBase
from recognition_engine.constants import MediaType
from config_manager import ConfigManager
from metadata.meta_cache import MetaCacheManager
from .data_provider.bangumi.client import BangumiProvider as BangumiClient
from .data_provider.tmdb.client import TMDBProvider as TMDBClient
from .data_provider.local_cache import LocalCacheDAO
from .data_provider.offline import OfflineDAO

logger = logging.getLogger("Recognition")

class RecognitionContext:
    """
    RecognitionContext encapsulated all configurations, logs, and intermediate states
    for a single recognition task. This is the "Heart" of Layer 3 (Orchestrator).
    """
    def __init__(self, filename: str, **kwargs):
        self.filename = filename
        self.start_time = time.time()
        self.kwargs = kwargs
        
        # Initial states
        self.logs: List[str] = []
        self.perf_stats: List[str] = []
        self.meta: Optional[MetaBase] = None
        self.tmdb_data: Optional[Dict[str, Any]] = None
        
        # Configuration Snapshot
        self.config = ConfigManager.get_config()
        cached_rules = ConfigManager.get_cached_rules()
        
        self.api_key = kwargs.get("api_key") or self.config.get("tmdb_api_key")
        
        # Helper to handle kwargs override with fallback to config
        def get_pref(key, config_key, default_val):
            val = kwargs.get(key)
            if val is None:
                return self.config.get(config_key, default_val)
            return val

        self.anime_priority = get_pref("anime_priority", "anime_priority", True)
        self.offline_priority = get_pref("offline_priority", "offline_priority", True)
        self.bangumi_priority = get_pref("bangumi_priority", "bangumi_priority", False)
        self.bangumi_failover = get_pref("bangumi_failover", "bangumi_failover", True)
        self.batch_enhance = get_pref("batch_enhancement", "batch_enhancement", False)
        self.use_fingerprint = get_pref("series_fingerprint", "series_fingerprint", True)
        
        # Initialize Providers
        self.tmdb_client = TMDBClient(self.api_key)
        self.bangumi_client = BangumiClient()
        
        # [Term Update] 兼容旧代码 (cache_dao/offline_dao) 与新架构 (local_store/full_db)
        self.local_store = self.cache_dao = LocalCacheDAO() 
        self.full_db = self.offline_dao = OfflineDAO() 
        
        # Rules
        local_noise = self.config.get("custom_noise_words", [])
        remote_noise = [f"[REMOTE]{r}" for r in cached_rules.get("noise", [])]
        self.all_noise = kwargs.get("all_noise") or (local_noise + remote_noise)

        local_groups = self.config.get("custom_release_groups", [])
        remote_groups = [f"[REMOTE]{r}" for r in cached_rules.get("groups", [])]
        self.all_groups = kwargs.get("all_groups") or (local_groups + remote_groups)

        local_render = self.config.get("custom_render_words", [])
        remote_render = [f"[REMOTE]{r}" for r in cached_rules.get("render", [])]
        self.all_render = kwargs.get("all_render") or (local_render + remote_render)

    def log(self, message: str, level: str = "INFO"):
        self.logs.append(message)
        # Also output to global system log for real-time console
        lvl = getattr(logging, level.upper(), logging.INFO)
        # [Upgrade] 使用 stacklevel=2 穿透包装，显示真实的调用文件名 (如 parser.py)
        logger.log(lvl, message, stacklevel=2)

    def add_perf(self, stage: str, start_ts: float):
        duration_ms = int((time.time() - start_ts) * 1000)
        self.perf_stats.append(f"{stage}: {duration_ms}ms")

    @property
    def duration(self) -> float:
        return time.time() - self.start_time

    def get_final_json(self) -> Dict[str, Any]:
        """
        Final cleanup and JSON structure generation.
        """
        # This will be used by the new RenderService
        pass
