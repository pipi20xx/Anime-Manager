# -*- coding: utf-8 -*-
"""番剧分季拆分 · 业务编排（预览 / 编译 / 保存 / 写剧集组）。"""

from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import httpx

from . import compiler, grouping, store, sytmdb_source
from .constants import ANIME_GENRE_ID
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


def _cfg_list(cfg: dict, key: str, default: list) -> list:
    """读 list 配置：区分「未设置」与「显式设成空列表」。"""
    val = cfg.get(key)
    return list(val) if isinstance(val, list) else default


def _cfg_int(cfg: dict, key: str, default: int) -> int:
    """读 int 配置，缺失/非法时回退默认。"""
    val = cfg.get(key)
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _cfg_bool(cfg: dict, key: str, default: bool) -> bool:
    """读 bool 配置，缺失/非法时回退默认。"""
    val = cfg.get(key)
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.strip().lower() in ("1", "true", "yes", "on")
    return default


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

async def _collect_references(structure: dict, opts: dict, log: Callable) -> dict:
    """一次性把可用的分季定义全部取回来：{basis: SeriesEntry}。

    和 Lens 的「按优先级取第一个」不同：这里 TVDB / Bangumi / 规则表 都尝试，
    结果全部作为候选交给页面，由人决定用哪一个（右侧「自动生成」可切换）。
    """
    cfg = _cfg()
    tmdb = structure["tmdb"]
    tv_show = structure["tv_show"]
    entries: dict = {}

    splitter = SeasonSplitter(tmdb, log)

    # 1) CureTMDb 规则表（命中即用，不依赖后面的国家/季数门槛）
    use_source = opts.get("use_source")
    if use_source is None:
        use_source = bool(cfg.get("season_split_use_source"))
    if use_source:
        source = (opts.get("source") or cfg.get("season_split_source") or "").strip()
        if not source:
            log("WARN", "启用了规则表但没配置地址，已跳过（高级 → 默认参数里填写）")
        else:
            log("INFO", f"加载 CureTMDb 规则表: {source}")
            try:
                source_data = await load_cure_source(source)
                log("INFO", f"规则表条目数: {len(source_data)}")
                entry = splitter.fetch_cure_tmdb_entry(source_data, int(tv_show.get("id")))
                if entry is not None:
                    entries["curetmdb"] = entry
            except Exception as e:
                log("WARN", f"规则表加载失败，跳过: {e}")

    force = opts.get("force_reference")
    if force is None:
        force = bool(cfg.get("season_split_force_reference"))

    # 2) 自动参照门槛：动画类型 / 出品国家 / 有效季数范围（高级里可配置，force 可整体跳过）
    ref_genre_ids = {
        int(x) for x in _cfg_list(cfg, "season_split_ref_genre_ids", [ANIME_GENRE_ID])
        if str(x).strip().lstrip("-").isdigit()
    }
    ref_countries = {
        str(c or "").strip().upper()
        for c in _cfg_list(cfg, "season_split_ref_countries", ["JP"])
        if str(c or "").strip()
    }
    season_min = _cfg_int(cfg, "season_split_ref_season_min", 1)
    season_max = _cfg_int(cfg, "season_split_ref_season_max", 2)

    genre_ids = [g.get("id") for g in (tv_show.get("genres") or []) if isinstance(g, dict)]
    if not genre_ids:
        genre_ids = tv_show.get("_genre_ids") or []
    genre_ids = {
        int(g) for g in genre_ids
        if isinstance(g, (int, str)) and str(g).strip().lstrip("-").isdigit()
    }
    origin = {str(c or "").strip().upper() for c in (tv_show.get("origin_country") or [])}

    is_anime = bool(ref_genre_ids & genre_ids) if ref_genre_ids else True
    is_country = bool(ref_countries & origin) if ref_countries else True
    valid_seasons = len(SeasonSplitter._valid_seasons(tv_show))

    if not force and not (is_anime and is_country):
        log("INFO", "未通过「动画类型 + 出品国家」参照门槛，跳过 TVDB / Bangumi（高级里可改门槛或开「强制参照」）")
        structure["reference_name"] = next(iter(entries), "")
        return entries
    if not force and not (season_min <= valid_seasons <= season_max):
        log("INFO", f"有效季数={valid_seasons}，不在 {season_min}~{season_max} 范围，跳过 TVDB / Bangumi（高级里可改或强制）")
        structure["reference_name"] = next(iter(entries), "")
        return entries

    # 3) TVDB（独立尝试，失败不影响 Bangumi）
    tvdb_id = int(((tv_show.get("external_ids") or {}).get("tvdb_id")) or 0)
    if tvdb_id > 0:
        log("INFO", f"TVDB 参照尝试: tvdbID={tvdb_id}")
        try:
            entry = await splitter.fetch_tvdb_entry(TVDBClient(cfg.get("tvdb_api_key") or "", log=log), tvdb_id)
            if entry is not None and entry.seasons:
                entries["tvdb"] = entry
                log("INFO", f"TVDB 参照命中: {len(entry.seasons)} 季定义")
            else:
                log("INFO", "TVDB 参照未返回结果")
        except Exception as e:
            log("WARN", f"TVDB 参照失败: {e}")
    else:
        log("INFO", "TMDB 没有关联 tvdb_id，跳过 TVDB 参照")

    # 4) Bangumi（续集链 → 分季定义）
    log("INFO", "Bangumi 参照尝试")
    try:
        entry = await splitter.fetch_bangumi_entry(BangumiSeasonChain(log=log), tv_show)
        if entry is not None and entry.seasons:
            entries["bangumi"] = entry
            log("INFO", f"Bangumi 参照命中: {len(entry.seasons)} 季定义")
        else:
            log("INFO", "Bangumi 参照未返回结果（单条目或未匹配到）")
    except Exception as e:
        log("WARN", f"Bangumi 参照失败: {e}")

    structure["reference_name"] = next(iter(entries), "")
    return entries

# ---------------------------------------------------------------------------
# 候选分组
# ---------------------------------------------------------------------------

# 参照源的固定展示顺序（与「参照优先级」设置无关，只影响候选按钮排列）
_REF_ORDER = ("curetmdb", "tvdb", "bangumi")


def _candidates(structure: dict, entries: dict, gap_days: int,
                fixed_sizes: Optional[list] = None) -> Dict[str, dict]:
    """所有候选分组：每个参照源一套 + 算法兜底。

    参照源不再「按优先级只取第一个」——TVDB / Bangumi / 规则表 各出一套，
    页面右侧「自动生成」里逐个可切换比较；固定集数兜底的每季集数可在高级里改。
    """
    flat = structure["flat"]
    out: Dict[str, dict] = {}

    def add(name: str, groups: list):
        if not groups:
            return
        out[name] = {"groups": groups, "warnings": grouping.validate(groups, flat)}

    for basis in _REF_ORDER:
        entry = entries.get(basis)
        if entry is not None and entry.seasons:
            add(basis, grouping.from_reference_entry(entry, flat))

    add("gap", grouping.from_gap(flat, gap_days))
    add("year", grouping.from_year(flat))
    add("finale", grouping.from_finale(flat))
    for size in (fixed_sizes or [12, 13]):
        try:
            size = int(size)
        except (TypeError, ValueError):
            continue
        if size > 0:
            add(f"fixed{size}", grouping.from_fixed(flat, size))
    add("whole", grouping.from_fixed(flat, max(1, len(flat))))
    return out


def _identity_groups(flat: list) -> list:
    """TMDB 自己的季边界（恒等映射）→ 分组。

    用于「连番号折算」：分组是恒等的，所以 mapping / 剧集组仍是 TMDB 原生坐标，
    只有在渲染词里追加的那一段才把 1..N 折回 (s,e)。
    单季番返回 []（没有跨季边界，不需要换算）。
    """
    items = []
    for ep in flat or []:
        try:
            key = (int(ep.get("season_number") or 0), int(ep.get("episode_number") or 0))
        except (TypeError, ValueError):
            continue
        if key[0] >= 1 and key[1] >= 1:
            items.append(key)
    if len(items) < 2 or len({s for s, _ in items}) < 2:
        return []
    return compiler.groups_from_mapping({key: key for key in items})


def _pick_default(candidates: Dict[str, dict], split_bases: list, priority: list) -> str:
    """默认选中哪个依据：按「参照优先级」里第一个既有候选又能拆分的源；
    都不行时退到算法依据（gap / year / finale 里第一个能拆的）。"""
    for key in priority:
        if key in split_bases and key in candidates:
            return key
    if split_bases:
        return split_bases[0]
    for name in ("gap", "year", "finale"):
        item = candidates.get(name)
        if item and len(item["groups"]) > 1:
            return name
    return "whole" if "whole" in candidates else (next(iter(candidates)) if candidates else "")


# ---------------------------------------------------------------------------
# 编译
# ---------------------------------------------------------------------------

def compile_rule(tmdb_id: int, flat: list, groups: list,
                 overrides: Optional[dict] = None, excluded: Optional[list] = None,
                 names: Optional[dict] = None, reference: str = "",
                 title: str = "", use_includes: bool = True,
                 use_absolute: bool = False) -> dict:
    """分组 → 映射表 / 渲染词 / 剧集组 / 逐集明细 / 告警。"""
    names = {int(k): v for k, v in (names or {}).items() if str(k).isdigit()}
    mapping = compiler.mapping_from_groups(groups, flat, overrides, excluded)
    years = compiler.season_years_from_mapping(mapping, flat)
    words = compiler.generate_render_words(tmdb_id, title, reference, mapping, years,
                                           use_includes=use_includes)
    # 连番号折算（开关）：分组仍是 TMDB 原生坐标，这里只往渲染词后面追加一段
    # 「按 TMDB 季边界把 1..N 折回 (s,e)」的规则；映射表 / 剧集组不受影响。
    absolute_rules: list = []
    if use_absolute:
        absolute_rules = compiler.absolute_rule_lines(tmdb_id, flat)
        if absolute_rules:
            words = "\n".join([words, *absolute_rules]) if words else "\n".join(absolute_rules)
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
        "absolute_rules": absolute_rules,
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
    """预览：拉结构 + 取全部参照源 + 出候选分组 + 编译默认方案。不落库。

    参照源不再「按优先级只取第一个」：TVDB / Bangumi / 规则表 能找到的全部返回，
    页面右侧「自动生成」里逐个切换比较；「参照优先级」只决定默认选中哪一个。
    """
    opts = opts or {}
    logs: List[str] = []
    log = _log_collector(logs)
    cfg = _cfg()
    gap_days = int(cfg.get("season_split_gap_days") or DEFAULT_GAP_DAYS)
    gap_mark_days = _cfg_int(cfg, "season_split_gap_mark_days", 21)
    fixed_sizes = [
        int(x) for x in _cfg_list(cfg, "season_split_fixed_sizes", [12, 13])
        if str(x).strip().isdigit()
    ] or [12, 13]
    use_includes = _cfg_bool(cfg, "season_split_use_includes_rules", True)
    use_absolute = _cfg_bool(cfg, "season_split_use_absolute_rules", False)
    priority = opts.get("priority") or _priority(cfg)
    if isinstance(priority, str):
        priority = [x.strip() for x in priority.split(",") if x.strip()]

    log("INFO", f"开始分析 TMDB {tmdb_id}")
    structure = await _fetch_structure(tmdb_id, log)
    tv_show = structure["tv_show"]
    flat = structure["flat"]
    if not flat:
        raise ValueError("TMDB 没有返回任何剧集数据")

    title = tv_show.get("name") or tv_show.get("original_name") or f"TMDB {tmdb_id}"
    structure_hash = _structure_hash(tv_show)
    existing = await store.get_rule(tmdb_id)

    # 编辑已有规则：不再拉 TVDB / Bangumi / 规则表，也不重生成候选
    if opts.get("skip_references"):
        log("INFO", "跳过参照源获取（编辑已有规则，仅载入 TMDB 结构 + 已存分组）")
        compiled = {"mapping": {}, "render_words": "", "group_json": {}, "rows": [], "warnings": []}
        if existing and existing.get("groups"):
            compiled = compile_rule(
                tmdb_id, flat,
                existing.get("groups") or [],
                overrides=existing.get("overrides") or {},
                excluded=existing.get("excluded") or [],
                names=existing.get("names") or {},
                reference=existing.get("reference") or "manual",
                title=title,
                use_includes=use_includes,
                use_absolute=use_absolute,
            )
        return {
            "tmdb_id": tmdb_id,
            "title": title,
            "reference": (existing or {}).get("reference") or "",
            "references": {},
            "need_split": False,
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
            "gaps": grouping.gaps(flat, gap_mark_days),
            "gap_mark_days": gap_mark_days,
            "definition": [],
            "candidates": {},
            "default_basis": "",
            "suggested": compiled,
            "existing_rule": existing,
            "gap_days": gap_days,
            "logs": logs,
        }

    entries = await _collect_references(structure, opts, log)

    split_bases = [
        name for name, entry in entries.items()
        if entry is not None and entry.has_inconsistent(structure["actual_counts"])
    ]
    need_split = bool(split_bases)

    if not entries:
        log("INFO", "未取得任何分季参照（TVDB / Bangumi / 规则表），仅提供算法候选")
    else:
        for name in _REF_ORDER:
            entry = entries.get(name)
            if entry is None:
                continue
            counts = " + ".join(
                str(s.episode_count) for s in sorted(entry.seasons, key=lambda s: s.season_number)
            )
            verdict = "需要拆分" if name in split_bases else "与 TMDB 结构一致"
            log("INFO", f"参照 {name}: {counts} 集 → {verdict}")

    candidates = _candidates(structure, entries, gap_days, fixed_sizes)
    # 「连番号折算」开关开着且确实不需要拆分时，多给一个「TMDB 季边界」候选（恒等分组），
    # 并默认选中它：保存后渲染词里会附带按连番号折算的那一段。
    absolute_groups = _identity_groups(flat) if (use_absolute and not need_split) else []
    if absolute_groups:
        candidates = {
            "tmdb": {"groups": absolute_groups,
                     "warnings": grouping.validate(absolute_groups, flat)},
            **candidates,
        }
        default_basis = "tmdb"
    else:
        default_basis = _pick_default(candidates, split_bases, priority)

    compiled = {"mapping": {}, "render_words": "", "group_json": {}, "rows": [], "warnings": []}
    if default_basis and default_basis in candidates:
        compiled = compile_rule(
            tmdb_id, flat, candidates[default_basis]["groups"],
            reference=default_basis, title=title,
            use_includes=use_includes,
            use_absolute=use_absolute,
        )

    # 分季定义明细：展示默认选中的那个参照源
    definition = []
    definition_source = default_basis if default_basis in entries else next(iter(entries), "")
    entry = entries.get(definition_source)
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

    references = {
        name: {
            "name": item.name or "",
            "split": name in split_bases,
            "seasons": [
                {"season_number": s.season_number, "episode_count": s.episode_count,
                 "name": s.name or f"第 {s.season_number} 季"}
                for s in sorted(item.seasons, key=lambda s: s.season_number)
            ],
        }
        for name, item in entries.items()
        if item is not None
    }

    return {
        "tmdb_id": tmdb_id,
        "title": title,
        "reference": definition_source,
        "references": references,
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
        "gaps": grouping.gaps(flat, gap_mark_days),
        "gap_mark_days": gap_mark_days,
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
    cfg = _cfg()
    use_includes = _cfg_bool(cfg, "season_split_use_includes_rules", True)
    use_absolute = _cfg_bool(cfg, "season_split_use_absolute_rules", False)
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
        use_includes=use_includes,
        use_absolute=use_absolute,
    )
    out.update({"tmdb_id": tmdb_id, "title": title, "logs": logs})
    return out


async def save(payload: dict) -> dict:
    """保存规则：重新编译一次再落库，保证库里的 render_words 与分组一致。"""
    tmdb_id = int(payload["tmdb_id"])
    logs: List[str] = []
    cfg = _cfg()
    use_includes = _cfg_bool(cfg, "season_split_use_includes_rules", True)
    use_absolute = _cfg_bool(cfg, "season_split_use_absolute_rules", False)
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
        use_includes=use_includes,
        use_absolute=use_absolute,
    )
    if not compiled["mapping"]:
        raise ValueError("分组为空，无法保存（至少要有 1 集被覆盖）")

    manual_words = (payload.get("render_words") or "").strip()

    # 来源：显式传入优先；否则沿用库里已有的（启停 / 工作台再编辑不会把「SYTMDB 导入」改成「手动」）；
    # 两者都没有（老数据首次被编辑）时按「手动」记。
    origin = str(payload.get("origin") or "").strip().lower()
    if origin not in store.ORIGINS:
        existing = await store.get_rule(tmdb_id)
        origin = str((existing or {}).get("origin") or "").strip().lower()
    if origin not in store.ORIGINS:
        origin = store.ORIGIN_MANUAL

    record = await store.upsert_rule({
        "tmdb_id": tmdb_id,
        "title": title,
        "status": payload.get("status") or "draft",
        "reference": payload.get("reference") or "manual",
        "origin": origin,
        "groups_json": payload.get("groups") or [],
        "overrides_json": payload.get("overrides") or {},
        "excluded_json": payload.get("excluded") or [],
        "names_json": payload.get("names") or {},
        "mapping_json": compiled["mapping"],
        "group_json": compiled["group_json"],
        "render_words": manual_words or compiled["render_words"],
        "tmdb_hash": _structure_hash(tv_show),
        "episode_total": compiled["episode_total"],
    })
    record["compile"] = compiled
    record["logs"] = logs
    return record


async def _save_absolute_rule(tmdb_id: int, data: dict, cfg: dict) -> Optional[dict]:
    """「无需分季」时，按开关生成一条只做「连番号折算」的规则。

    场景：TMDB 自己就是 S1 12 集 + S2 12 集（`need_split=False`，本来不需要分季），
    但发布侧按「第 1 话…第 24 话」连续编号 → 文件名里的 13 在 TMDB 里不存在，其实是 S2E1。

    - 分组仍用 TMDB 自己的季边界（恒等映射），所以 `mapping_json` / `group_json`
      都是 TMDB 原生坐标，推 SYTMDB 也不会写错；
    - 连番号那段只进渲染词（`use_absolute` 在 compile_rule 里追加）；
    - 开关关闭 / 单季 / 生成不出跨季规则 → 返回 None，调用方继续走原来的黑名单逻辑。
    """
    if not _cfg_bool(cfg, "season_split_use_absolute_rules", False):
        return None
    flat = data.get("episodes") or []
    if not flat:
        return None
    groups = _identity_groups(flat)
    if not groups:
        return None          # 单季：连番号与 TMDB 坐标一致，没有可折算的边界
    if not compiler.absolute_rule_lines(tmdb_id, flat):
        return None          # 两季边界一致时不会产生规则，不必落库

    record = await save({
        "tmdb_id": tmdb_id,
        "groups": groups,
        "overrides": {},
        "excluded": [],
        "names": {},
        "reference": "tmdb",
        "status": "active",
        "origin": store.ORIGIN_AUTO,
    })
    record["absolute"] = True
    return record


async def auto_generate_rule(tmdb_id: int, entry: str = "organize") -> Optional[dict]:
    """识别链路调用：满足条件时自动生成并保存一条 active 分季规则。

    生成条件（全部满足才生成）：
    - season_split_auto_generate 开关开启
    - season_split_mode == on
    - season_split_scope 允许当前 entry
    - 不在番剧黑名单
    - 库里还没有该番的规则
    - 参照门槛通过，且确实「需要拆分」（TVDB / Bangumi / 规则表 与 TMDB 结构不一致）

    生成依据与页面「生成方案」默认选中一致（参照优先级），保存后立即重载内存快照，
    由调用方把返回的 render_words 追加进本次识别的渲染词列表，做到当场生效。

    判定「无需拆分」时：
    - `season_split_use_absolute_rules` 开着 → 尝试生成「连番号折算」规则（见
      `_save_absolute_rule`），成功就返回（不拉黑、不写剧集组）；生成不出来才继续往下；
    - 否则返回 {"blacklisted": True} 并加入黑名单（持久化），之后不再重复拉参照源。
    """
    cfg = _cfg()
    if not _cfg_bool(cfg, "season_split_auto_generate", False):
        return None
    if str(cfg.get("season_split_mode") or "off").strip().lower() != "on":
        return None
    scope = cfg.get("season_split_scope") or {}
    if isinstance(scope, dict) and scope and not scope.get(entry, True):
        return None

    tmdb_id = int(tmdb_id)

    blocked = set()
    for item in cfg.get("season_split_blacklist") or []:
        try:
            blocked.add(int(item))
        except (TypeError, ValueError):
            continue
    if tmdb_id in blocked:
        return None

    if await store.get_rule(tmdb_id):
        return None

    data = await preview(tmdb_id)
    if not data.get("need_split"):
        absolute = await _save_absolute_rule(tmdb_id, data, cfg)
        if absolute:
            return absolute

        from config_manager import ConfigManager

        blacklist = list(cfg.get("season_split_blacklist") or [])
        if tmdb_id not in blacklist:
            blacklist.append(tmdb_id)
            ConfigManager.update_config({"season_split_blacklist": blacklist})
        return {"blacklisted": True, "tmdb_id": tmdb_id}

    basis = data.get("default_basis") or ""
    groups = ((data.get("candidates") or {}).get(basis) or {}).get("groups") or []
    if not groups:
        return None

    record = await save({
        "tmdb_id": tmdb_id,
        "groups": groups,
        "reference": basis or "tvdb",
        "status": "active",
        "origin": store.ORIGIN_AUTO,
    })

    # 可选：自动写入 SYTMDB 剧集组（闭环；写入失败不中断识别）
    pushed = False
    push_error = ""
    if _cfg_bool(cfg, "season_split_auto_push_sytmdb", False):
        try:
            await push_episode_group(tmdb_id)
            pushed = True
        except Exception as e:
            push_error = str(e)
    record["pushed_sytmdb"] = pushed
    record["push_error"] = push_error
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
    """剧集组写回地址。补全逻辑与读取侧一致（sytmdb_source.base_url），
    避免「ip:8121」被拼成 ip:8121:8121。"""
    return f"{sytmdb_source.base_url(addr)}/api/tv/{tmdb_id}/episodegroup"


# ---------------------------------------------------------------------------
# SYTMDB 一键导入（直接吃那边的剧集组，不拿 TMDB 重新生成）
# ---------------------------------------------------------------------------

def _sytmdb_conn() -> tuple[str, str]:
    cfg = _cfg()
    return (cfg.get("sytmdb_host") or "").strip(), (cfg.get("sytmdb_token") or "").strip()


async def sytmdb_candidates() -> dict:
    """列出 SYTMDB 里所有「带剧集组」的番，并标注是否已有规则 / 会不会改动季号。"""
    addr, token = _sytmdb_conn()
    if not addr:
        raise ValueError("未配置 SYTMDB 地址（系统设置 → SYTMDB）")

    rows, scanned, errors = await sytmdb_source.collect_candidates(addr, token)
    existing = {int(r["tmdb_id"]): r for r in await store.list_rules()}
    for row in rows:
        rule = existing.get(int(row["tmdb_id"])) or {}
        row["existing"] = bool(rule)
        row["existing_status"] = rule.get("status") or ""
        row["existing_reference"] = rule.get("reference") or ""
        row["existing_origin"] = rule.get("origin") or ""
    # 会改动季号的排前面，其次是没有规则的，再按年份倒序
    rows.sort(key=lambda r: (
        not r["will_change"], not r["existing"], -int(r.get("year") or 0), r["title"]
    ))
    return {
        "source": addr,
        "scanned": scanned,
        "matched": len(rows),
        "importable": sum(1 for r in rows if r["will_change"]),
        "existing": sum(1 for r in rows if r["existing"]),
        "specials": sum(1 for r in rows if r.get("specials")),
        "errors": errors,
        "items": rows,
    }


async def sytmdb_import(tmdb_ids: Optional[List[int]] = None, status: str = "active",
                        overwrite: bool = False) -> dict:
    """把 SYTMDB 的剧集组直接落成规则库条目（不经过 TMDB 重新生成）。

    - ``tmdb_ids`` 为空 = 导入全部「会改动季号」的条目
    - ``overwrite`` False 时跳过库中已存在的番
    - 每条规则同时写入 mapping / group_json / render_words，写完统一 reload 一次
    """
    addr, token = _sytmdb_conn()
    if not addr:
        raise ValueError("未配置 SYTMDB 地址（系统设置 → SYTMDB）")
    if status not in ("draft", "active", "disabled"):
        status = "active"

    rows, scanned, errors = await sytmdb_source.collect_candidates(addr, token)
    meta = {int(r["tmdb_id"]): r for r in rows}
    if tmdb_ids:
        ids = [int(x) for x in tmdb_ids if int(x) in meta]
        missing = [int(x) for x in tmdb_ids if int(x) not in meta]
    else:
        ids = [tid for tid, row in meta.items() if row["will_change"]]
        missing = []

    existing = {int(r["tmdb_id"]): r for r in await store.list_rules()}
    sem = asyncio.Semaphore(8)
    imported = 0
    skipped: List[dict] = [{"tmdb_id": tid, "reason": "SYTMDB 里没有这部剧集组"} for tid in missing]
    failed: List[dict] = []
    items: List[dict] = []

    async def build_one(tmdb_id: int) -> Optional[dict]:
        if tmdb_id in existing and not overwrite:
            skipped.append({"tmdb_id": tmdb_id, "reason": "规则库里已有该番"})
            return None
        row_meta = meta[tmdb_id]
        if not row_meta.get("will_change"):
            skipped.append({"tmdb_id": tmdb_id, "reason": "与 TMDB 原生季结构一致，无需导入"})
            return None
        try:
            async with sem:
                raw = await sytmdb_source.fetch_episode_group(addr, token, tmdb_id)
            built = sytmdb_source.build_rule(
                {"id": tmdb_id, "name": row_meta["title"], "year": row_meta.get("year"),
                 "source": row_meta.get("source")},
                raw, status,
            )
        except Exception as e:
            failed.append({"tmdb_id": tmdb_id, "error": str(e)})
            return None
        try:
            await store.upsert_rule(built["payload"], reload_cache=False)
        except Exception as e:
            failed.append({"tmdb_id": tmdb_id, "error": f"写库失败: {e}"})
            return None
        return built["stats"]

    for stats in await asyncio.gather(*[build_one(tid) for tid in ids]):
        if stats:
            imported += 1
            items.append(stats)

    if imported:
        await store.reload()

    return {
        "imported": imported,
        "skipped": skipped,
        "failed": failed,
        "items": items,
        "scanned": scanned,
        "fetch_errors": errors,
        "cache": store.cache_stats(),
    }


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
        "use_source": bool(cfg.get("season_split_use_source")),
        "force_reference": bool(cfg.get("season_split_force_reference")),
        "auto_generate": bool(cfg.get("season_split_auto_generate")),
        "auto_push_sytmdb": bool(cfg.get("season_split_auto_push_sytmdb")),
        "source": cfg.get("season_split_source") or "",
        "gap_days": cfg.get("season_split_gap_days") or DEFAULT_GAP_DAYS,
        "ref_genre_ids": _cfg_list(cfg, "season_split_ref_genre_ids", [16]),
        "ref_countries": _cfg_list(cfg, "season_split_ref_countries", ["JP"]),
        "ref_season_min": _cfg_int(cfg, "season_split_ref_season_min", 1),
        "ref_season_max": _cfg_int(cfg, "season_split_ref_season_max", 2),
        "fixed_sizes": _cfg_list(cfg, "season_split_fixed_sizes", [12, 13]),
        "gap_mark_days": _cfg_int(cfg, "season_split_gap_mark_days", 21),
        "use_includes_rules": bool(cfg.get("season_split_use_includes_rules", True)),
        "use_absolute_rules": bool(cfg.get("season_split_use_absolute_rules", False)),
        "tvdb_key_configured": bool((cfg.get("tvdb_api_key") or "").strip()),
        "cache": store.cache_stats(),
    }


def settings_update(payload: dict) -> dict:
    from config_manager import ConfigManager

    allowed = {
        "season_split_mode", "season_split_scope", "season_split_blacklist",
        "season_split_exclude_patterns", "season_split_priority", "season_split_source",
        "season_split_gap_days", "season_split_use_source", "season_split_force_reference",
        "season_split_auto_generate", "season_split_auto_push_sytmdb",
        "season_split_ref_genre_ids", "season_split_ref_countries",
        "season_split_ref_season_min", "season_split_ref_season_max",
        "season_split_fixed_sizes", "season_split_gap_mark_days",
        "season_split_use_includes_rules",
        "season_split_use_absolute_rules",
        "tvdb_api_key",
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


async def blacklist_meta() -> dict:
    """给黑名单里的 tmdb_id 补全名称 / 年份 / 海报（读项目内永久缓存 + 数据中心元数据资产）。

    数据统一来自 MetaCacheManager（TmdbDeepMeta 超级表），即本地永久缓存与
    数据中心离线档案的合并结果；不联网。tv 查不到再回退 movie。
    """
    cfg = _cfg()
    ids: List[int] = []
    for item in cfg.get("season_split_blacklist") or []:
        try:
            ids.append(int(item))
        except (TypeError, ValueError):
            continue

    from metadata.meta_cache import MetaCacheManager

    items: List[dict] = []
    for tmdb_id in ids:
        meta = await MetaCacheManager.get(f"tv:{tmdb_id}")
        if not meta:
            meta = await MetaCacheManager.get(f"movie:{tmdb_id}")
        m = meta or {}
        year = m.get("year") or ""
        items.append({
            "tmdb_id": tmdb_id,
            "title": m.get("title") or m.get("name") or "",
            "year": str(year)[:4] if year else None,
            "poster_path": m.get("poster_path") or "",
            "is_custom": bool(m.get("is_custom")),
            "source": "data_center" if meta else None,
            "has_meta": bool(meta),
        })
    return {"items": items}
