# -*- coding: utf-8 -*-
"""番剧分季拆分 · 参照源与 TMDB 适配层。

- `TMDBAdapter`  把项目现有 `TMDBProvider` 的输出适配成 Lens 算法期望的原始形状
- `TVDBClient`   TVDB v4（官方共用 Key，可在设置里覆盖）
- `BangumiSeasonChain`  Bangumi 续集链 → 分季定义（移植 Lens `media_clients.py`）
- `load_cure_source`    CureTMDb 规则表（URL 或本地文件）
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Callable, Optional

import httpx

from .constants import (
    ANIME_GENRE_ID,
    DEFAULT_BANGUMI_BASE,
    DEFAULT_TVDB_BASE,
    DEFAULT_TVDB_KEY,
)
from .models import SeasonEntry, SeriesEntry

TIMEOUT = 25
UA = "AnimeManager-SeasonSplit/1.0"


def _log_noop(level: str, message: str) -> None:
    print(f"[{level}] {message}")


def _proxy_for(service: str = "tmdb") -> Optional[str]:
    """按服务名取代理（复用项目 ConfigManager 的 proxy_services 配置）。"""
    try:
        from config_manager import ConfigManager
        return ConfigManager.get_proxy(service)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# TMDB 适配层
# ---------------------------------------------------------------------------

class TMDBAdapter:
    """把 `TMDBProvider` 的归一化输出还原成 Lens 算法要的原始形状。

    - `tv_detail`   → {seasons:[{season_number, episode_count, air_date}], genres:[{id}], external_ids, ...}
    - `season_detail` → {season_number, episodes:[{episode_number, air_date, name, episode_type, ...}]}
    """

    def __init__(self, api_key: Optional[str] = None, log: Callable = None):
        from recognition.data_provider.tmdb.client import TMDBProvider

        self._client = TMDBProvider(api_key)
        self.log = log or _log_noop

    async def tv_detail(self, tmdb_id: int) -> Optional[dict]:
        data = await self._client.get_subject_details(str(tmdb_id), "tv")
        if not data:
            return None
        out = dict(data)

        # genres: 归一化层会把它换成中文名列表，这里还原成 [{"id": 16}] 供算法判定
        raw_genres = data.get("genres")
        genre_ids: list = []
        if isinstance(raw_genres, list):
            for g in raw_genres:
                if isinstance(g, dict) and g.get("id") is not None:
                    genre_ids.append(int(g["id"]))
                elif isinstance(g, str) and g in ("动画", "Animation", "anime"):
                    genre_ids.append(ANIME_GENRE_ID)
        if not genre_ids and data.get("genre_ids"):
            genre_ids = [int(x) for x in data["genre_ids"] if str(x).isdigit()]
        out["genres"] = [{"id": gid} for gid in genre_ids]

        seasons = [s for s in (data.get("seasons") or []) if isinstance(s, dict)]
        out["seasons"] = seasons
        if not out.get("number_of_seasons"):
            out["number_of_seasons"] = len([s for s in seasons if (s.get("season_number") or 0) > 0])
        out["name"] = data.get("name") or data.get("title") or ""
        out["original_name"] = data.get("original_name") or out["name"]
        return out

    async def season_detail(self, tmdb_id: int, season: int) -> Optional[dict]:
        data = await self._client.get_season_episodes(str(tmdb_id), int(season))
        if not data or not data.get("episodes"):
            return None
        episodes = []
        for ep in data["episodes"]:
            number = ep.get("episode") if ep.get("episode") is not None else ep.get("episode_number")
            episodes.append({
                "episode_number": int(number) if number is not None else 0,
                "season_number": int(season),
                "air_date": ep.get("air_date") or "",
                "name": ep.get("name") or "",
                "overview": ep.get("overview") or "",
                "still_path": ep.get("still_path") or "",
                "vote_average": ep.get("vote_average") or 0,
                "vote_count": ep.get("vote_count") or 0,
                "runtime": ep.get("runtime"),
                "episode_type": ep.get("episode_type") or "",
                "id": int(season) * 100000 + int(number or 0),
            })
        info = data.get("season_info") or {}
        return {
            "season_number": int(season),
            "name": info.get("name") or f"第 {season} 季",
            "air_date": info.get("air_date") or "",
            "poster_path": info.get("poster_path") or "",
            "episodes": episodes,
        }

    async def movie_detail(self, movie_id: int) -> Optional[dict]:
        data = await self._client.get_subject_details(str(movie_id), "movie")
        if not data:
            return None
        return {
            "air_date": data.get("release_date") or data.get("air_date") or "",
            "still_path": data.get("poster_path") or "",
        }


# ---------------------------------------------------------------------------
# TVDB v4
# ---------------------------------------------------------------------------

class TVDBClient:
    def __init__(self, api_key: str = "", base: str = "", log: Callable = None,
                 proxy: Optional[str] = None):
        self.api_key = (api_key or "").strip() or DEFAULT_TVDB_KEY
        self.base = (base or DEFAULT_TVDB_BASE).rstrip("/")
        self.log = log or _log_noop
        self.proxy = proxy if proxy is not None else _proxy_for("tmdb")
        self._token: str = ""

    async def _login(self, client: httpx.AsyncClient) -> None:
        resp = await client.post(f"{self.base}/login", json={"apikey": self.api_key})
        resp.raise_for_status()
        token = (resp.json().get("data") or {}).get("token")
        if not token:
            raise ValueError("TVDB 登录响应缺少 token")
        self._token = token
        self.log("INFO", "TVDB token 获取成功")

    async def get_series_entry(self, tvdb_id: int) -> Optional[SeriesEntry]:
        if not tvdb_id or tvdb_id <= 0:
            return None
        async with httpx.AsyncClient(timeout=TIMEOUT, proxy=self.proxy,
                                     headers={"User-Agent": UA}) as client:
            if not self._token:
                await self._login(client)
            headers = {"Authorization": f"Bearer {self._token}"}
            episodes: list = []
            series_name = ""
            page = 0
            while page < 10:  # TVDB 每页 500 集，正常番剧一页足够
                resp = await client.get(
                    f"{self.base}/series/{tvdb_id}/episodes/official/eng",
                    params={"page": str(page)},
                    headers=headers,
                )
                resp.raise_for_status()
                data = (resp.json() or {}).get("data") or {}
                series_name = data.get("name") or series_name
                batch = data.get("episodes") or []
                episodes.extend(batch)
                links = data.get("links") or {}
                if not batch or not links.get("next"):
                    break
                page += 1

            if not episodes:
                self.log("INFO", f"TVDB {tvdb_id} 未返回剧集数据")
                return None

            counts: dict = {}
            for ep in episodes:
                season_number = int(ep.get("seasonNumber") or 0)
                number = int(ep.get("number") or 0)
                if season_number <= 0 or number <= 0:
                    continue
                counts[season_number] = counts.get(season_number, 0) + 1
            if not counts:
                self.log("WARN", f"TVDB {tvdb_id} 返回 {len(episodes)} 集但没有可用季信息")
                return None

            seasons = [SeasonEntry(season_number=n, episode_count=c) for n, c in sorted(counts.items())]
            for s in seasons:
                self.log("INFO", f"TVDB {series_name} 季 {s.season_number}，集数: {s.episode_count}")
            return SeriesEntry(name=series_name, seasons=seasons)


# ---------------------------------------------------------------------------
# Bangumi 续集链
# ---------------------------------------------------------------------------

def strip_punctuations_spaces(text: str) -> str:
    """等价 Go 的 [\\p{P}\\p{S}\\s}] 清洗：去掉标点、符号与空白。"""
    out = []
    for ch in text or "":
        if ch.isspace():
            continue
        cat = unicodedata.category(ch)
        if cat.startswith("P") or cat.startswith("S"):
            continue
        out.append(ch)
    return "".join(out)


_RE_CHINESE_SEASON = re.compile(r"[第\s]*([一二三四五六七八九十壹贰叁肆伍陆柒捌玖拾0-9]+)\s*(?:季|期)")
_RE_ROMAN_SEASON = re.compile(r"(?i)(?:Season|S)\s*([IVXLCDM]+)")
_RE_ENGLISH_SEASON = re.compile(r"(?:Season|S)\s*([0-9]+)")
_RE_ORDINAL_SEASON = re.compile(r"([0-9]{1,2})(?:st|nd|rd|th)\s+season")
_RE_FULL_CHINESE = re.compile(r"^[零一二三四五六七八九十壹贰叁肆伍陆柒捌玖拾]+$")
_RE_FULL_ROMAN = re.compile(r"^[IVXLCDM]+$")

_CN_DIGITS = {"零": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6,
              "七": 7, "八": 8, "九": 9, "壹": 1, "贰": 2, "叁": 3, "肆": 4,
              "伍": 5, "陆": 6, "柒": 7, "捌": 8, "玖": 9}
_CN_UNITS = {"十": 10, "拾": 10}
_ROMAN_VALUES = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}


def number_converter(s: str) -> int:
    """把数字字符串（阿拉伯/中文/罗马）转换为整数，失败返回 0。"""
    try:
        return int(s)
    except (TypeError, ValueError):
        pass

    if s and _RE_FULL_CHINESE.match(s):
        result, temp = 0, 0
        for r in s:
            if r in _CN_DIGITS:
                temp = _CN_DIGITS[r]
            elif r in _CN_UNITS:
                if temp == 0:
                    temp = 1
                result += temp * _CN_UNITS[r]
                temp = 0
            else:
                return 0
        result += temp
        return result

    if s:
        s_upper = s.upper()
        if _RE_FULL_ROMAN.match(s_upper):
            total, prev = 0, 0
            for ch in reversed(s_upper):
                curr = _ROMAN_VALUES[ch]
                if curr < prev:
                    total -= curr
                else:
                    total += curr
                prev = curr
            if total != 0:
                return total
    return 0


def extract_season_number(name_cn: str, name: str) -> int:
    """从 Bangumi 标题提取季号；正则顺序与 Lens/Go 一致：中文 → 罗马 → 英文 → 序数词。"""
    patterns = (_RE_CHINESE_SEASON, _RE_ROMAN_SEASON, _RE_ENGLISH_SEASON, _RE_ORDINAL_SEASON)

    def parse(text: str) -> int:
        if not text:
            return 0
        for pat in patterns:
            m = pat.search(text)
            if m:
                num = number_converter(m.group(1))
                if num != 0:
                    return num
                return 1
        return 0

    num = parse(name_cn)
    if num != 0:
        return num
    num = parse(name)
    if num != 0:
        return num
    return 1


class BangumiSeasonChain:
    """Bangumi 续集链 → 分季定义（移植 Lens `BangumiClient` 的 season_info 部分）。"""

    def __init__(self, base: str = "", log: Callable = None, proxy: Optional[str] = None):
        self.base = (base or DEFAULT_BANGUMI_BASE).rstrip("/")
        self.log = log or _log_noop
        self.proxy = proxy if proxy is not None else _proxy_for("bangumi")

    # -- 底层 ---------------------------------------------------------------

    def _headers(self) -> dict:
        headers = {"User-Agent": UA}
        try:
            from config_manager import ConfigManager
            token = (ConfigManager.get_config() or {}).get("bangumi_token") or ""
            if token:
                headers["Authorization"] = f"Bearer {token}"
        except Exception:
            pass
        return headers

    async def _get(self, client: httpx.AsyncClient, path: str, params: dict = None):
        resp = await client.get(f"{self.base}{path}", params=params, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    async def _post(self, client: httpx.AsyncClient, path: str, body: dict):
        resp = await client.post(f"{self.base}{path}", json=body, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    # -- 语义 ---------------------------------------------------------------

    async def search(self, title: str, air_date: str) -> list:
        """按原名 + 首播日期 ±10 天窗口搜索动画条目。"""
        if not title or not air_date:
            return []
        from datetime import date, timedelta
        try:
            d = date.fromisoformat(str(air_date)[:10])
        except ValueError:
            return []
        start = (d - timedelta(days=10)).isoformat()
        end = (d + timedelta(days=10)).isoformat()
        body = {
            "keyword": strip_punctuations_spaces(title),
            "sort": "match",
            "filter": {"type": [2], "air_date": [f">={start}", f"<={end}"]},
        }
        async with httpx.AsyncClient(timeout=TIMEOUT, proxy=self.proxy) as client:
            data = await self._post(client, "/v0/search/subjects", body)
        items = (data or {}).get("data")
        if not isinstance(items, list):
            raise ValueError("Bangumi 搜索响应 data 字段格式错误")
        return [item for item in items if isinstance(item, dict)]

    @staticmethod
    def extract_season_number(name_cn: str, name: str) -> int:
        return extract_season_number(name_cn, name)

    async def is_first_episode_sequential(self, sid: int) -> bool:
        """首集的 sort 与 ep 是否相等（不等说明该条目不是从第 1 集开始）。"""
        async with httpx.AsyncClient(timeout=TIMEOUT, proxy=self.proxy) as client:
            resp = await self._get(client, "/v0/episodes", {"subject_id": sid})
        data = (resp or {}).get("data")
        if not isinstance(data, list) or not data:
            raise ValueError(f"Bangumi ID '{sid}' 剧集列表为空")
        ep0 = data[0]
        sort_val, ep_val = ep0.get("sort"), ep0.get("ep")
        if not isinstance(sort_val, (int, float)) or not isinstance(ep_val, (int, float)):
            return False
        return int(sort_val) == int(ep_val)

    async def _all_sequels(self, client: httpx.AsyncClient, bid: int) -> list:
        """沿「续集」关系递归收集整个系列的条目 ID（前序遍历）。"""
        seen: set = set()
        sequence: list = []

        async def walk(current: int) -> None:
            if current in seen:
                return
            seen.add(current)
            sequence.append(current)
            try:
                related = await self._get(client, f"/v0/subjects/{current}/subjects")
            except Exception as e:
                self.log("ERROR", f"获取 Bangumi {current} 相关条目失败: {e}")
                return
            for item in (related or []):
                if isinstance(item, dict) and item.get("relation") == "续集":
                    rid = item.get("id")
                    if isinstance(rid, (int, float)):
                        await walk(int(rid))

        await walk(bid)
        self.log("INFO", f"Bangumi ID {bid} 续集条目: {sequence}")
        return sequence

    async def season_info(self, item: dict) -> Optional[SeriesEntry]:
        """把 Bangumi 系列条目转成分季定义。"""
        bid = item.get("id")
        if not isinstance(bid, (int, float)):
            return None

        async with httpx.AsyncClient(timeout=TIMEOUT, proxy=self.proxy) as client:
            sids = await self._all_sequels(client, int(bid))
            if len(sids) < 2:
                self.log("INFO", "Bangumi 系列仅一个条目，不进行拆分")
                return None

            bgm_seasons: dict = {}
            for sid in sids:
                try:
                    d = await self._get(client, f"/v0/subjects/{sid}")
                except Exception as e:
                    self.log("ERROR", f"获取 Bangumi ID {sid} 详情失败: {e}")
                    continue
                if not d:
                    self.log("WARN", f"Bangumi ID {sid} 详情为空")
                    continue
                platform = d.get("platform")
                if platform in ("剧场版", "OVA"):
                    self.log("INFO", f"{d.get('name_cn')} ID={sid} platform={platform}，跳过处理")
                    continue

                name_cn = d.get("name_cn") if isinstance(d.get("name_cn"), str) else ""
                name = d.get("name") if isinstance(d.get("name"), str) else ""
                num = extract_season_number(name_cn, name)

                eps = 12
                for key in ("eps", "total_episodes"):
                    val = d.get(key)
                    if isinstance(val, (int, float)) and val > 0:
                        eps = int(val)
                        break

                if num not in bgm_seasons:
                    bgm_seasons[num] = SeasonEntry(season_number=num, episode_count=eps, name=name_cn)
                    continue

                try:
                    resp = await self._get(client, "/v0/episodes", {"subject_id": sid})
                    data = (resp or {}).get("data") or []
                    ep0 = data[0] if data else {}
                    sequential = (isinstance(ep0.get("sort"), (int, float))
                                  and isinstance(ep0.get("ep"), (int, float))
                                  and int(ep0["sort"]) == int(ep0["ep"]))
                except Exception as e:
                    self.log("ERROR", f"{e}")
                    bgm_seasons[num].episode_count += eps
                    continue
                if sequential:
                    new_num = max(bgm_seasons) + 1
                    bgm_seasons[new_num] = SeasonEntry(season_number=new_num, episode_count=eps, name=name_cn)
                else:
                    bgm_seasons[num].episode_count += eps

            if not bgm_seasons:
                return None
            seasons = [bgm_seasons[k] for k in sorted(bgm_seasons)]
            return SeriesEntry(name=item.get("name_cn"), seasons=seasons)


# ---------------------------------------------------------------------------
# CureTMDb 规则表
# ---------------------------------------------------------------------------

async def load_cure_source(source: str, proxy: Optional[str] = None) -> dict:
    """加载 CureTMDb 规则表：支持 http(s) URL 或本地文件路径。地址为空则不加载。"""
    source = (source or "").strip()
    if not source:
        raise ValueError("未配置 CureTMDb 规则表地址")
    if source.startswith("http://") or source.startswith("https://"):
        async with httpx.AsyncClient(timeout=30, proxy=proxy, headers={"User-Agent": UA}) as client:
            resp = await client.get(source)
            resp.raise_for_status()
            return resp.json()
    text = Path(source).read_text(encoding="utf-8")
    return json.loads(text)
