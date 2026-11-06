# -*- coding: utf-8 -*-
"""TVDB v4 统一数据中心 (L2)。

收拢 TVDB 的 token 登录与数据获取，统一走 MetaCacheManager 缓存与代理。
所有需要 TVDB 数据的地方都应走这里，不再各自裸发 httpx。
"""

import httpx
from typing import Any, Dict, Optional

from config_manager import ConfigManager
from logger import log_audit
from metadata.meta_cache import MetaCacheManager


class TVDBProvider:
    BASE_URL = "https://api4.thetvdb.com/v4"
    # 官方共用 Key（Lens 内置、社区通用），可在系统设置里覆盖
    DEFAULT_API_KEY = "d3158670-26f0-48bb-9267-2f63781dca6b"

    _token: Optional[str] = None  # 进程内 token 缓存

    @staticmethod
    def _api_key() -> str:
        key = (ConfigManager.get_config() or {}).get("tvdb_api_key") or ""
        return key.strip() or TVDBProvider.DEFAULT_API_KEY

    @staticmethod
    def _proxy() -> Optional[str]:
        # TVDB 复用 TMDB 的代理配置（与原 season_split TVDBClient 行为一致）
        try:
            return ConfigManager.get_proxy("tmdb")
        except Exception:
            return None

    @staticmethod
    def _headers(auth: bool = False) -> dict:
        h = {"User-Agent": "AnimeManager-TVDB/1.0", "Accept": "application/json"}
        if auth and TVDBProvider._token:
            h["Authorization"] = f"Bearer {TVDBProvider._token}"
        return h

    @staticmethod
    async def _fetch(method: str, url: str, logs: Any = None, params: dict = None,
                     json: dict = None, auth: bool = True, _retried: bool = False) -> Optional[Any]:
        def _log(msg):
            if hasattr(logs, "log"):
                logs.log(msg)
            elif isinstance(logs, list):
                logs.append(msg)

        proxy = TVDBProvider._proxy()
        path = url.replace(TVDBProvider.BASE_URL, "")
        _log(f"┃ [TVDB] ☁️ {method} {path}")
        log_audit("TVDB", "请求", f"{method} {path} [代理: {proxy}]" if proxy else f"{method} {path} [直连]")

        async with httpx.AsyncClient(timeout=25, proxy=proxy) as client:
            try:
                if method == "GET":
                    resp = await client.get(url, headers=TVDBProvider._headers(auth=auth), params=params)
                else:
                    resp = await client.post(url, headers=TVDBProvider._headers(auth=auth), json=json)
                if resp.status_code == 200:
                    return resp.json()
                if resp.status_code == 401 and auth and TVDBProvider._token and not _retried:
                    _log("┃ [TVDB] 🔑 token 失效，重新登录")
                    TVDBProvider._token = None
                    await TVDBProvider._ensure_token(logs=logs)
                    return await TVDBProvider._fetch(
                        method, url, logs=logs, params=params, json=json, auth=auth, _retried=True,
                    )
                _log(f"┃   ❌ TVDB HTTP {resp.status_code}")
            except Exception as e:
                _log(f"┃   ❌ TVDB Network Error: {e}")
        return None

    @staticmethod
    async def _ensure_token(logs: Any = None) -> str:
        if TVDBProvider._token:
            return TVDBProvider._token
        data = await TVDBProvider._fetch(
            "POST", f"{TVDBProvider.BASE_URL}/login",
            logs=logs, json={"apikey": TVDBProvider._api_key()}, auth=False,
        )
        token = ((data or {}).get("data") or {}).get("token")
        if not token:
            raise ValueError("TVDB 登录响应缺少 token")
        TVDBProvider._token = token
        return token

    @staticmethod
    async def get_series_episodes(tvdb_id: int, logs: Any = None) -> Optional[Dict[str, Any]]:
        """获取 /series/{id}/episodes/official/eng 原始响应（分页拉全，带 7 天缓存）。"""
        cache_key = f"tvdb:series_episodes:v2:{tvdb_id}"
        cached = await MetaCacheManager.get_discover_cache(cache_key)
        if cached is not None:
            if logs:
                _log = logs.log if hasattr(logs, "log") else (lambda m: logs.append(m) if isinstance(logs, list) else None)
                _log(f"┃ [TVDB] ⚡️ 本地缓存命中 (Series ID:{tvdb_id})")
            return cached

        await TVDBProvider._ensure_token(logs=logs)
        episodes: list = []
        series_name = ""
        page = 0
        while page < 10:  # 每页 500 集，正常番剧一页足够
            data = await TVDBProvider._fetch(
                "GET", f"{TVDBProvider.BASE_URL}/series/{tvdb_id}/episodes/official/eng",
                logs=logs, params={"page": str(page)},
            )
            page_data = (data or {}).get("data") or {}
            series_name = page_data.get("name") or series_name
            batch = page_data.get("episodes") or []
            episodes.extend(batch)
            links = page_data.get("links") or {}
            if not batch or not links.get("next"):
                break
            page += 1

        result = {"name": series_name, "episodes": episodes}
        await MetaCacheManager.set_discover_cache(cache_key, result, expire_hours=24 * 7)
        return result
