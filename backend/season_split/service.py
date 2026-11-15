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
    # 只在「分组是恒等映射」时追加——需要拆分的番（合并季）不该混进连番号规则。
    absolute_rules: list = []
    if use_absolute and mapping and all(src == dst for src, dst in mapping.items()):
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
    existing = await store.get_rule(tmdb_id)

    # 来源：显式传入优先；否则沿用库里已有的（启停 / 工作台再编辑不会把「SYTMDB 导入」改成「手动」）；
    # 两者都没有（老数据首次被编辑）时按「手动」记。
    origin = str(payload.get("origin") or "").strip().lower()
    if origin not in store.ORIGINS:
        origin = str((existing or {}).get("origin") or "").strip().lower()
    if origin not in store.ORIGINS:
        origin = store.ORIGIN_MANUAL

    # 工作台改动了自动规则的分组 → 这条改由用户维护：来源改成「手动」，
    # 之后 TMDB 结构变化时不会被自动重排覆盖。只切启停、内容没变则仍是「自动」。
    if (origin == store.ORIGIN_AUTO
            and not str(payload.get("origin") or "").strip()
            and existing
            and _rule_content_changed(payload, existing)):
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
        "structure_fp": _fp_text(_seasons_fingerprint(tv_show.get("seasons"))),
        "episode_total": compiled["episode_total"],
    })
    # 建/存规则 = 明确「这部要分季」：顺手把它从黑名单里移出来（手动条目也移）。
    record["blacklist_released"] = bool(await store.delete_blacklist(tmdb_id))
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


# ---------------------------------------------------------------------------
# 番剧黑名单（public.season_split_blacklist，一部番一条）
#
# origin = manual（人加的，只有人能删）/ auto（判定加的，带判定记录）。
# 自动条目在 reason / decided_at / seasons_fp / use_absolute 里记一份「当时凭什么判定」：
# 原因、入榜时间、TMDB 季表指纹、当时的「连番号折算」开关。
# 之后每次识别到这部番都会拿当前季表/开关免费比一次（纯比较，不联网）：
# 前提变了就解除黑名单并重新判定，前提没变则什么都不做。
#
# 读路径只看 store 的内存快照（`store.is_blocked` / `store.blocked_ids`），
# 写路径走单行 CRUD —— 不再整表重写 config.json。
# ---------------------------------------------------------------------------

BLACKLIST_REASON_SINGLE_SHORT = "single-season-short"
BLACKLIST_REASON_NO_SPLIT = "no-split"
BLACKLIST_REASON_LABELS = {
    BLACKLIST_REASON_SINGLE_SHORT: "TMDB 单季且集数 < 15",
    BLACKLIST_REASON_NO_SPLIT: "判定无需拆分",
}


def _seasons_fingerprint(seasons: Any) -> Optional[List[List[int]]]:
    """季表指纹：`[[季号, 集数], ...]`，只看 S1 起的正片季；拿不到季表返回 None。

    只取「季号 + 集数」两项——季名、首播日这些不影响「要不要分季」，
    带进来只会让判定无谓地反复失效。
    """
    rows: List[List[int]] = []
    for item in seasons or []:
        if not isinstance(item, dict):
            continue
        try:
            number = int(item.get("season_number"))
        except (TypeError, ValueError):
            continue
        if number < 1:
            continue
        try:
            count = int(item.get("episode_count") or 0)
        except (TypeError, ValueError):
            count = 0
        rows.append([number, count])
    if not rows:
        return None
    rows.sort()
    return rows


def _fp_counts(text: str) -> List[int]:
    """`1:12,2:12` → [12, 12]（只给人话说明用）。"""
    counts: List[int] = []
    for part in str(text or "").split(","):
        _, _, count = part.partition(":")
        count = count.strip()
        if count.isdigit():
            counts.append(int(count))
    return counts


def _blacklist_release_reason(cfg: dict, tmdb_id: int, seasons: Any) -> str:
    """自动条目该不该解除？返回原因代码，`""` = 不动。纯比较：不联网、不写库、不读库。

    - 「单季且集数<15」：前提就是季表本身，每次识别都能免费复算；
    - 「判定无需拆分」：结论依赖 TVDB / Bangumi，重算要联网，所以比落库的指纹
      （季表 + 当时的连番号折算开关），前提没变就不重拉参照源；
    - 手动 / 没有判定记录 / 原因不明：永远返回 ""（只有人能删）。

    判定记录来自 store 的内存快照（`store.get_blocked_row`），所以识别链路每遇到
    一部已拉黑的番也只多一次字典查询，不会为它多打一次数据库。
    """
    tmdb_id = int(tmdb_id)
    entry = store.get_blocked_row(tmdb_id)
    if not entry or entry.get("origin") != store.ORIGIN_AUTO:
        return ""
    reason = str(entry.get("reason") or "")
    current_fp = _fp_text(_seasons_fingerprint(seasons))
    if reason == BLACKLIST_REASON_SINGLE_SHORT:
        if not current_fp:
            return ""          # 没有季表判断不了，保守不动
        if grouping.single_season_too_short(seasons):
            return ""          # 前提仍成立
        return reason
    if reason == BLACKLIST_REASON_NO_SPLIT:
        if not current_fp:
            return ""
        stored_fp = str(entry.get("seasons_fp") or "")
        if not stored_fp:
            return ""          # 没有落库指纹，保守不动
        use_absolute_now = _cfg_bool(cfg, "season_split_use_absolute_rules", False)
        if current_fp == stored_fp and bool(entry.get("use_absolute")) == use_absolute_now:
            return ""
        return reason
    return ""


async def release_blacklist_if_stale(cfg: dict, tmdb_id: int, seasons: Any) -> Optional[dict]:
    """识别链路调用：前提变了就解除自动条目，返回被解除的条目；没解除返回 None。"""
    reason = _blacklist_release_reason(cfg, tmdb_id, seasons)
    if not reason:
        return None
    removed = await store.delete_blacklist(tmdb_id) or {"tmdb_id": int(tmdb_id)}
    removed["released"] = True
    removed["released_reason"] = reason
    return removed


async def _add_to_blacklist(tmdb_id: int, reason: str = "",
                            seasons: Any = None, use_absolute: bool = False,
                            manual: bool = False) -> None:
    """把该番加入分季黑名单（单行落库）。

    `manual=True` 只落 origin=manual、不写判定记录：人工条目永远不会被自动解除
    （「重新评估」后仍无需分季时也按手动放回，避免它又变成能被自动解除的条目）。
    """
    if manual:
        await store.upsert_blacklist(int(tmdb_id), origin=store.ORIGIN_MANUAL)
        return
    await store.upsert_blacklist(
        int(tmdb_id),
        origin=store.ORIGIN_AUTO,
        reason=reason or "",
        decided_at=datetime.now(),
        seasons_fp=_fp_text(_seasons_fingerprint(seasons)),
        use_absolute=bool(use_absolute),
    )


def _blacklist_reason_text(entry: dict) -> str:
    """判定原因的人话说明（带当时的结构，方便回头判断该不该留）。"""
    if not entry:
        return ""
    reason = str(entry.get("reason") or "")
    label = BLACKLIST_REASON_LABELS.get(reason, "原因未知")
    counts = _fp_counts(entry.get("seasons_fp"))
    if counts:
        return f"{label}（当时 {' + '.join(str(count) for count in counts)} 集）"
    return label


# ---------------------------------------------------------------------------
# 自动规则的结构自愈
#
# 自动生成的分季规则只代表「保存那一刻的 TMDB 结构」。之后 TMDB 加了季 / 改了集数，
# 旧规则的映射就会错位。这里给它记一份季表指纹（`structure_fp`，形如 `1:12,2:12`），
# 识别链路每次免费比一次：结构变了才重排（等于「删掉再自动生成」，但自动完成）。
# 手动 / SYTMDB 导入 / 历史来源的规则一律不动 —— 那是用户或外部源维护的内容。
# ---------------------------------------------------------------------------

def _fp_text(fp: Optional[List[List[int]]]) -> str:
    """季表指纹的紧凑文本（落库 / 比较用）：`1:12,2:12`。"""
    return ",".join(f"{number}:{count}" for number, count in (fp or []))


def _fp_text_from_mapping(mapping: Any) -> str:
    """老规则没有 `structure_fp` 时，从 `mapping_json` 反推当时的结构。

    mapping 的 key 是原始季号、value 是「集号 → 目标坐标」，所以 key 的数量就是
    当时那一季的集数。反推值可能比 TMDB 少（去重 / 排除过的集），第一次比对若判成
    「变了」就会重排一次，重排后存的是真实季表指纹，之后不会再抖。
    """
    if not isinstance(mapping, dict):
        return ""
    counts: Dict[int, int] = {}
    for season_key, episodes in mapping.items():
        try:
            number = int(season_key)
        except (TypeError, ValueError):
            continue
        if number < 1 or not isinstance(episodes, dict):
            continue
        counts[number] = len(episodes)
    if not counts:
        return ""
    return ",".join(f"{number}:{counts[number]}" for number in sorted(counts))


def _rule_structure_fp(rule: dict) -> str:
    """规则保存时的结构指纹；没有就回退从 mapping 反推。"""
    stored = str((rule or {}).get("structure_fp") or "").strip()
    return stored or _fp_text_from_mapping((rule or {}).get("mapping"))


def _json_key(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)


def _rule_content_changed(payload: dict, existing: dict) -> bool:
    """工作台这次保存有没有改动规则内容（只切启停 / 只重存不算）。"""
    for field, default in (("groups", []), ("overrides", {}),
                           ("excluded", []), ("names", {})):
        current = payload.get(field)
        current = default if current is None else current
        if _json_key(current) != _json_key((existing or {}).get(field) or default):
            return True
    reference = str(payload.get("reference") or "").strip()
    if reference and reference != str((existing or {}).get("reference") or "").strip():
        return True
    words = (payload.get("render_words") or "").strip()
    if words and words != str((existing or {}).get("render_words") or "").strip():
        return True
    return False


def _auto_rule_needs_refresh(rule: dict, seasons: Any) -> bool:
    """系统托管的自动规则，TMDB 结构变了没有？纯比较，不联网。

    - 只认「自动生成 + 生效中」：手动 / SYTMDB / 历史规则永远 False；
    - 没有季表、或规则连指纹都推不出来 → False（保守不动）。
    """
    if str((rule or {}).get("origin") or "") != store.ORIGIN_AUTO:
        return False
    if str((rule or {}).get("status") or "") != "active":
        return False
    current = _fp_text(_seasons_fingerprint(seasons))
    if not current:
        return False
    stored = _rule_structure_fp(rule)
    if not stored:
        return False
    return current != stored


async def auto_generate_rule(tmdb_id: int, entry: str = "organize",
                             seasons: Optional[list] = None,
                             force: bool = False,
                             manual_readd: bool = False) -> Optional[dict]:
    """识别链路调用：满足条件时自动生成并保存一条 active 分季规则。

    生成条件（全部满足才生成）：
    - season_split_auto_generate 开关开启（`force=True` 时跳过：页面点「重新评估」）
    - season_split_mode == on（同上）
    - season_split_scope 允许当前 entry（同上）
    - 不在番剧黑名单
    - 库里还没有该番的规则
    - 参照门槛通过，且确实「需要拆分」（TVDB / Bangumi / 规则表 与 TMDB 结构不一致）

    生成依据与页面「生成方案」默认选中一致（参照优先级），保存后立即重载内存快照，
    由调用方把返回的 render_words 追加进本次识别的渲染词列表，做到当场生效。

    判定「无需拆分」时：
    - `season_split_use_absolute_rules` 开着 → 尝试生成「连番号折算」规则（见
      `_save_absolute_rule`），成功就返回（不拉黑、不写剧集组）；生成不出来才继续往下；
    - 否则返回 {"blacklisted": True} 并加入黑名单（持久化），之后不再重复拉参照源。

    `seasons`（可选，识别链路传 ctx.tmdb_data["seasons"]）用于两件事：
    - **快速拉黑**：TMDB 只有一季且集数 < `SINGLE_SEASON_BLACKLIST_MAX` 时，既拆不出
      两季也没有跨季边界，直接进黑名单，省掉一次 TVDB / Bangumi 拉取；
    - **自动解除**：自动条目的判定前提（季表 / 折算开关）变了就先解除黑名单，再重新
      判定一次。纯比较，不额外联网。

    `force` / `manual_readd` 只给页面「重新评估」用：前者不看开关，后者表示重判后
    仍无需分季时按「手动条目」放回名单（不会被自动解除）。
    """
    tmdb_id = int(tmdb_id)
    cfg = _cfg()

    # 先做「前提变了就解除」：不管开关是否开启都执行——这是纯状态修正，不联网。
    released = await release_blacklist_if_stale(cfg, tmdb_id, seasons)

    if not force:
        if not _cfg_bool(cfg, "season_split_auto_generate", False):
            return None
        if str(cfg.get("season_split_mode") or "off").strip().lower() != "on":
            return None
        scope = cfg.get("season_split_scope") or {}
        if isinstance(scope, dict) and scope and not scope.get(entry, True):
            return None
        if store.is_blocked(tmdb_id):
            return None

    rule = await store.get_rule(tmdb_id)
    if rule:
        if force:
            return {"existing_rule": True, "released": bool(released)}
        if not _auto_rule_needs_refresh(rule, seasons):
            return None
        # 系统托管的自动规则结构过期了：按最新结构重排（见 _refresh_auto_rule）
        return await _refresh_auto_rule(tmdb_id, cfg, seasons)

    use_absolute = _cfg_bool(cfg, "season_split_use_absolute_rules", False)

    # 快速拉黑：TMDB 单季 + 集数很少 → 怎么处理都一样，不必再拉参照源。
    if grouping.single_season_too_short(seasons):
        await _add_to_blacklist(tmdb_id, BLACKLIST_REASON_SINGLE_SHORT,
                                seasons=seasons, use_absolute=use_absolute,
                                manual=manual_readd)
        return {"blacklisted": True, "tmdb_id": tmdb_id,
                "reason": BLACKLIST_REASON_SINGLE_SHORT}

    data = await preview(tmdb_id)
    if not data.get("need_split"):
        absolute = await _save_absolute_rule(tmdb_id, data, cfg)
        if absolute:
            return absolute

        await _add_to_blacklist(tmdb_id, BLACKLIST_REASON_NO_SPLIT,
                                seasons=seasons or (data.get("tmdb") or {}).get("seasons"),
                                use_absolute=use_absolute,
                                manual=manual_readd)
        return {"blacklisted": True, "tmdb_id": tmdb_id,
                "reason": BLACKLIST_REASON_NO_SPLIT}

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
    return await _auto_push_if_enabled(cfg, tmdb_id, record)


async def _auto_push_if_enabled(cfg: dict, tmdb_id: int, record: dict) -> dict:
    """自动生成/重排后按开关顺带写 SYTMDB 剧集组（失败不中断识别）。"""
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


async def _refresh_auto_rule(tmdb_id: int, cfg: dict,
                             seasons: Any = None) -> Optional[dict]:
    """自动规则的结构过期了：按最新结构重排一次（等于「删掉再自动生成」）。

    - 仍需要拆分 → 覆盖保存（origin 仍是 auto，渲染词当场生效）；
    - 不再需要拆分 → 能出「连番号折算」就换成折算规则，否则删掉这条过期规则并进黑名单；
    - 拉不到参照源 / 算不出分组 → 返回 None，保留旧规则（别把还能用的删了）。
    """
    data = await preview(tmdb_id)
    use_absolute = _cfg_bool(cfg, "season_split_use_absolute_rules", False)

    if not data.get("need_split"):
        absolute = await _save_absolute_rule(tmdb_id, data, cfg)
        if absolute:
            absolute["refreshed"] = True
            return absolute
        await store.delete_rule(tmdb_id)   # 过期规则留着只会错配集号，删掉再拉黑
        await _add_to_blacklist(tmdb_id, BLACKLIST_REASON_NO_SPLIT,
                                seasons=seasons or (data.get("tmdb") or {}).get("seasons"),
                                use_absolute=use_absolute)
        return {"blacklisted": True, "tmdb_id": tmdb_id,
                "reason": BLACKLIST_REASON_NO_SPLIT, "refreshed": True}

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
    record["refreshed"] = True
    return await _auto_push_if_enabled(cfg, tmdb_id, record)


async def recheck_blacklist(tmdb_id: int) -> dict:
    """手动「重新评估」：当场按自动流程重判一次，并给出人话结论。

    与识别链路的区别：不看「自动生成规则」开关 / 模式 / scope —— 用户点了按钮就是
    明确意图；但「连番号折算」这类行为偏好照旧尊重（开关关着就不生成）。
    重判结论仍是「不需要分季」时：自动条目按自动条目放回（带走新指纹），手动条目
    按手动条目放回（之后不会被自动解除）。
    """
    tmdb_id = int(tmdb_id)
    if not store.is_blocked(tmdb_id):
        raise ValueError("该番不在黑名单中")

    entry = await store.get_blacklist_entry(tmdb_id)
    was_auto = bool(entry and entry.get("origin") == store.ORIGIN_AUTO)

    record = await auto_generate_rule(
        tmdb_id, entry="organize", seasons=None,
        force=True, manual_readd=not was_auto,
    )

    if record and record.get("blacklisted"):
        action = "blacklisted"
        message = ("仍判定不需要分季，已留在黑名单" if was_auto
                   else "仍判定不需要分季，已按手动条目留在黑名单")
    elif record and record.get("absolute"):
        action = "absolute"
        message = "无需分季，已生成「连番号折算」规则并启用"
    elif record and record.get("existing_rule"):
        action = "existing_rule"
        message = "该番已有分季规则，已移出黑名单"
    elif record:
        action = "split"
        message = f"需要分季，已生成并启用规则（依据 {record.get('reference') or '-'}）"
    else:
        action = "released"
        message = "已移出黑名单；这次没生成出规则，下次识别会再判定"

    if action != "blacklisted":
        # 重判结果不是「留在黑名单」→ 名单里这条彻底删掉（含判定记录）。
        await store.delete_blacklist(tmdb_id)

    return {
        "tmdb_id": tmdb_id,
        "released": action != "blacklisted",
        "was_auto": was_auto,
        "action": action,
        "message": message,
    }


async def blacklist_add_manual(tmdb_id: int) -> dict:
    """手动加入黑名单：用户显式操作 → 不写判定记录，永远不会被自动解除。"""
    await _add_to_blacklist(int(tmdb_id), manual=True)
    return await blacklist_meta()


async def blacklist_remove(tmdb_id: int) -> dict:
    """移出黑名单（手动 / 自动都移），返回最新列表。"""
    await store.delete_blacklist(int(tmdb_id))
    return await blacklist_meta()


async def push_episode_group(tmdb_id: int) -> dict:
    """把规则里的剧集组写入 SYTMDB（先探活，404 则创建，再整体覆盖）。"""
    rule = await store.get_rule(tmdb_id)
    if not rule:
        raise ValueError("该番还没有保存过分季规则")
    if (rule.get("reference") or "") == "tmdb":
        # 连番号折算的源坐标（1..N）不在 TMDB 里，推上去会让 Emby 把 S1E13 当成第 2 季
        raise ValueError("连番号折算规则只写渲染词，不写剧集组")
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
        # 黑名单存 PG 表，这里只给内存快照的 ID 列表（前端用于「是否已在名单里」的判断）
        "blacklist": store.blocked_ids(),
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

    payload = payload or {}
    if "season_split_blacklist" in payload:
        # 名单已经是独立的表，整表覆盖会悄无声息地删掉别人刚加进来的条目，所以直接拒绝：
        # 增删请走 POST /season-split/blacklist 和 DELETE /season-split/blacklist/{id}。
        raise ValueError(
            "黑名单已改为独立数据表，不再通过设置接口修改；"
            "请用 POST /season-split/blacklist 或 DELETE /season-split/blacklist/{tmdb_id}"
        )

    allowed = {
        "season_split_mode", "season_split_scope",
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
    patch = {k: v for k, v in payload.items() if k in allowed}
    if "season_split_mode" in patch:
        mode = str(patch["season_split_mode"]).lower()
        if mode not in ("off", "preview", "on"):
            raise ValueError("season_split_mode 只能是 off / preview / on")
        patch["season_split_mode"] = mode
    if patch:
        ConfigManager.update_config(patch)
    return settings_snapshot()


async def blacklist_meta() -> dict:
    """给黑名单补全名称 / 年份 + 判定来源（读项目内永久缓存 + 数据中心元数据资产）。

    名单本身从 PG 表 `public.season_split_blacklist` 读；名称 / 年份来自
    MetaCacheManager（TmdbDeepMeta 超级表），即本地永久缓存与数据中心离线档案的
    合并结果；不联网。tv 查不到再回退 movie。
    不返回 poster_path：黑名单只是维护 ID 的清单，前端也不再渲染海报。
    自动条目额外带上 reason / reason_label / at，供页面解释「为什么在、什么时候进的」。
    """
    rows = await store.list_blacklist()

    from metadata.meta_cache import MetaCacheManager

    items: List[dict] = []
    for row in rows:
        tmdb_id = int(row["tmdb_id"])
        meta = await MetaCacheManager.get(f"tv:{tmdb_id}")
        if not meta:
            meta = await MetaCacheManager.get(f"movie:{tmdb_id}")
        m = meta or {}
        year = m.get("year") or ""
        is_auto = row.get("origin") == store.ORIGIN_AUTO
        items.append({
            "tmdb_id": tmdb_id,
            "title": m.get("title") or m.get("name") or "",
            "year": str(year)[:4] if year else None,
            "is_custom": bool(m.get("is_custom")),
            "source": "data_center" if meta else None,
            "has_meta": bool(meta),
            "auto": is_auto,
            "reason": str(row.get("reason") or ""),
            "reason_label": _blacklist_reason_text(row) if is_auto else "",
            "at": row.get("decided_at") or None,
        })
    return {"items": items}
