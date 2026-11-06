# -*- coding: utf-8 -*-
"""番剧分季拆分 · 业务编排（预览 / 编译 / 保存 / 写剧集组）。"""

from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import httpx

from . import compiler, grouping, store
from .models import SeriesEntry
from .reference import BangumiSeasonChain, TMDBAdapter, TVDBClient, load_cure_source
from .splitter import SeasonSplitter, remove_duplicate_episodes

DEFAULT_GAP_DAYS = 45


def _cfg() -> dict:
    from config_manager import ConfigManager
    return ConfigManager.get_config() or {}


def _priority(cfg: dict) -> List[str]:
    text = str(cfg.get("season_split_priority") or "tvdb, bangumi")
    if text.startswith("仅"):
        return [text.replace("仅", "").strip()]
    return [x.strip() for x in text.split(",") if x.strip()]


def _log_collector(bucket: List[str]) -> Callable:
    def _log(level: str, message: str) -> None:
        bucket.append(f"{level}: {message}")
    return _log


# ---------------------------------------------------------------------------
# TMDB 结构
# ---------------------------------------------------------------------------

async def _fetch_structure(tmdb_id: int, log: Callable) -> dict:
    """拉 TMDB 季结构 + 全部原始季 + 摊平后的集列表。"""
    tmdb = TMDBAdapter(log=log)
    tv_show = await tmdb.tv_detail(tmdb_id)
    if not tv_show:
        raise ValueError(f"TMDB ID {tmdb_id} 未找到剧集详情（或 API Key 未配置）")

    max_season = int(tv_show.get("number_of_seasons") or 1)
    wanted = [s for s in range(1, max_season + 1)]

    async def fetch_one(season: int):
        try:
            return await tmdb.season_detail(tmdb_id, season)
        except Exception as e:  # 单季失败不影响整体
            log("WARN", f"获取 TMDB 第 {season} 季失败: {e}")
            return None

    results = await asyncio.gather(*[fetch_one(s) for s in wanted])
    raw_seasons = [r for r in results if r]
    if max_season > 1:
        raw_seasons = remove_duplicate_episodes(raw_seasons)

    flat = grouping.flatten(raw_seasons)
    actual_counts = {
        int(s["season_number"]): int(s.get("episode_count") or 0)
        for s in (tv_show.get("seasons") or [])
        if isinstance(s.get("season_number"), int)
    }
    return {
        "tmdb": tmdb,
        "tv_show": tv_show,
        "raw_seasons": raw_seasons,
        "flat": flat,
        "actual_counts": actual_counts,
        "max_season": max_season,
    }


def _structure_hash(tv_show: dict) -> str:
    """结构指纹：季数 + 每季集数。用于判断「方案是否过期」。"""
    payload = {
        "n": tv_show.get("number_of_seasons"),
        "s": sorted(
            (int(s.get("season_number") or 0), int(s.get("episode_count") or 0))
            for s in (tv_show.get("seasons") or [])
            if isinstance(s.get("season_number"), int)
        ),
        "status": tv_show.get("status") or "",
    }
    return hashlib.sha1(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


def _is_volatile(tv_show: dict) -> bool:
    """连载中（方案随时可能失效）。"""
    status = str(tv_show.get("status") or "")
    if status in ("Returning Series", "In Production", "Planned"):
        return True
    today = datetime.now().date().isoformat()
    for season in tv_show.get("seasons") or []:
        air = str(season.get("air_date") or "")
        if air and air > today:
            return True
    return False


# ---------------------------------------------------------------------------
# 参照源
# ---------------------------------------------------------------------------

async def _pick_reference(structure: dict, opts: dict, log: Callable) -> Optional[SeriesEntry]:
    cfg = _cfg()
    tmdb = structure["tmdb"]
    tv_show = structure["tv_show"]

    source_data: dict = {}
    if opts.get("use_source"):
        source = (opts.get("source") or cfg.get("season_split_source") or "").strip()
        if not source:
            log("WARN", "勾选了规则表但没配置地址，已跳过（可在「高级 → 默认参数」里填写）")
        else:
            log("INFO", f"加载 CureTMDb 规则表: {source}")
            try:
                source_data = await load_cure_source(source)
                log("INFO", f"规则表条目数: {len(source_data)}")
            except Exception as e:
                log("WARN", f"规则表加载失败，按空表继续: {e}")
                source_data = {}

    priority = opts.get("priority") or _priority(cfg)
    if isinstance(priority, str):
        priority = [x.strip() for x in priority.split(",") if x.strip()]

    splitter = SeasonSplitter(tmdb, log)
    entry = await splitter.fetch_series_entries_sequentially(
        tv_show,
        source_data,
        priority,
        TVDBClient(cfg.get("tvdb_api_key") or "", log=log),
        BangumiSeasonChain(log=log),
        bool(opts.get("force_reference")),
    )
    structure["reference_name"] = splitter.last_reference_name or ""
    return entry


# ---------------------------------------------------------------------------
# 候选分组
# ---------------------------------------------------------------------------

def _candidates(structure: dict, entry: Optional[SeriesEntry], gap_days: int) -> Dict[str, dict]:
    flat = structure["flat"]
    out: Dict[str, dict] = {}

    def add(name: str, groups: list):
        if not groups:
            return
        out[name] = {"groups": groups, "warnings": grouping.validate(groups, flat)}

    if entry is not None and entry.seasons:
        ref = structure.get("reference_name") or "reference"
        add(ref, grouping.from_reference_entry(entry, flat))
    add("gap", grouping.from_gap(flat, gap_days))
    add("year", grouping.from_year(flat))
    add("finale", grouping.from_finale(flat))
    add("fixed12", grouping.from_fixed(flat, 12))
    add("fixed13", grouping.from_fixed(flat, 13))
    add("whole", grouping.from_fixed(flat, max(1, len(flat))))
    return out


def _pick_default(candidates: Dict[str, dict], need_split: bool, reference_name: str) -> str:
    if need_split and reference_name in candidates:
        return reference_name
    for name in ("gap", "year", "finale"):
        item = candidates.get(name)
        if item and len(item["groups"]) > 1:
            return name
    if need_split and candidates:
        return next(iter(candidates))
    return "whole" if "whole" in candidates else (next(iter(candidates)) if candidates else "")


# ---------------------------------------------------------------------------
# 编译
# ---------------------------------------------------------------------------

def compile_rule(tmdb_id: int, flat: list, groups: list,
                 overrides: Optional[dict] = None, excluded: Optional[list] = None,
                 names: Optional[dict] = None, reference: str = "",
                 title: str = "") -> dict:
    """分组 → 映射表 / 渲染词 / 剧集组 / 逐集明细 / 告警。"""
    names = {int(k): v for k, v in (names or {}).items() if str(k).isdigit()}
    mapping = compiler.mapping_from_groups(groups, flat, overrides, excluded)
    years = compiler.season_years_from_mapping(mapping, flat)
    words = compiler.generate_render_words(tmdb_id, title, reference, mapping, years)
    air_dates = {
        (int(ep.get("season_number") or 0), int(ep.get("episode_number") or 0)): ep.get("air_date") or ""
        for ep in (flat or [])
    }
    group_json = compiler.group_json_from_mapping(tmdb_id, mapping, names, air_dates)
    warnings = grouping.validate(groups, flat)

    # 逐集明细要带标题/播出日期，供页面展示（之前没传查找表，标题列是空的）
    raw_lookup = {
        f"S{int(ep.get('season_number') or 0)}E{int(ep.get('episode_number') or 0)}": ep
        for ep in (flat or [])
    }

    # 回放自检：编译出的规则必须能还原映射表，否则说明分段算法出了问题
    replay_bad = []
    for (s, e), (vs, ve) in mapping.items():
        got = compiler.apply_rules_to_episode(words, s, e, tmdb_id)
        if got != (vs, ve):
            replay_bad.append({"from": [s, e], "expect": [vs, ve], "got": list(got)})
    if replay_bad:
        warnings.append(f"规则回放与映射表有 {len(replay_bad)} 处不一致（请检查分组定义）")

    return {
        "mapping": compiler.dump_mapping(mapping),
        "mapping_raw": {f"{s}-{e}": [vs, ve] for (s, e), (vs, ve) in mapping.items()},
        "render_words": words,
        "group_json": group_json,
        "rows": compiler.episode_rows(mapping, raw_lookup),
        "season_years": years,
        "warnings": warnings,
        "replay_bad": replay_bad,
        "episode_total": len(mapping),
    }


# ---------------------------------------------------------------------------
# 对外的四个动作
# ---------------------------------------------------------------------------

async def preview(tmdb_id: int, opts: Optional[dict] = None) -> dict:
    """预览：拉结构 + 挑参照 + 出候选分组 + 编译默认方案。不落库。"""
    opts = opts or {}
    logs: List[str] = []
    log = _log_collector(logs)
    cfg = _cfg()
    gap_days = int(cfg.get("season_split_gap_days") or DEFAULT_GAP_DAYS)

    log("INFO", f"开始分析 TMDB {tmdb_id}")
    structure = await _fetch_structure(tmdb_id, log)
    tv_show = structure["tv_show"]
    flat = structure["flat"]
    if not flat:
        raise ValueError("TMDB 没有返回任何剧集数据")

    entry = await _pick_reference(structure, opts, log)
    reference_name = structure.get("reference_name") or ""
    need_split = bool(entry is not None and entry.has_inconsistent(structure["actual_counts"]))
    if entry is None:
        log("INFO", "未取得分季参照（TVDB/Bangumi/规则表均无结果），仅提供算法候选")
    elif need_split:
        log("INFO", f"分季依据 {reference_name} 与 TMDB 结构不一致 → 需要拆分")
    else:
        log("INFO", "TMDB 结构与分季定义一致 → 不需要拆分")

    candidates = _candidates(structure, entry, gap_days)
    default_basis = _pick_default(candidates, need_split, reference_name)
    title = tv_show.get("name") or tv_show.get("original_name") or f"TMDB {tmdb_id}"

    compiled = {"mapping": {}, "render_words": "", "group_json": {}, "rows": [], "warnings": []}
    if default_basis and default_basis in candidates:
        compiled = compile_rule(
            tmdb_id, flat, candidates[default_basis]["groups"],
            reference=default_basis, title=title,
        )

    definition = []
    if entry is not None:
        for season in sorted(entry.seasons, key=lambda s: s.season_number):
            definition.append({
                "season_number": season.season_number,
                "name": season.name or f"第 {season.season_number} 季",
                "episode_count": season.episode_count,
                "include": [
                    {"order": i.order, "count": i.count,
                     "season_number": i.season_number, "episode_number": i.episode_number}
                    for i in season.include
                ],
            })

    existing = await store.get_rule(tmdb_id)
    structure_hash = _structure_hash(tv_show)

    return {
        "tmdb_id": tmdb_id,
        "title": title,
        "reference": reference_name,
        "need_split": need_split,
        "volatile": _is_volatile(tv_show),
        "status": tv_show.get("status") or "",
        "tmdb_hash": structure_hash,
        "stale": bool(existing and existing.get("tmdb_hash")
                      and existing["tmdb_hash"] != structure_hash),
        "tmdb": {
            "number_of_seasons": structure["max_season"],
            "seasons": tv_show.get("seasons") or [],
            "poster_path": tv_show.get("poster_path") or "",
            "first_air_date": tv_show.get("first_air_date") or "",
        },
        "episodes": flat,
        "gaps": grouping.gaps(flat),
        "definition": definition,
        "candidates": candidates,
        "default_basis": default_basis,
        "suggested": compiled,
        "existing_rule": existing,
        "gap_days": gap_days,
        "logs": logs,
    }


async def compile_only(payload: dict) -> dict:
    """按前端提交的分组重新编译（不落库）。"""
    tmdb_id = int(payload["tmdb_id"])
    logs: List[str] = []
    structure = await _fetch_structure(tmdb_id, _log_collector(logs))
    title = structure["tv_show"].get("name") or f"TMDB {tmdb_id}"
    out = compile_rule(
        tmdb_id, structure["flat"],
        payload.get("groups") or [],
        overrides=payload.get("overrides"),
        excluded=payload.get("excluded"),
        names=payload.get("names"),
        reference=payload.get("reference") or "manual",
        title=title,
    )
    out.update({"tmdb_id": tmdb_id, "title": title, "logs": logs})
    return out


async def save(payload: dict) -> dict:
    """保存规则：重新编译一次再落库，保证库里的 render_words 与分组一致。"""
    tmdb_id = int(payload["tmdb_id"])
    logs: List[str] = []
    structure = await _fetch_structure(tmdb_id, _log_collector(logs))
    tv_show = structure["tv_show"]
    title = tv_show.get("name") or f"TMDB {tmdb_id}"

    compiled = compile_rule(
        tmdb_id, structure["flat"],
        payload.get("groups") or [],
        overrides=payload.get("overrides"),
        excluded=payload.get("excluded"),
        names=payload.get("names"),
        reference=payload.get("reference") or "manual",
        title=title,
    )
    if not compiled["mapping"]:
        raise ValueError("分组为空，无法保存（至少要有 1 集被覆盖）")

    record = await store.upsert_rule({
        "tmdb_id": tmdb_id,
        "title": title,
        "status": payload.get("status") or "draft",
        "reference": payload.get("reference") or "manual",
        "groups_json": payload.get("groups") or [],
        "overrides_json": payload.get("overrides") or {},
        "excluded_json": payload.get("excluded") or [],
        "names_json": payload.get("names") or {},
        "mapping_json": compiled["mapping"],
        "group_json": compiled["group_json"],
        "render_words": compiled["render_words"],
        "tmdb_hash": _structure_hash(tv_show),
        "episode_total": compiled["episode_total"],
    })
    record["compile"] = compiled
    record["logs"] = logs
    return record


async def push_episode_group(tmdb_id: int) -> dict:
    """把规则里的剧集组写入 SYTMDB（先探活，404 则创建，再整体覆盖）。"""
    rule = await store.get_rule(tmdb_id)
    if not rule:
        raise ValueError("该番还没有保存过分季规则")
    groups = (rule.get("group_json") or {}).get("groups") or []
    if not groups:
        raise ValueError("规则里没有剧集组数据")

    cfg = _cfg()
    addr = (cfg.get("sytmdb_host") or "").strip()
    token = (cfg.get("sytmdb_token") or "").strip()
    if not addr:
        raise ValueError("未配置 SYTMDB 地址（系统设置 → SYTMDB）")

    url = _sytmdb_url(addr, tmdb_id)
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    async with httpx.AsyncClient(timeout=30) as client:
        probe = await client.get(url, headers=headers)
        if probe.status_code != 200:
            created = await client.post(url, headers=headers)
            if created.status_code >= 400:
                raise ValueError(f"SYTMDB 创建剧集组失败 HTTP {created.status_code}: {created.text[:200]}")
        resp = await client.put(url, headers=headers, json={"groups": groups})

    if resp.status_code >= 400:
        raise ValueError(f"SYTMDB 写入失败 HTTP {resp.status_code}: {resp.text[:200]}")
    return {
        "tmdb_id": tmdb_id,
        "groups": len(groups),
        "message": f"已写入 {len(groups)} 个剧集组",
        "response": resp.json() if resp.content else {},
    }


def _sytmdb_url(addr: str, tmdb_id: int) -> str:
    addr = addr.rstrip("/")
    if addr and not addr.startswith("http"):
        return f"http://{addr}:8121/api/tv/{tmdb_id}/episodegroup"
    return f"{addr}/api/tv/{tmdb_id}/episodegroup"


async def debug_episode(tmdb_id: int, season: int, episode: int, filename: str = "") -> dict:
    """映射调试器：给定一集的原始坐标，回放该番已保存的规则。"""
    rule = await store.get_rule(tmdb_id)
    if not rule:
        raise ValueError("该番还没有保存过分季规则")
    words = rule.get("render_words") or ""
    got = compiler.apply_rules_to_episode(words, season, episode, tmdb_id, filename=filename)
    return {
        "tmdb_id": tmdb_id,
        "from": [season, episode],
        "to": list(got),
        "changed": list(got) != [season, episode],
        "rule_status": rule.get("status"),
        "reference": rule.get("reference"),
        "render_words": words,
    }


def settings_snapshot() -> dict:
    cfg = _cfg()
    return {
        "mode": cfg.get("season_split_mode") or "off",
        "scope": cfg.get("season_split_scope") or {},
        "blacklist": cfg.get("season_split_blacklist") or [],
        "exclude_patterns": cfg.get("season_split_exclude_patterns") or [],
        "priority": cfg.get("season_split_priority") or "tvdb, bangumi",
        "source": cfg.get("season_split_source") or "",
        "gap_days": cfg.get("season_split_gap_days") or DEFAULT_GAP_DAYS,
        "tvdb_key_configured": bool((cfg.get("tvdb_api_key") or "").strip()),
        "cache": store.cache_stats(),
    }


def settings_update(payload: dict) -> dict:
    from config_manager import ConfigManager

    allowed = {
        "season_split_mode", "season_split_scope", "season_split_blacklist",
        "season_split_exclude_patterns", "season_split_priority", "season_split_source",
        "season_split_gap_days", "tvdb_api_key",
    }
    patch = {k: v for k, v in (payload or {}).items() if k in allowed}
    if "season_split_mode" in patch:
        mode = str(patch["season_split_mode"]).lower()
        if mode not in ("off", "preview", "on"):
            raise ValueError("season_split_mode 只能是 off / preview / on")
        patch["season_split_mode"] = mode
    if patch:
        ConfigManager.update_config(patch)
    return settings_snapshot()
