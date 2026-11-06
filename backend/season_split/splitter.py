# -*- coding: utf-8 -*-
"""番剧分季拆分 · 核心算法。

移植自 Lens `backend/app/modules/cure_splitter/splitter.py`
（其上游为 CureTMDbAnime(Go) internal/processor/splitter.go）。

**分季逻辑一行不改**：并发拉原始季 → 同日去重 → 按播出日期摊平 → 按定义重灌切虚拟季。
唯一改动：把原版同步 `requests` / `ThreadPoolExecutor` 换成异步 fetcher / `asyncio.gather`，
fetcher 由调用方注入（见 `season_split/reference.py` 的 TMDBAdapter）。
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Callable, Optional

from .constants import ANIME_GENRE_ID
from .models import EpisodeMap, LogicSeries, SeriesEntry

# 异步 fetcher 协议（由 reference.TMDBAdapter 实现）：
#   await tmdb.tv_detail(tmdb_id) -> dict | None
#   await tmdb.season_detail(tmdb_id, season) -> dict | None
#   await tmdb.movie_detail(movie_id) -> dict | None


def completeness_score(episode: dict) -> int:
    """集数据完整度评分：name+10 overview+8 still_path+5 vote_average+3 其余字段各+1。"""
    score = 0
    if episode.get("name"):
        score += 10
    if episode.get("overview"):
        score += 8
    if episode.get("still_path"):
        score += 5
    va = episode.get("vote_average")
    if isinstance(va, (int, float)) and va != 0:
        score += 3
    skip = {"name", "overview", "still_path", "vote_average", "air_date",
            "season_number", "episode_number", "id"}
    for k, v in episode.items():
        if k in skip:
            continue
        if v is None or isinstance(v, bool):
            continue
        if isinstance(v, str) and v == "":
            continue
        score += 1
    return score


@dataclass
class _AugEpisode:
    episode: dict
    season_idx: int
    ep_idx: int
    season_number: int

    def slot(self) -> tuple:
        return (self.season_idx, self.ep_idx)

    def is_earlier_than(self, other: "_AugEpisode") -> bool:
        return self.slot() < other.slot()

    def is_better_content_than(self, other: "_AugEpisode") -> bool:
        score, other_score = completeness_score(self.episode), completeness_score(other.episode)
        if score != other_score:
            return score > other_score
        return self.is_earlier_than(other)


def remove_duplicate_episodes(raw_seasons: list) -> list:
    """同 air_date 跨季去重：保留最早槽位的位置字段，内容取最完整者。"""
    by_air_date: dict = {}
    for season_idx, season in enumerate(raw_seasons):
        season_num = int(season.get("season_number") or 0)
        for ep_idx, ep in enumerate(season.get("episodes") or []):
            air = ep.get("air_date") or ""
            if not air:
                continue
            by_air_date.setdefault(air, []).append(_AugEpisode(ep, season_idx, ep_idx, season_num))

    to_remove: set = set()
    for group in by_air_date.values():
        if len(group) <= 1:
            continue
        keeper, best = group[0], group[0]
        cross_season = False
        for candidate in group[1:]:
            if candidate.season_number != keeper.season_number:
                cross_season = True
            if candidate.is_earlier_than(keeper):
                keeper = candidate
            if candidate.is_better_content_than(best):
                best = candidate
        if not cross_season:
            continue

        original = (keeper.episode.get("season_number"),
                    keeper.episode.get("episode_number"),
                    keeper.episode.get("id"))
        keeper.episode.update(best.episode)
        keeper.episode["season_number"] = original[0]
        keeper.episode["episode_number"] = original[1]
        keeper.episode["id"] = original[2]

        for candidate in group:
            if candidate.slot() != keeper.slot():
                to_remove.add(candidate.slot())

    result: list = []
    for season_idx, season in enumerate(raw_seasons):
        filtered = [
            ep for ep_idx, ep in enumerate(season.get("episodes") or [])
            if (season_idx, ep_idx) not in to_remove
        ]
        if not filtered:
            continue
        season["episodes"] = filtered
        result.append(season)
    return result


def first_air_year(air_date) -> Optional[int]:
    """'2026-04-05' → 2026；空或非日期开头返回 None。"""
    text = str(air_date or "").strip()
    if len(text) >= 4 and text[:4].isdigit():
        return int(text[:4])
    return None


def mapping_to_json(org_map: dict) -> dict:
    """逐集映射 → 与 Go 服务 /cache/mapping 接口相同的格式。"""
    out: dict = {}
    for (src_s, src_e), (dst_s, dst_e) in sorted(org_map.items()):
        out.setdefault(str(src_s), {})[str(src_e)] = {"season": dst_s, "episode": dst_e}
    return out


class SeasonSplitter:
    """按「分季定义」把 TMDB 的合并季重灌成虚拟季。

    tmdb/tvdb/bangumi 为异步 fetcher（见文件头协议），log 为 (level, message) 回调。
    """

    def __init__(self, tmdb, log: Callable = None):
        self.tmdb = tmdb
        self.log = log or (lambda level, msg: None)
        # 全量原始集查找表: "S{s}E{e}" -> 集数据（含 S0），用于季首播日期与展示
        self.raw_ep_lookup: dict = {}
        # 选中的分季依据名称（curetmdb/tvdb/bangumi），用于规则来源标注
        self.last_reference_name: str = ""

    # -- 参照获取 ------------------------------------------------------------

    def fetch_cure_tmdb_entry(self, source_data: dict, tmdb_id: int) -> Optional[SeriesEntry]:
        entry = source_data.get(str(tmdb_id))
        if isinstance(entry, dict) and entry.get("seasons"):
            self.last_reference_name = "curetmdb"
            self.log("INFO", f"分季依据选中: tmdbID={tmdb_id}, 依据=curetmdb")
            return SeriesEntry.decode(entry)
        return None

    async def fetch_tvdb_entry(self, tvdb, tvdb_id: int) -> Optional[SeriesEntry]:
        if tvdb_id > 0:
            return await tvdb.get_series_entry(tvdb_id)
        return None

    async def fetch_bangumi_entry(self, bangumi, tv_show: dict) -> Optional[SeriesEntry]:
        original_name = tv_show.get("original_name") or ""
        first_air = tv_show.get("first_air_date") or ""
        items = await bangumi.search(original_name, first_air)
        if not items:
            return None
        return await bangumi.season_info(items[0])

    async def handle_two_seasons_check(self, bangumi, tv_show: dict) -> tuple:
        """TMDB 恰有 2 季时的 Bangumi 特殊检查。返回 (should_skip, error)。"""
        seasons = tv_show.get("seasons") or []

        def valid_seasons() -> list:
            out = []
            for s in seasons:
                num = s.get("season_number")
                cnt = s.get("episode_count")
                air = (s.get("air_date") or "").strip()
                if not isinstance(num, int) or num <= 0:
                    continue
                if not isinstance(cnt, (int, float)) or cnt <= 0:
                    continue
                if not air:
                    continue
                out.append(s)
            out.sort(key=lambda s: s["season_number"])
            prev = ""
            valid = []
            for s in out:
                air = s["air_date"].strip()
                if prev and air <= prev:
                    continue
                valid.append(s)
                prev = air
            return valid

        vs = valid_seasons()
        air_date = None
        if len(vs) >= 2:
            air_date = vs[1].get("air_date")
        if not air_date:
            for s in seasons:
                if s.get("season_number") == 2:
                    air_date = s.get("air_date")
                    break
        if not air_date:
            air_date = tv_show.get("first_air_date")
        if not air_date:
            return False, None

        try:
            items = await bangumi.search(tv_show.get("original_name") or "", air_date)
        except Exception as e:
            self.log("ERROR", f"Bangumi API 搜索 seasonCount=2 失败: {e}")
            return False, None
        if not items:
            return False, None
        item = items[0]
        name_cn = item.get("name_cn") if isinstance(item.get("name_cn"), str) else None
        name = item.get("name") if isinstance(item.get("name"), str) else None
        if name_cn is None or name is None:
            return False, None

        season_num = bangumi.extract_season_number(name_cn, name)
        if season_num != 1:
            return False, None

        bid = item.get("id")
        if not isinstance(bid, (int, float)):
            return False, None
        try:
            sequential = await bangumi.is_first_episode_sequential(int(bid))
        except Exception as e:
            return False, e
        return (not sequential), None

    async def fetch_series_entries_sequentially(
        self,
        tv_show: dict,
        source_data: dict,
        priority: list,
        tvdb,
        bangumi,
        force_reference: bool,
    ) -> Optional[SeriesEntry]:
        tmdb_id = int(tv_show.get("id"))
        entry = self.fetch_cure_tmdb_entry(source_data, tmdb_id)
        if entry is not None:
            return entry

        # 自动参照仅处理日本动画，且有效季数 1~2
        genre_ids = [g.get("id") for g in (tv_show.get("genres") or []) if isinstance(g, dict)]
        if not genre_ids:
            genre_ids = tv_show.get("_genre_ids") or []
        is_anime = ANIME_GENRE_ID in genre_ids
        is_jp = "JP" in (tv_show.get("origin_country") or [])
        if not force_reference and not (is_anime and is_jp):
            self.log("INFO", "非日本动画，跳过 TVDB/Bangumi 自动参照")
            return None

        valid_seasons_count = len(self._valid_seasons(tv_show))
        if not force_reference and (valid_seasons_count <= 0 or valid_seasons_count >= 3):
            self.log("INFO", f"有效季数={valid_seasons_count}，不在 1~2 范围，跳过自动参照")
            return None

        for reference in priority:
            self.log("INFO", f"分季依据尝试: tmdbID={tmdb_id}, 依据={reference}")
            entry: Optional[SeriesEntry] = None
            try:
                if reference == "bangumi":
                    if valid_seasons_count == 2 and not force_reference:
                        should_skip, check_err = await self.handle_two_seasons_check(bangumi, tv_show)
                        if check_err is not None:
                            self.log("WARN", f"分季依据 bangumi 2季特殊检查失败，继续通用查询: {check_err}")
                        elif should_skip:
                            self.log("INFO", "2季特殊检查命中，视为无需拆分")
                            return None
                    entry = await self.fetch_bangumi_entry(bangumi, tv_show)
                elif reference == "tvdb":
                    tvdb_id = int(((tv_show.get("external_ids") or {}).get("tvdb_id")) or 0)
                    entry = await self.fetch_tvdb_entry(tvdb, tvdb_id)
            except Exception as e:
                self.log("WARN", f"分季依据 {reference} 获取信息失败: {e}")
                continue
            if entry is not None and entry.seasons:
                self.last_reference_name = reference
                self.log("INFO", f"分季依据选中: tmdbID={tmdb_id}, 依据={reference}")
                return entry
            self.log("INFO", f"分季依据返回空结果: tmdbID={tmdb_id}, 依据={reference}")

        self.log("INFO", f"分季依据均未返回结果: tmdbID={tmdb_id}")
        return None

    @staticmethod
    def _valid_seasons(tv_show: dict) -> list:
        seasons = []
        for s in tv_show.get("seasons") or []:
            num, cnt = s.get("season_number"), s.get("episode_count")
            air = (s.get("air_date") or "").strip()
            if not isinstance(num, int) or num <= 0:
                continue
            if not isinstance(cnt, (int, float)) or cnt <= 0:
                continue
            if not air:
                continue
            seasons.append(s)
        seasons.sort(key=lambda s: s["season_number"])
        prev, valid = "", []
        for s in seasons:
            air = s["air_date"].strip()
            if prev and air <= prev:
                continue
            valid.append(s)
            prev = air
        return valid

    # -- 主流程 --------------------------------------------------------------

    async def fetch_seasons(self, tmdb_id: int, start: int, end: int) -> list:
        """并发拉取 TMDB 季详情 [start, end]，按季号排序（finale 分组用）。"""
        wanted = list(range(start, end + 1))

        async def fetch_one(s: int):
            try:
                detail = await self.tmdb.season_detail(tmdb_id, s)
            except Exception as e:
                self.log("WARN", f"获取 TMDB 季详情失败: ID={tmdb_id} 季={s}: {e}")
                return s, None
            return s, detail

        results = await asyncio.gather(*[fetch_one(s) for s in wanted]) if wanted else []
        raw = {s: d for s, d in results if d}
        return [{**raw[s], "season_number": s} for s in sorted(raw)]

    async def process_tv(
        self,
        tmdb_id: int,
        source_data: dict,
        priority: list,
        tvdb,
        bangumi,
        force_reference: bool,
    ) -> Optional[LogicSeries]:
        tv_show = await self.tmdb.tv_detail(tmdb_id)
        if not tv_show:
            raise ValueError(f"TMDB ID {tmdb_id} 未找到剧集详情")

        series = await self.fetch_series_entries_sequentially(
            tv_show, source_data, priority, tvdb, bangumi, force_reference,
        )
        if series is None:
            return None

        actual_counts = {
            int(s["season_number"]): int(s.get("episode_count") or 0)
            for s in (tv_show.get("seasons") or [])
            if isinstance(s.get("season_number"), int)
        }
        if not series.has_inconsistent(actual_counts):
            self.log("INFO", f"剧集结构一致，无需构建: tmdbID={tmdb_id}")
            return None

        return await self.build_logic_series(tmdb_id, tv_show, series)

    # -- 构建逻辑季 ----------------------------------------------------------

    async def _fetch_raw_seasons(self, tmdb_id: int, series: SeriesEntry, max_season: int) -> list:
        """并发拉取 TMDB 原始季详情（min_season..max_season），按季号排序保证确定性。"""
        wanted = list(range(series.min_season(), max_season + 1))

        async def fetch_one(s: int):
            try:
                detail = await self.tmdb.season_detail(tmdb_id, s)
            except Exception as e:
                self.log("WARN", f"获取 TMDB 季详情失败: ID={tmdb_id} 季={s}: {e}")
                return s, None
            return s, detail

        results = await asyncio.gather(*[fetch_one(s) for s in wanted]) if wanted else []
        raw = {s: d for s, d in results if d}
        out = []
        for s in sorted(raw):
            detail = raw[s]
            detail.setdefault("season_number", s)
            out.append(detail)
        return out

    async def build_logic_series(self, tmdb_id: int, tv_show: dict, series: SeriesEntry) -> LogicSeries:
        logic = LogicSeries(
            name=series.name,
            vote_average=float(tv_show.get("vote_average") or 0),
            poster_path=tv_show.get("poster_path"),
            overview=tv_show.get("overview"),
        )

        max_season = int(tv_show.get("number_of_seasons") or 0)
        raw_seasons = await self._fetch_raw_seasons(tmdb_id, series, max_season)

        # 特殊季（S0）仅进入查找表，不参与摊平
        if series.has_any_special_season():
            detail = await self.tmdb.season_detail(tmdb_id, 0)
            if detail:
                for ep in detail.get("episodes") or []:
                    sn, en = int(ep.get("season_number") or 0), int(ep.get("episode_number") or 0)
                    self.raw_ep_lookup[f"S{sn}E{en}"] = ep
                    if sn == 0:
                        self.raw_ep_lookup[f"S0E{en}"] = ep

        if max_season > 1:
            raw_seasons = remove_duplicate_episodes(raw_seasons)

        raw_eps = self._flatten_and_sort(raw_seasons)
        if not raw_eps:
            self.log("WARN", "摊平后无可用剧集，返回空逻辑季")
            return logic

        # 收集展示用查找表（含全部已拉取季）
        for season in raw_seasons:
            sn = int(season.get("season_number") or 0)
            for ep in season.get("episodes") or []:
                en = int(ep.get("episode_number") or 0)
                self.raw_ep_lookup.setdefault(f"S{sn}E{en}", ep)

        mapping = series.episode_mapping()
        missing_eps = series.missing_by_season()
        season_names = series.season_names()

        curr_s_idx = series.min_season()
        curr_missing = list(missing_eps.get(curr_s_idx, []))
        logic_ep_num = 0

        for i, ep in enumerate(raw_eps):
            season_num = int(ep.get("season_number") or 0)
            episode_num = int(ep.get("episode_number") or 0)
            if season_num != 0 or episode_num != 0:
                self.raw_ep_lookup[f"S{season_num}E{episode_num}"] = ep

            if curr_missing:
                logic_ep_num = curr_missing[0]
                curr_missing = curr_missing[1:]
            else:
                logic_ep_num += 1

            season_map = mapping.setdefault(curr_s_idx, {})
            season_map[logic_ep_num] = EpisodeMap(
                order=logic_ep_num,
                episode_number=episode_num,
                season_number=season_num,
                type="tv",
                tmdbid=tmdb_id,
            )

            is_last = i == len(raw_eps) - 1
            while (curr_s_idx in missing_eps and len(curr_missing) == 0) or is_last:
                if curr_s_idx not in season_names:
                    season_names[curr_s_idx] = f"第 {curr_s_idx} 季"
                    defined_max = max(season_names) if season_names else 0
                    self.log("WARN", f"原始集数超出分季定义覆盖(定义到 S{defined_max})，"
                                     f"季 {curr_s_idx} 的溢出集数使用默认季名")
                air_date, poster = await self._first_episode_metadata(season_map)
                logic.add_season(season_names[curr_s_idx], air_date, curr_s_idx, season_map, poster)
                if is_last:
                    break
                curr_s_idx += 1
                curr_missing = list(missing_eps.get(curr_s_idx, []))
                logic_ep_num = 0

        return logic

    @staticmethod
    def _flatten_and_sort(raw_seasons: list) -> list:
        """全部集打平，按 air_date 升序（无日期的排最后）。"""
        all_eps: list = []
        for season in raw_seasons:
            sn = season.get("season_number")
            if sn is None:
                continue
            sn = int(sn)
            for ep in season.get("episodes") or []:
                ep["season_number"] = sn
                all_eps.append(ep)
        return sorted(all_eps, key=lambda e: (not bool(e.get("air_date")), e.get("air_date") or ""))

    async def _first_episode_metadata(self, season_map: dict) -> tuple:
        if not season_map:
            return None, None
        min_order = min(season_map.keys())
        first = season_map[min_order]
        if first.season_num() < 0 and first.tmdbid is not None:
            movie = await self.tmdb.movie_detail(first.tmdbid)
            if movie:
                return movie.get("air_date"), movie.get("still_path")
            return None, None
        found = self.raw_ep_lookup.get(f"S{first.season_num()}E{first.episode_num()}")
        if found:
            return found.get("air_date"), found.get("still_path")
        return None, None


def logic_result_to_group_json_text(group_json: Optional[dict]) -> str:
    if not group_json:
        return ""
    return json.dumps(group_json, ensure_ascii=False, indent=2)
