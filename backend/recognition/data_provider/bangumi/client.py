import httpx
import asyncio
import datetime
from typing import List, Optional, Dict, Any, Tuple
from config_manager import ConfigManager
from metadata.meta_cache import MetaCacheManager
from recognition_engine.bgm_matcher.logic import BangumiMatcher
from recognition_engine.tmdb_matcher.logic import TMDBMatcher
from ..tmdb.client import TMDBProvider as TMDBClient

class BangumiProvider:
    """
    Bangumi 统一数据中心 (L2)
    收拢识别引擎与路由器共用的 IO 逻辑。
    """
    BASE_URL = "https://api.bgm.tv"

    @staticmethod
    def _get_headers():
        token = ConfigManager.get_config().get("bangumi_token")
        h = {"User-Agent": "ANIME-Pro-Matcher/2.0"}
        if token: h["Authorization"] = f"Bearer {token}"
        return h

    @staticmethod
    async def _fetch(method: str, url: str, logs: Any = None, params: dict = None, json: dict = None) -> Optional[Any]:
        def _log(msg):
            if hasattr(logs, "log"): logs.log(msg)
            elif isinstance(logs, list): logs.append(msg)

        proxy = ConfigManager.get_proxy("bangumi")
        
        # 日志参数拼接
        query_str = f"?{'&'.join([f'{k}={v}' for k, v in params.items()])}" if params else ""
        payload_str = f" | Body: {json}" if json else ""
        _log(f"┃ [BGM] ☁️ {method} {url}{query_str}{payload_str}")
        
        if proxy:
            _log(f"┃ [Proxy] 🛡️ 启用代理加速")

        async with httpx.AsyncClient(timeout=10, proxy=proxy) as client:
            try:
                if method == "GET":
                    resp = await client.get(url, headers=BangumiProvider._get_headers(), params=params)
                else:
                    resp = await client.post(url, headers=BangumiProvider._get_headers(), json=json)
                
                if resp.status_code == 200: return resp.json()
                _log(f"┃   ❌ BGM HTTP {resp.status_code}")
            except Exception as e:
                _log(f"┃   ❌ BGM Network Error: {e}")
        return None

    @staticmethod
    def _proxy_img(url: str) -> str:
        """
        将 Bangumi 图片链接转换为本地代理链接
        """
        if not url: return ""
        # 强制 HTTPS
        if url.startswith("http:"): 
            url = url.replace("http:", "https:")
        
        # 已经是本地代理或相对路径则不处理
        if url.startswith("/"): return url
        
        # 编码 URL 参数
        from urllib.parse import quote
        return f"/api/system/bgm_img?url={quote(url)}"

    @staticmethod
    async def discover(params: Dict[str, Any], logs: Any = None) -> Dict:
        """
        Bangumi 发现/搜索接口 (模拟 Discover)
        Hybrid Mode:
        - 无筛选/纯浏览: 使用 GET /v0/subjects (支持精准 Rank/Date 排序)
        - 有筛选: 使用 POST /v0/search/subjects (支持多维过滤)
        """
        # 0. 尝试读取缓存
        import hashlib
        import json
        
        # 生成缓存键 (过滤掉无关参数如 timestamp)
        cache_params = {k: v for k, v in params.items() if v is not None}
        param_str = json.dumps(cache_params, sort_keys=True)
        param_hash = hashlib.md5(param_str.encode()).hexdigest()
        cache_key = f"bangumi:discover:{param_hash}"
        
        cached = await MetaCacheManager.get_discover_cache(cache_key)
        if cached:
            if logs: 
                msg = f"┃ [BGM] ⚡️ 本地缓存命中 (Discover)"
                if hasattr(logs, "log"): logs.log(msg)
                elif isinstance(logs, list): logs.append(msg)
            return cached

        # 1. 检测是否有“高级筛选” (API v0 subjects 仅支持 type/sort/limit/offset)
        has_complex_filters = False
        complex_keys = ["with_genres", "subtype", "source", "region", "audience", "year", "rank_range", "keyword"]
        for k in complex_keys:
            if params.get(k):
                has_complex_filters = True
                break
        
        page = int(params.get("page", 1))
        limit = 60 
        offset = (page - 1) * limit
        sort_by = params.get("sort_by")

        # === 模式 A: 纯浏览 (GET /v0/subjects) ===
        if not has_complex_filters:
            # 排序映射 (Subject Endpoint)
            # match -> date (Newest)
            # popularity.desc -> rank (Top Rated)
            sort_val = "rank"
            if sort_by == "match": sort_val = "date"
            elif sort_by == "popularity.desc": sort_val = "rank"
            
            browse_params = {
                "type": 2, # Anime
                "sort": sort_val,
                "limit": limit,
                "offset": offset
            }
            
            url = f"{BangumiProvider.BASE_URL}/v0/subjects"
            if logs: print(f"BGM Browse: {url} params={browse_params}")
            
            data = await BangumiProvider._fetch("GET", url, logs=logs, params=browse_params)
            
        # === 模式 B: 高级搜索 (POST /v0/search/subjects) ===
        else:
            # 排序映射 (Search Endpoint)
            # match -> match (Default)
            # popularity.desc -> heat (Trending)
            # rank -> rank (虽然叫rank但在search里表现不同)
            sort_map = {
                "match": "match",
                "popularity.desc": "heat", 
                "vote_average.desc": "score", 
                "rank.asc": "rank"
            }
            sort_val = sort_map.get(sort_by, "match")
            
            filters = {
                "type": [2], 
                "nsfw": True
            }
            
            # 排名范围
            rank_range = params.get("rank_range")
            if rank_range and "-" in rank_range:
                try:
                    start, end = rank_range.split("-")
                    filters["rank"] = [f">={start.strip()}", f"<={end.strip()}"]
                except: pass

            # 标签聚合
            tags = []
            if params.get("with_genres"): tags.append(params.get("with_genres"))
            if params.get("subtype"): tags.append(params.get("subtype"))
            if params.get("source"): tags.append(params.get("source"))
            if params.get("region"): tags.append(params.get("region"))
            if params.get("audience"): tags.append(params.get("audience"))
            if tags: filters["tag"] = tags

            # 年份
            if params.get("year"):
                y = params.get("year")
                if y == "1980s": filters["air_date"] = ["<=1989-12-31"]
                else: filters["air_date"] = [f">={y}-01-01", f"<={y}-12-31"]

            payload = {
                "keyword": params.get("keyword", ""), 
                "sort": sort_val,
                "filter": filters
            }
            
            url = f"{BangumiProvider.BASE_URL}/v0/search/subjects?limit={limit}&offset={offset}"
            if logs: print(f"BGM Search: {url} payload={payload}")
            
            data = await BangumiProvider._fetch("POST", url, logs=logs, json=payload)

        # === 通用结果处理 ===
        results = []
        total = 0
        if data:
            total = data.get("total", 0)
            items = data.get("data", [])
            
            for item in items:
                images = item.get("images") or {}
                raw_poster = images.get("large") or images.get("common") or ""
                poster = BangumiProvider._proxy_img(raw_poster)
                
                # Robust score extraction (Search returns flat 'score', Browse returns 'rating' object)
                score = item.get("score")
                if score is None:
                    score = item.get("rating", {}).get("score")
                
                results.append({
                    "id": item.get("id"),
                    "title": item.get("name_cn") or item.get("name"),
                    "original_title": item.get("name"),
                    "overview": item.get("summary") or "", 
                    "poster_path": poster,
                    "backdrop_path": poster,
                    "vote_average": score or 0,
                    "release_date": item.get("date"),
                    "first_air_date": item.get("date"),
                    "media_type": "tv", 
                    "source": "bangumi"
                })
        
        final_result = {
            "results": results,
            "total_pages": (total + limit - 1) // limit,
            "total_results": total
        }
        
        # 写入缓存 (6小时过期)
        await MetaCacheManager.set_discover_cache(cache_key, final_result, expire_hours=6)
        
        return final_result

    @staticmethod
    async def get_calendar(logs: Any = None) -> Dict:
        """
        获取每日放送表 (带缓存)
        """
        cache_key = "bangumi:calendar"
        cached = await MetaCacheManager.get_discover_cache(cache_key)
        if cached:
            today_idx = datetime.datetime.today().weekday() + 1
            for day in cached.get("data", []):
                day["is_today"] = day.get("weekday", {}).get("id") == today_idx
            return cached

        data = await BangumiProvider._fetch("GET", f"{BangumiProvider.BASE_URL}/calendar", logs=logs)
        if not data: return {"data": []}
        
        today_idx = datetime.datetime.today().weekday() + 1
        result = []
        for day_item in data:
            weekday_obj = day_item.get('weekday', {})
            items = day_item.get('items', [])
            norm_items = []
            for i in items:
                images = i.get('images') or {}
                raw_img = images.get('large') or images.get('common') or images.get('medium') or ''
                img_url = BangumiProvider._proxy_img(raw_img)
                
                norm_items.append({
                    "id": i.get('id'),
                    "title": i.get('name_cn') or i.get('name'),
                    "original_title": i.get('name'),
                    "image": img_url,
                    "rating": i.get('rating', {}).get('score')
                })
            result.append({
                "weekday": weekday_obj,
                "is_today": weekday_obj.get('id') == today_idx,
                "items": norm_items
            })
        
        resp_data = {"status": "success", "data": result}
        await MetaCacheManager.set_discover_cache(cache_key, resp_data, expire_hours=24)
        return resp_data

    @staticmethod
    async def get_subject_details(subject_id: int, logs: Any = None, include_cast: bool = False) -> Optional[Dict]:
        """
        获取条目详细元数据 (带缓存)
        :param include_cast: 是否包含演职员/角色信息 (识别阶段可设为 False 以优化性能)
        """
        def _log(msg):
            if hasattr(logs, "log"): logs.log(msg)
            elif isinstance(logs, list): logs.append(msg)

        cache_key = f"bangumi:detail:{subject_id}"
        cached = await MetaCacheManager.get_discover_cache(cache_key)
        
        # 缓存命中逻辑：如果缓存里已经有 cast 了，或者我们本次不需要 cast，直接返回
        if cached:
            if not include_cast or (include_cast and cached.get("cast")):
                _log(f"┃ [BGM] ⚡️ 本地数据库命中 (ID:{subject_id})")
                return cached

        data = await BangumiProvider._fetch("GET", f"{BangumiProvider.BASE_URL}/v0/subjects/{subject_id}", logs=logs)
        if not data: return None
        
        # 2. 角色 (声优) - 按需抓取
        cast = []
        if include_cast:
            characters = await BangumiProvider._fetch("GET", f"{BangumiProvider.BASE_URL}/v0/subjects/{subject_id}/characters", logs=logs) or []
            for char in characters[:12]:
                actors = char.get("actors", [])
                cast.append({
                    "character": char.get("name"),
                    "actor": actors[0].get("name") if actors else "未知",
                    "image": BangumiProvider._proxy_img(char.get("images", {}).get("grid") or "")
                })

        # 3. 标签与图片处理
        meta_tags = []
        platform = data.get("platform")
        if platform: meta_tags.append(platform)
        infobox = data.get("infobox", [])
        for info in infobox:
            if info.get("key") in ["地区", "产地", "放送星期"]:
                val = info.get("value")
                if isinstance(val, str): meta_tags.append(val)
                elif isinstance(val, list): meta_tags.extend([v.get("v") for v in val if v.get("v")])

        user_tags = [t.get("name") for t in data.get("tags", [])]
        images = data.get("images", {})
        raw_poster = images.get("large") or images.get("common") or ""
        poster = BangumiProvider._proxy_img(raw_poster)
        
        result = {
            "id": data.get("id"),
            "title": data.get("name_cn") or data.get("name"),
            "original_title": data.get("name"),
            "overview": data.get("summary"),
            "poster_path": poster,
            "backdrop_path": poster,
            "vote_average": data.get("rating", {}).get("score", 0),
            "release_date": data.get("date"),
            "total_episodes": data.get("total_episodes") or 0,
            "genres": meta_tags,
            "tags": user_tags,
            "cast": cast,
            "source": "bangumi",
            "platform": platform
        }
        await MetaCacheManager.set_discover_cache(cache_key, result, expire_hours=24 * 7)
        return result

    @staticmethod
    async def search_subject(keyword: str, logs: Any, current_episode: Optional[int] = None, expected_type: str = "tv") -> Optional[dict]:
        """
        用于识别引擎的搜索逻辑 (增强日志版)
        """
        def _log(msg):
            if hasattr(logs, "log"): logs.log(msg)
            elif isinstance(logs, list): logs.append(msg)

        if not keyword: return None
        _log(f"┃ [BGM-Search] 🔍 正在检索 Bangumi 库: '{keyword}'")
        
        data = await BangumiProvider._fetch("POST", f"{BangumiProvider.BASE_URL}/v0/search/subjects", logs=logs, json={"keyword": keyword, "filter": {"type": [2]}})
        if not data: return None
        
        candidates = data.get("data", [])
        if not candidates: 
            _log(f"┃   ❌ 未发现匹配条目")
            return None

        _log(f"┃ [BGM-Filter] ⚖️ 正在核验 {len(candidates[:3])} 个潜在候选人...")
        best_candidate = None
        
        for idx, cand in enumerate(candidates[:3]):
            # 详情请求会有它自己的云端日志
            detail = await BangumiProvider.get_subject_details(cand['id'], logs)
            if not detail: continue

            platform = detail.get('platform', '')
            total_eps = detail.get('total_episodes', 0)
            c_name = detail['title']
            rank = idx + 1
            
            _log(f"┣ [Rank #{rank}] {c_name} (ID:{cand['id']})")
            _log(f"┃   ├─ 类型: {platform} | 总集数: {total_eps}")
            
            # 逻辑 1: 类型冲突核验
            is_movie_type = platform in ["剧场版", "电影版", "Movie"]
            if expected_type == "tv" and (current_episode or 0) > 1:
                if is_movie_type or total_eps == 1:
                    _log(f"┃   └─ ❌ [排除] 模式冲突: 识别模式为 TV，但该条目为单集电影/OVA")
                    continue
            
            # 逻辑 2: 集数范围核验
            if total_eps > 0 and current_episode and current_episode > (total_eps + 5):
                if idx == 0 or len(candidates) == 1:
                    _log(f"┃   └─ ⚠️ [警告] 集数存疑: 提取到 E{current_episode} 但条目仅 {total_eps} 集，作为首选仍尝试采信")
                else: 
                    _log(f"┃   └─ ❌ [排除] 集数超限: 文件集数(E{current_episode}) 远超条目总量({total_eps})")
                    continue

            # 成功锁定第一个符合要求的
            if not best_candidate:
                _log(f"┃   └─ ✅ [胜出] 该条目相关度最高且通过规格核验")
                best_candidate = detail
            else:
                _log(f"┃   └─ ⏩ [略过] 已有相关度更高的优选条目")

        if best_candidate:
            _log(f"┗ 🎯 最终锁定 Bangumi 目标: {best_candidate['title']}")
            return best_candidate
        
        _log(f"┗ ❌ 遗憾：本次搜索发现的 {len(candidates[:3])} 个候选人均未通过规格核验")
        return None

    @staticmethod
    async def map_to_tmdb(bgm_item: Dict, tmdb_api_key: str, logs: Any) -> Optional[Dict]:
        """
        Bangumi 条目对撞 TMDB (整合 L1 算法)
        """
        def _log(msg):
            if hasattr(logs, "log"): logs.log(msg)
            elif isinstance(logs, list): logs.append(msg)

        bgm_platform = bgm_item.get('platform', '')
        name_cn = bgm_item.get('title', '')
        
        primary_strategy = 'tv' 
        if bgm_platform in ['Movie', '剧场版'] or '剧场版' in name_cn:
            primary_strategy = 'movie'

        _log(f"┃ [BGM-Link] 🔗 正在尝试将 Bangumi 条目映射至 TMDB ({primary_strategy} 模式)")
        strategies = BangumiMatcher.generate_search_strategies(bgm_item)
        search_phases = [('tv', 'tv'), ('movie', 'movie')] if primary_strategy == 'tv' else [('movie', 'movie'), ('tv', 'tv')]

        scored_pool = []
        seen_ids = set()
        tmdb = TMDBClient(tmdb_api_key)

        for endpoint, scoring_strategy in search_phases:
            if any(x["score"] >= 85 for x in scored_pool): break
            
            for query, year, lang_hint in strategies:
                tmdb_lang = "ja-JP" if lang_hint == "ja" else "zh-CN"
                q_label = "日文原名" if lang_hint == "ja" else "中文标题"
                
                results, _ = await tmdb.search(query, year, endpoint, logs=logs, lang=tmdb_lang)
                _log(f"┃   ├─ 🔍 [{q_label}] '{query}' -> 发现 {len(results)} 个候选人")
                
                for cand in results:
                    m_id = cand.get('id')
                    if m_id in seen_ids: continue
                    seen_ids.add(m_id)
                    
                    cand['media_type'] = endpoint
                    score, trace, reason = BangumiMatcher.score_candidate(cand, bgm_item, query, scoring_strategy, query_label=q_label)
                    scored_pool.append({"item": cand, "score": score, "query": query, "reason": reason, "trace": trace, "win_lang": q_label})
        
        if not scored_pool:
            _log(f"┃ ❌ TMDB 所有搜索维度均未发现任何候选结果")
            return None

        scored_pool.sort(key=lambda x: x["score"], reverse=True)
        # 即使匹配失败，也展示前 5 个候选人，方便用户从日志判断搜到了什么
        for idx, entry in enumerate(scored_pool[:5]):
            item = entry["item"]
            c_name = item.get('title') or item.get('name')
            c_year = (item.get('release_date') or item.get('first_air_date') or '')[:4]
            _log(f"┣ [TMDB#{idx+1}] ID:{item['id']} | {c_name} ({c_year})")
            for t_line in entry["trace"]:
                _log(t_line)
            _log(f"┃   ├─ 最终分: {entry['score']:.1f} | 依据: {entry['win_lang']}")
            _log(f"┃   └─ 构成: {entry['reason']}")

        best = scored_pool[0]
        threshold = 70
        if best["score"] >= threshold:
            _log(f"┗ ✅ 建立映射: [BGM ID:{bgm_item['id']}] -> [TMDB ID:{best['item']['id']}] ({best['item'].get('title') or best['item'].get('name')})")
            # [Fix] 强制重新获取一次详情，以确保拿到的是中文标题而非搜索阶段的日文标题
            details = await tmdb.get_details(str(best["item"]["id"]), best["item"]['media_type'], logs=logs)
            if details:
                return details
            return TMDBMatcher.normalize(best["item"], media_type_hint=best["item"]['media_type'])
        
        _log(f"┃ ⚠️ BGM 映射最高分不足 ({best['score']:.1f} < {threshold})，执行回退策略...")
        return None