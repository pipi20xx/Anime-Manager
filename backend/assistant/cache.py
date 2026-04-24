import json
import time
import hashlib
import logging
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from threading import Lock

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    data: Any
    created_at: float
    ttl: int
    hits: int = 0
    
    def is_expired(self) -> bool:
        return time.time() - self.created_at > self.ttl
    
    def touch(self):
        self.hits += 1


class QueryCache:
    """
    查询结果缓存管理器
    
    用于缓存 TMDB/Bangumi 等外部 API 的查询结果，减少重复调用
    """
    _instance = None
    _lock = Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._cache: Dict[str, CacheEntry] = {}
                    cls._instance._stats = {"hits": 0, "misses": 0}
        return cls._instance
    
    def _generate_key(self, prefix: str, *args, **kwargs) -> str:
        key_data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
        key_hash = hashlib.md5(key_data.encode()).hexdigest()[:12]
        return f"{prefix}:{key_hash}"
    
    def get(self, prefix: str, *args, **kwargs) -> Tuple[bool, Any]:
        key = self._generate_key(prefix, *args, **kwargs)
        
        with self._lock:
            entry = self._cache.get(key)
            
            if entry is None:
                self._stats["misses"] += 1
                return False, None
            
            if entry.is_expired():
                del self._cache[key]
                self._stats["misses"] += 1
                return False, None
            
            entry.touch()
            self._stats["hits"] += 1
            logger.debug(f"[Cache] 命中: {key}, 命中次数: {entry.hits}")
            return True, entry.data
    
    def set(self, prefix: str, data: Any, ttl: int = 3600, *args, **kwargs):
        key = self._generate_key(prefix, *args, **kwargs)
        
        with self._lock:
            self._cache[key] = CacheEntry(
                data=data,
                created_at=time.time(),
                ttl=ttl
            )
            logger.debug(f"[Cache] 存储: {key}, TTL: {ttl}s")
    
    def get_or_set(self, prefix: str, fetch_func, ttl: int = 3600, *args, **kwargs) -> Any:
        hit, data = self.get(prefix, *args, **kwargs)
        if hit:
            return data
        
        data = fetch_func(*args, **kwargs)
        self.set(prefix, data, ttl, *args, **kwargs)
        return data
    
    async def get_or_set_async(self, prefix: str, fetch_func, ttl: int = 3600, *args, **kwargs) -> Any:
        hit, data = self.get(prefix, *args, **kwargs)
        if hit:
            return data
        
        data = await fetch_func(*args, **kwargs)
        self.set(prefix, data, ttl, *args, **kwargs)
        return data
    
    def invalidate(self, prefix: str = None):
        with self._lock:
            if prefix:
                keys_to_delete = [k for k in self._cache if k.startswith(prefix)]
                for key in keys_to_delete:
                    del self._cache[key]
                logger.info(f"[Cache] 清除前缀 {prefix} 的缓存，共 {len(keys_to_delete)} 条")
            else:
                self._cache.clear()
                logger.info("[Cache] 清除所有缓存")
    
    def cleanup_expired(self):
        with self._lock:
            expired_keys = [k for k, v in self._cache.items() if v.is_expired()]
            for key in expired_keys:
                del self._cache[key]
            if expired_keys:
                logger.info(f"[Cache] 清理过期缓存 {len(expired_keys)} 条")
    
    def get_stats(self) -> Dict:
        with self._lock:
            total = self._stats["hits"] + self._stats["misses"]
            hit_rate = self._stats["hits"] / total * 100 if total > 0 else 0
            return {
                "total_entries": len(self._cache),
                "hits": self._stats["hits"],
                "misses": self._stats["misses"],
                "hit_rate": f"{hit_rate:.1f}%"
            }


CACHE_TTL = {
    "tmdb_search": 86400,
    "tmdb_detail": 604800,
    "bangumi_search": 86400,
    "bangumi_detail": 604800,
    "bangumi_calendar": 3600,
    "trending": 1800,
    "jackett_search": 300,
}

query_cache = QueryCache()
