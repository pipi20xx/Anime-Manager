import httpx
import asyncio
import re
from typing import List, Optional, Dict, Any, Tuple
from config_manager import ConfigManager
from metadata.meta_cache import MetaCacheManager
from recognition_engine.tmdb_matcher.logic import TMDBMatcher

class TMDBProvider:
    """
    TMDB 统一数据中心 (L2)
    """
    BASE_URL = "https://api.themoviedb.org/3"

    def __init__(self, api_key: str = None):
        config_key = ConfigManager.get_config().get("tmdb_api_key")
        self.api_key = api_key or config_key
        self.proxy = ConfigManager.get_proxy("tmdb")

    async def _fetch(self, endpoint: str, params: dict = {}, logs: Any = None) -> Optional[Dict]:
        if not self.api_key: return None
        
        def _log(msg):
            if hasattr(logs, "log"): logs.log(msg)
            elif isinstance(logs, list): logs.append(msg)

        params["api_key"] = self.api_key
        params["language"] = params.get("language", "zh-CN")
        
        full_url = f"{TMDBProvider.BASE_URL}{endpoint}"
        # 脱敏日志 URL
        log_params = {k: ("****" if k == "api_key" else v) for k, v in params.items()}
        query_str = "&".join([f"{k}={v}" for k, v in log_params.items()])
        _log(f"┃ [TMDB] ☁️ GET {full_url}?{query_str}")
        
        if self.proxy:
            _log(f"┃ [Proxy] 🛡️ 启用代理加速")

        async with httpx.AsyncClient(timeout=10, proxy=self.proxy) as client:
            try:
                resp = await client.get(full_url, params=params)
                if resp.status_code == 200: return resp.json()
                
                # 记录详细错误信息
                error_msg = f"┃   ❌ TMDB HTTP {resp.status_code}"
                try:
                    err_json = resp.json()
                    if "status_message" in err_json:
                        error_msg += f" - {err_json['status_message']}"
                except: pass
                
                _log(error_msg)
                return None
            except Exception as e: 
                _log(f"┃   ❌ TMDB Network Error: {e} (Proxy: {self.proxy or 'None'})")
                return None

    @staticmethod
    def _proxy_img(path: Optional[str]) -> Optional[str]:
        if not path: return None
        # 如果已经是代理路径（无论是 img 还是 bgm_img），或者已经是完整 URL，保持原样
        if "/api/system/" in path or path.startswith("http"): return path
        from urllib.parse import quote
        return f"/api/system/img?path={quote(path)}"

    async def discover(self, media_type: str, params: Dict[str, Any], logs: Any = None) -> Dict:
        """
        通用发现接口 (支持自定义过滤)
        聚合模式：一次请求并行拉取 3 页 TMDB 数据 (60条)，提高浏览密度。
        """
        # 前端请求的页码
        page = int(params.get("page", 1))
        
        # 聚合因子: 1个前端页 = 3个 TMDB 页 (20 * 3 = 60 items)
        AGGREGATION_FACTOR = 3
        
        # 生成缓存 Key (基于参数哈希 + 聚合因子)
        # 注意：这里必须把原始 page 放入 key，否则翻页会失效
        params_copy = params.copy()
        params_copy["page"] = page
        params_copy["aggregation"] = AGGREGATION_FACTOR
        
        param_key = sorted([(k, str(v)) for k, v in params_copy.items()])
        cache_key = f"tmdb:discover:{media_type}:{hash(tuple(param_key))}"
        
        cached = await MetaCacheManager.get_discover_cache(cache_key)
        if cached: return cached

        # 计算实际需要请求的 TMDB 页码范围
        start_tmdb_page = (page - 1) * AGGREGATION_FACTOR + 1
        
        tasks = []
        for i in range(AGGREGATION_FACTOR):
            # 构造每一页的查询参数
            p = params.copy()
            p["page"] = start_tmdb_page + i
            tasks.append(self._fetch(f"/discover/{media_type}", p, logs=logs))
            
        # 并行请求
        responses = await asyncio.gather(*tasks)
        
        # 合并结果
        all_results = []
        max_tmdb_pages = 0
        total_results = 0
        
        for data in responses:
            if not data: continue
            
            # 归一化并添加到总列表
            for i in data.get("results", []):
                norm = TMDBMatcher.normalize(i, media_type_hint=media_type)
                norm["poster_path"] = self._proxy_img(norm["poster_path"])
                norm["backdrop_path"] = self._proxy_img(norm["backdrop_path"])
                all_results.append(norm)
            
            # 更新统计信息 (取最大的那个响应的 total_pages)
            max_tmdb_pages = max(max_tmdb_pages, data.get("total_pages", 0))
            total_results = max(total_results, data.get("total_results", 0))
            
        # 重新计算前端的总页数
        import math
        frontend_total_pages = math.ceil(max_tmdb_pages / AGGREGATION_FACTOR)
        
        resp_data = {
            "results": all_results, 
            "total_pages": frontend_total_pages,
            "total_results": total_results
        }
        await MetaCacheManager.set_discover_cache(cache_key, resp_data, expire_hours=6)
        return resp_data

    async def get_trending(self) -> Dict:
        # 静态方法改为实例方法调用
        cache_key = "tmdb:trending:v4"
        cached = await MetaCacheManager.get_discover_cache(cache_key)
        if cached: return cached

        m_task = self._fetch("/discover/movie", {"with_genres": "16", "with_original_language": "ja", "sort_by": "popularity.desc", "vote_count.gte": 20})
        t_task = self._fetch("/discover/tv", {"with_genres": "16", "with_original_language": "ja", "sort_by": "popularity.desc"})
        
        m_data, t_data = await asyncio.gather(m_task, t_task)
        
        results = []
        movies = (m_data or {}).get("results", [])
        tvs = (t_data or {}).get("results", [])
        
        for i in range(max(len(movies), len(tvs))):
            if i < len(movies): 
                norm = TMDBMatcher.normalize(movies[i], "movie")
                norm["poster_path"] = self._proxy_img(norm["poster_path"])
                norm["backdrop_path"] = self._proxy_img(norm["backdrop_path"])
                results.append(norm)
            if i < len(tvs): 
                norm = TMDBMatcher.normalize(tvs[i], "tv")
                norm["poster_path"] = self._proxy_img(norm["poster_path"])
                norm["backdrop_path"] = self._proxy_img(norm["backdrop_path"])
                results.append(norm)
            
        resp_data = {"results": results[:20]}
        await MetaCacheManager.set_discover_cache(cache_key, resp_data, expire_hours=12)
        return resp_data

    async def get_popular(self, media_type: str) -> Dict:
        cache_key = f"tmdb:popular:v3:{media_type}"
        cached = await MetaCacheManager.get_discover_cache(cache_key)
        if cached: return cached
        
        data = await self._fetch(f"/discover/{media_type}", {"with_genres": "16", "with_original_language": "ja", "sort_by": "popularity.desc"})
        results = []
        for i in (data or {}).get("results", []):
            norm = TMDBMatcher.normalize(i, media_type_hint=media_type)
            norm["poster_path"] = self._proxy_img(norm["poster_path"])
            norm["backdrop_path"] = self._proxy_img(norm["backdrop_path"])
            results.append(norm)
        
        resp_data = {"results": results}
        await MetaCacheManager.set_discover_cache(cache_key, resp_data, expire_hours=24)
        return resp_data

    async def get_subject_details(self, tmdb_id: str, media_type: str, logs: Any = None) -> Optional[Dict]:
        cache_key = f"tmdb:detail:v3:{media_type}:{tmdb_id}"
        cached = await MetaCacheManager.get_discover_cache(cache_key)
        if cached: return cached

        data = await self._fetch(f"/{media_type}/{tmdb_id}", {"append_to_response": "credits"}, logs=logs)
        if not data: return None
        
        cast_list = []
        for c in data.get("credits", {}).get("cast", [])[:15]:
            cast_list.append({
                "character": c.get("character"),
                "actor": c.get("name"),
                "image": self._proxy_img(c.get("profile_path"))
            })
        
        norm = TMDBMatcher.normalize(data, media_type_hint=media_type)
        norm["poster_path"] = self._proxy_img(norm["poster_path"])
        norm["backdrop_path"] = self._proxy_img(norm["backdrop_path"])
        norm["genres"] = [g.get("name") for g in data.get("genres", [])]
        norm["tagline"] = data.get("tagline")
        norm["cast"] = cast_list
        
        await MetaCacheManager.set_discover_cache(cache_key, norm, expire_hours=24 * 7)
        return norm

    async def get_details(self, tmdb_id: str, media_type: str, logs: Any = None) -> Optional[Dict]:
        # 兼容识别引擎的 get_details 命名
        return await self.get_subject_details(tmdb_id, media_type, logs=logs)

    async def get_season_episodes(self, tmdb_id: str, season_number: int, logs: Any = None) -> List[Dict]:
        """
        获取指定季度的所有剧集及其放送日期
        """
        endpoint = f"/tv/{tmdb_id}/season/{season_number}"
        data = await self._fetch(endpoint, logs=logs)
        if not data or "episodes" not in data:
            return []
        
        results = []
        for ep in data["episodes"]:
            results.append({
                "episode": ep.get("episode_number"),
                "air_date": ep.get("air_date"), # YYYY-MM-DD
                "name": ep.get("name")
            })
        return results

    async def search(self, query: str, year: Optional[str], media_type: str, logs: Any = None, lang: str = "zh-CN") -> List[Dict]:
        # 生成缓存 Key
        cache_key = f"tmdb:search:{media_type}:{lang}:{query}:{year or ''}"
        cached = await MetaCacheManager.get_discover_cache(cache_key)
        if cached: return cached

        params = {"query": query, "include_adult": "false", "language": lang}
        if year: params["year" if media_type == "movie" else "first_air_date_year"] = year
        data = await self._fetch(f"/search/{media_type}", params, logs=logs)
        results = (data or {}).get("results", [])
        if not results and year:
            params.pop("year" if media_type == "movie" else "first_air_date_year")
            data_retry = await self._fetch(f"/search/{media_type}", params, logs=logs)
            if data_retry: results = data_retry.get("results", [])
            
        await MetaCacheManager.set_discover_cache(cache_key, results, expire_hours=6)
        return results

    async def smart_search(self, cn_name: Optional[str], en_name: Optional[str], year: Optional[str], media_type: str, logs: Any, anime_priority: bool = True, original_cn_name: Optional[str] = None) -> Optional[Dict]:
        def _log(msg):
            if hasattr(logs, "log"): logs.log(msg)
            elif isinstance(logs, list): logs.append(msg)

        cn_queries = TMDBMatcher.prepare_queries(cn_name)
        en_queries = TMDBMatcher.prepare_queries(en_name)
        orig_queries = TMDBMatcher.prepare_queries(original_cn_name) if original_cn_name and original_cn_name != cn_name else []

        _log(f"┃ [TMDB-Smart] 🚀 启动定向搜索策略...")
        
        merged_candidates = []
        seen_ids = set()

        all_query_groups = []
        # [Strategy] 优先使用原始抓取的中文标题（可能是繁体）进行搜索
        if orig_queries: all_query_groups.append({"queries": orig_queries, "lang": "zh-CN", "label": "原始中文"})
        if cn_queries: all_query_groups.append({"queries": cn_queries, "lang": "zh-CN", "label": "简体中文"})
        if en_queries: all_query_groups.append({"queries": en_queries, "lang": "en-US", "label": "英文"})

        for group in all_query_groups:
            lang = group["lang"]
            for idx, q in enumerate(group["queries"]):
                # [Optimization] 如果已经有候选人，先进行一轮对撞，如果分数极高则熔断
                if len(merged_candidates) > 0:
                    targets = self._build_match_targets(cn_name, en_name, cn_queries, original_cn_name=original_cn_name)
                    temp_scored = []
                    for c_idx, item in enumerate(merged_candidates[:5]):
                        score, _, _, _ = TMDBMatcher.calculate_match_score(item, targets, cn_name or "", en_name or "", c_idx, anime_priority)
                        temp_scored.append(score)
                    
                    if temp_scored and max(temp_scored) >= 95:
                        _log(f"┃   ℹ️ 已命中高置信度候选 ({max(temp_scored):.0f}分)，跳过后续查询")
                        break

                res_list = await self.search(q, year, media_type, logs=logs, lang=lang)
                
                # 全名唯一命中保护：如果第一次搜索（通常是全名）只返回一个结果，直接确认为目标
                if idx == 0 and len(res_list) == 1:
                    _log(f"┃   🪄 全名搜索唯一命中，确认为高置信度目标")
                    for item in res_list:
                        if item.get("id") not in seen_ids:
                            seen_ids.add(item.get("id"))
                            merged_candidates.append(item)
                    return await self._process_candidates(merged_candidates, seen_ids, cn_name, en_name, cn_queries, media_type, logs, anime_priority, original_cn_name=original_cn_name)

                for item in res_list:
                    if item.get("id") not in seen_ids:
                        seen_ids.add(item.get("id"))
                        merged_candidates.append(item)

        return await self._process_candidates(merged_candidates, seen_ids, cn_name, en_name, cn_queries, media_type, logs, anime_priority, original_cn_name=original_cn_name)

    async def _process_candidates(self, merged_candidates, seen_ids, cn_name, en_name, cn_queries, media_type, logs, anime_priority, original_cn_name=None):
        def _log(msg):
            if hasattr(logs, "log"): logs.log(msg)
            elif isinstance(logs, list): logs.append(msg)

        if not merged_candidates:
            _log(f"┃ ❌ TMDB 定向搜索均无结果")
            return None
        
        _log(f"┃ [TMDB-Match] ⚖️ 正在对合并后的 {len(merged_candidates[:10])} 个候选进行交叉对撞...")
        
        targets = self._build_match_targets(cn_name, en_name, cn_queries, original_cn_name=original_cn_name)
        scored_pool = []
        for idx, item in enumerate(merged_candidates[:10]):
            score, trace, best_match_info, summary = TMDBMatcher.calculate_match_score(
                item, targets, cn_name or "", en_name or "", idx, anime_priority
            )
            c_name = item.get("title") or item.get("name")
            c_year = (item.get("release_date") or item.get("first_air_date") or "")[:4]
            
            _log(f"┣ [#{idx+1}] ID:{item.get('id')} | {c_name} ({c_year})")
            for t_line in trace: _log(t_line)
            _log(f"┃   ├─ 最佳匹配: {best_match_info}")
            _log(f"┃   └─ {summary}")
            
            scored_pool.append({"item": item, "score": score})
        
        scored_pool.sort(key=lambda x: x["score"], reverse=True)
        best = scored_pool[0]
        
        _log(f"┃")
        if best["score"] >= 85 or len(seen_ids) == 1:
             if len(seen_ids) == 1 and best["score"] < 85:
                 _log(f"┃ 🪄 触发[孤独命中]策略 (唯一 ID)")
             
             final_name = best["item"].get("title") or best["item"].get("name")
             _log(f"┗ ✅ 最终采信: {final_name} (ID: {best['item']['id']})")
             
             # 尝试获取详情，如果失败则回退到基础搜索结果
             details = await self.get_details(str(best["item"]["id"]), media_type, logs=logs)
             if details:
                 details["_score"] = best["score"]
                 return details
             else:
                 # [Fallback] 如果网络错误导致拿不到详情，不要直接放弃！
                 # 归一化搜索结果中的条目，作为兜底元数据返回
                 _log(f"┃   ⚠️ 详情获取失败(网络波动)，已启用元数据自动补全兜底")
                 fallback_norm = TMDBMatcher.normalize(best["item"], media_type_hint=media_type)
                 fallback_norm["_score"] = best["score"]
                 return fallback_norm
        
        _log(f"┗ ❌ 置信度不足 ({best['score']:.1f} < 85)")
        return None

    def _build_match_targets(self, cn_name, en_name, cn_queries, original_cn_name=None):
        targets = []
        if cn_name: targets.append(re.sub(r"[^\w]", "", cn_name).upper())
        if original_cn_name and original_cn_name != cn_name:
            targets.append(re.sub(r"[^\w]", "", original_cn_name).upper())
        if en_name: targets.append(re.sub(r"[^\w]", "", en_name).upper())
        if cn_queries and len(cn_queries) > 1: targets.append(re.sub(r"[^\w]", "", cn_queries[1]).upper())
        return targets
