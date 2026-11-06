# -*- coding: utf-8 -*-
"""番剧分季拆分 · 编译器（纯函数，无 I/O）。

职责：把「分组定义」编译成运行时真正要用的三样东西
  1. 逐集映射表   mapping: {(原始季, 原始集): (虚拟季, 虚拟集)}
  2. 渲染词文本   `@?{[tmdbid=..;type=tv;e=a-b]} => {[s=VS;e=EP-off]}`（由现有 RenderEngine 执行）
  3. 剧集组 JSON  写 SYTMDB / Emby 显示用

`generate_render_words` / `includes_rule_lines` / `logic_to_group_json` /
`build_finale_groups` / `groups_to_group_json` / `generate_group_render_words`
移植自 Lens `cure_splitter/splitter.py`，**分段与偏移逻辑一行未改**。
"""

from __future__ import annotations

import json
import re
from datetime import date as _date
from typing import Optional

from .splitter import first_air_year


# ---------------------------------------------------------------------------
# 渲染词生成（移植 Lens，逻辑不变）
# ---------------------------------------------------------------------------

def includes_rule_lines(tmdb_id: int, season_years: dict) -> list:
    """按虚拟季首播年份生成 includes 条件规则行。

    同一年份对应多个虚拟季时仅凭 includes 无法消歧，跳过并注释说明。

    注意：本项目 RenderEngine 的 `includes=` 是对**原始文件名**做包含匹配
    （比依赖 meta.year 更稳：文件名里没写年份就不命中，自动退回季号校准结果），
    所以这里保持 Lens 原样的 `includes={年份}` 写法，不要改成 `year=`。
    """
    by_year: dict = {}
    for season_number in sorted(season_years):
        by_year.setdefault(int(season_years[season_number]), []).append(season_number)
    lines: list = []
    for year in sorted(by_year):
        seasons = by_year[year]
        if len(seasons) > 1:
            names = ",".join(f"S{s}" for s in seasons)
            lines.append(f"# 注意: 年份 {year} 对应多个虚拟季({names})，未生成 includes 规则")
            continue
        lines.append(f"@?{{[tmdbid={tmdb_id};type=tv;includes={year}]}} => {{[s={seasons[0]}]}}")
    return lines


def generate_render_words(tmdb_id: int, title: str, reference: str, org_map: dict,
                          season_years: Optional[dict] = None,
                          use_includes: bool = True) -> str:
    """把逐集映射转换为渲染词(专家规则)文本块，含来源注释头。

    条件默认不带季号(s=)：文件名里的季前缀不可靠（存在 S2E25 这类
    "季号 + 续位集号"的命名），以集号作为绝对定位依据。
    若不同原始季产生的集号区间重叠且目标不同（仅凭集号无法消歧），
    冲突段自动保留季限定并在注释中说明。

    season_years: 虚拟季号 → 首播年份；提供时按年份追加 includes 条件规则。
    """
    per_orig: dict = {}
    for (orig_s, orig_e), (virt_s, virt_e) in org_map.items():
        if not isinstance(orig_s, int) or orig_s < 1:
            continue  # S0 / 电影条目无法用季集条件表达
        if not isinstance(orig_e, int) or orig_e < 1:
            continue
        per_orig.setdefault(orig_s, {})[orig_e] = (virt_s, virt_e)

    segments: list = []  # 需要生成规则的偏移段 (orig_s, a, b, virt_s, offset)
    claims: list = []    # 全部区间占用（含无偏移段），用于冲突检测

    for orig_s in sorted(per_orig):
        entries = sorted(per_orig[orig_s].items())

        def flush(orig_s: int, seg: list) -> None:
            if not seg:
                return
            a, b = seg[0][0], seg[-1][0]
            virt_s, virt_a = seg[0][1]
            offset = a - virt_a
            claims.append((orig_s, a, b, virt_s, offset))
            if virt_s == orig_s and offset == 0:
                return  # 无偏移:不生成规则,但区间已被原始季占用
            segments.append((orig_s, a, b, virt_s, offset))

        seg: list = []
        prev = None
        for oe, target in entries:
            if (prev is not None and oe == prev[0] + 1
                    and target[0] == prev[1][0]
                    and (oe - target[1]) == (prev[0] - prev[1][1])):
                seg.append((oe, target))
            else:
                flush(orig_s, seg)
                seg = [(oe, target)]
            prev = (oe, target)
        flush(orig_s, seg)

    rules: list = []
    ambiguous_any = False
    for seg in segments:
        os_, a, b, vs, off = seg
        # 与任何其他占用区间重叠且目标不同 → 仅凭集号无法消歧,保留季限定
        ambiguous = any(
            other != seg and not (b < other[1] or other[2] < a)
            and (vs, off) != (other[3], other[4])
            for other in claims
        )
        ambiguous_any = ambiguous_any or ambiguous
        cond = f"tmdbid={tmdb_id};type=tv;"
        if ambiguous:
            cond += f"s={os_};"
        cond += f"e={a}-{b}"
        mod = f"[s={vs};e=EP-{off}]" if off != 0 else f"[s={vs}]"
        rule = f"@?{{[{cond}]}} => {{{mod}}}"
        if rule not in rules:
            rules.append(rule)

    lines = [
        f"# [自动分季] {title or tmdb_id} TMDB:{tmdb_id} 依据={reference or '未知'} {_date.today().isoformat()}"
    ]
    if ambiguous_any:
        lines.append("# 注意: 存在跨季重叠的集号区间,冲突段已保留季限定(s=)")
    lines.extend(rules)
    if season_years and use_includes:
        lines.extend(includes_rule_lines(tmdb_id, season_years))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 剧集组 JSON（移植 Lens，逻辑不变）
# ---------------------------------------------------------------------------

def logic_to_group_json(logic, tmdb_id: int) -> dict:
    """把拆分出的虚拟季导出为剧集组 JSON(与 episode_group_tool 输出同格式)。"""
    groups = []
    for season in logic.seasons:
        episodes = []
        idx = 0
        for order in sorted(season.episodes_map):
            em = season.episodes_map[order]
            if em.type != "tv":
                continue  # 剧集组无法表达电影条目
            episodes.append({
                "episode_number": em.episode_number,
                "season_number": em.season_num(),
                "order": idx,
            })
            idx += 1
        groups.append({
            "name": season.name or f"第 {season.season_number} 季",
            "air_date": season.air_date or "",
            "order": season.season_number,
            "episodes": episodes,
        })
    return {"description": "", "groups": groups, "id": str(tmdb_id)}


def build_finale_groups(raw_seasons: list, number_of_seasons: int) -> list:
    """以季结局(episode_type=finale)为界划分剧集组;finale 标记缺失且 TMDB 有多季时按季兜底。"""
    all_eps: list = []
    for season in raw_seasons:
        sn = int(season.get("season_number") or 0)
        for ep in season.get("episodes") or []:
            ep = dict(ep)
            ep["_season_number"] = sn
            if sn > 0:
                all_eps.append(ep)
    all_eps.sort(key=lambda e: (e["_season_number"], e.get("episode_number") or 0))
    if not all_eps:
        return []

    groups: list = []
    current: list = []
    idx = 1
    for ep in all_eps:
        current.append(ep)
        if ep.get("episode_type") == "finale":
            groups.append({"name": f"第 {idx} 季", "order": idx, "episodes": list(current)})
            current = []
            idx += 1
    if current:
        groups.append({"name": f"第 {idx} 季", "order": idx, "episodes": list(current)})

    # finale 标记缺失兜底:只划出一个组但 TMDB 有多季 → 直接按季分组
    if len(groups) == 1 and number_of_seasons > 1:
        per: dict = {}
        for ep in all_eps:
            per.setdefault(ep["_season_number"], []).append(ep)
        groups = [
            {"name": f"第 {sn} 季", "order": sn, "episodes": eps}
            for sn, eps in sorted(per.items())
        ]
    return groups


def groups_to_group_json(groups: list, tmdb_id: int) -> dict:
    """把分组结果转为剧集组 JSON。"""
    out_groups = []
    for g in groups:
        eps = g.get("episodes") or []
        episodes = [
            {
                "episode_number": e.get("episode_number"),
                "season_number": e.get("_season_number"),
                "order": i,
            }
            for i, e in enumerate(eps)
        ]
        first = eps[0] if eps else {}
        out_groups.append({
            "name": g.get("name"),
            "air_date": first.get("air_date") or "",
            "order": g.get("order"),
            "episodes": episodes,
        })
    return {"description": "", "groups": out_groups, "id": str(tmdb_id)}


def generate_group_render_words(tmdb_id: int, title: str, reference: str, groups: list,
                                use_includes: bool = True) -> str:
    """按剧集组生成渲染词:第 i 组(i>0)的集号绝对窗口 [cum+1, cum+n] → [s=order;e=EP-cum]。

    窗口为全作累计集序,组间天然不重叠,因此条件无需季号限定,
    可同时命中 S2E13 这类"季号 + 续位集号"的命名(→ S2E1)。
    仅一个组时不生成。另按各组首播年份追加 includes 条件规则(含首个组)。
    """
    if len(groups) <= 1:
        return ""
    lines = [
        f"# [自动分季] {title or tmdb_id} TMDB:{tmdb_id} 依据={reference or '未知'} {_date.today().isoformat()}"
    ]
    cumulative = 0
    for i, g in enumerate(groups):
        n = len(g.get("episodes") or [])
        if n <= 0:
            continue
        if i > 0:
            start, end = cumulative + 1, cumulative + n
            lines.append(
                f"@?{{[tmdbid={tmdb_id};type=tv;e={start}-{end}]}} => {{[s={g['order']};e=EP-{cumulative}]}}"
            )
        cumulative += n

    # 每组首播年份（按组内集顺序取第一个有日期的集）→ includes 条件规则
    season_years: dict = {}
    for g in groups:
        order = g.get("order")
        if not isinstance(order, int):
            continue
        for ep in g.get("episodes") or []:
            year = first_air_year(ep.get("air_date"))
            if year:
                season_years[order] = year
                break
    if season_years and use_includes:
        lines.extend(includes_rule_lines(tmdb_id, season_years))
    return "\n".join(lines) if len(lines) > 1 else ""


# ---------------------------------------------------------------------------
# 分组 ⇄ 映射表（本项目的「可编辑分组」层）
# ---------------------------------------------------------------------------

def _ep_key(ep) -> tuple:
    """把 (s, e) / {"s":..,"e":..} / [s, e] / TMDB 原始集字典 统一成 (season, episode)。"""
    if isinstance(ep, (tuple, list)) and len(ep) >= 2:
        return (int(ep[0]), int(ep[1]))
    if isinstance(ep, dict):
        season = ep.get("s")
        if season is None:
            season = ep.get("season")
        if season is None:
            season = ep.get("season_number")
        episode = ep.get("e")
        if episode is None:
            episode = ep.get("episode")
        if episode is None:
            episode = ep.get("episode_number")
        return (int(season or 0), int(episode or 0))
    raise ValueError(f"无法解析集坐标: {ep!r}")


def mapping_from_groups(groups: list, flat_eps: list,
                        overrides: Optional[dict] = None,
                        excluded: Optional[list] = None) -> dict:
    """分组定义 + 逐集覆盖 + 排除集 → 逐集映射表。

    - groups 里的 start/end 是「摊平后序号区间」的端点（用 (s,e) 表达）；
      组内按摊平顺序（即播出顺序）连续编号。
    - excluded 里的集**不参与重排**：既不消耗编号，也不会进 mapping
      （= 不会被任何规则命中，保持原编号）。
    - overrides 优先级最高，形如 {("1", "13"): {"s":2,"e":1}} 或 {(1,13):(2,1)}。
    """
    flat = [_ep_key(e) for e in flat_eps]
    index_of = {ep: i for i, ep in enumerate(flat)}
    excluded_set = {_ep_key(e) for e in (excluded or [])}

    mapping: dict = {}
    for g in sorted(groups, key=lambda x: int(x.get("order") or 0)):
        order = int(g.get("order") or 0)
        if order <= 0:
            continue
        start = _ep_key(g.get("start") or (0, 0))
        end = _ep_key(g.get("end") or (0, 0))
        a = index_of.get(start)
        b = index_of.get(end)
        if a is None or b is None:
            # 起点/终点不在摊平表里（数据变动）→ 用坐标顺序兜底
            members = [ep for ep in flat if start <= ep <= end]
        else:
            if b < a:
                a, b = b, a
            members = flat[a:b + 1]
        n = 0
        for ep in members:
            if ep in excluded_set:
                continue
            n += 1
            mapping[ep] = (order, n)

    for key, dst in (overrides or {}).items():
        src = _ep_key(key if isinstance(key, (tuple, list)) else (str(key).split("-")[0], str(key).split("-")[1]))
        if isinstance(dst, dict):
            mapping[src] = (int(dst.get("s") or 0), int(dst.get("e") or 0))
        else:
            mapping[src] = _ep_key(dst)
    return mapping


def groups_from_mapping(mapping: dict) -> list:
    """逐集映射表 → 分组定义（用于把算法结果送进编辑器）。"""
    per: dict = {}
    for (orig_s, orig_e), (virt_s, virt_e) in mapping.items():
        per.setdefault(int(virt_s), []).append(((int(orig_s), int(orig_e)), int(virt_e)))
    groups = []
    for order in sorted(per):
        items = sorted(per[order], key=lambda x: x[1])
        groups.append({
            "order": order,
            "name": f"第 {order} 季",
            "start": {"s": items[0][0][0], "e": items[0][0][1]},
            "end": {"s": items[-1][0][0], "e": items[-1][0][1]},
        })
    return groups


def groups_from_logic(logic) -> list:
    """LogicSeries → 分组定义。"""
    groups = []
    for season in logic.seasons:
        if not season.episodes_map:
            continue
        orders = sorted(season.episodes_map)
        first = season.episodes_map[orders[0]]
        last = season.episodes_map[orders[-1]]
        groups.append({
            "order": int(season.season_number),
            "name": season.name or f"第 {season.season_number} 季",
            "start": {"s": first.season_num(), "e": first.episode_num()},
            "end": {"s": last.season_num(), "e": last.episode_num()},
        })
    return groups


def group_json_from_mapping(tmdb_id: int, mapping: dict, names: Optional[dict] = None,
                            air_dates: Optional[dict] = None) -> dict:
    """映射表 → 剧集组 JSON（等价 Lens logic_to_group_json，但直接吃 mapping）。

    虚拟季按 order 升序成为 group；组内按虚拟集号升序，`order` 为组内序号（从 0 起）。
    air_dates: {(原始季, 原始集): "YYYY-MM-DD"}，用于填 group 的 air_date（取组内第一集）。
    """
    names = names or {}
    air_dates = air_dates or {}
    per: dict = {}
    for (orig_s, orig_e), (virt_s, virt_e) in mapping.items():
        per.setdefault(int(virt_s), []).append((int(virt_e), int(orig_s), int(orig_e)))

    groups = []
    for virt_s in sorted(per):
        items = sorted(per[virt_s], key=lambda x: x[0])
        episodes = [
            {"episode_number": orig_e, "season_number": orig_s, "order": i}
            for i, (_virt_e, orig_s, orig_e) in enumerate(items)
        ]
        first = items[0]
        groups.append({
            "name": names.get(virt_s) or f"第 {virt_s} 季",
            "air_date": air_dates.get((first[1], first[2])) or "",
            "order": virt_s,
            "episodes": episodes,
        })
    return {"description": "", "groups": groups, "id": str(tmdb_id)}


def episode_rows(mapping: dict, raw_lookup: Optional[dict] = None) -> list:
    """映射表 → 逐集明细（前端表格用）。"""
    raw_lookup = raw_lookup or {}
    rows = []
    for (orig_s, orig_e), (virt_s, virt_e) in sorted(
        mapping.items(), key=lambda kv: (kv[1][0], kv[1][1])
    ):
        raw = raw_lookup.get(f"S{orig_s}E{orig_e}") or {}
        rows.append({
            "season": virt_s,
            "episode": virt_e,
            "org_season": orig_s,
            "org_episode": orig_e,
            "air_date": raw.get("air_date") or "",
            "name": raw.get("name") or "",
            "episode_type": raw.get("episode_type") or "",
        })
    return rows


def season_years_from_mapping(mapping: dict, flat_eps: list) -> dict:
    """虚拟季号 → 首播年份（按摊平顺序取该季第一集有日期的年份）。"""
    flat_index: dict = {}
    for ep in flat_eps or []:
        s, e = _ep_key(ep) if not isinstance(ep, dict) else _ep_key(ep)
        flat_index[(s, e)] = ep
    years: dict = {}
    per: dict = {}
    for (orig_s, orig_e), (virt_s, _virt_e) in mapping.items():
        per.setdefault(int(virt_s), []).append((int(orig_s), int(orig_e)))
    for virt_s, items in per.items():
        for s, e in sorted(items):
            ep = flat_index.get((s, e))
            air = ""
            if isinstance(ep, dict):
                air = ep.get("air_date") or ""
            elif isinstance(ep, (tuple, list)) and len(ep) >= 3:
                air = ep[2] or ""
            year = first_air_year(air)
            if year:
                years[virt_s] = year
                break
    return years


def parse_mapping_json(data) -> dict:
    """{"1": {"13": {"season":2,"episode":1}}} → {(1,13): (2,1)}"""
    out: dict = {}
    if isinstance(data, str):
        try:
            data = json.loads(data or "{}")
        except Exception:
            return out
    if not isinstance(data, dict):
        return out
    for s, eps in data.items():
        if not isinstance(eps, dict):
            continue
        for e, dst in eps.items():
            try:
                if isinstance(dst, dict):
                    out[(int(s), int(e))] = (int(dst.get("season") or dst.get("s") or 0),
                                             int(dst.get("episode") or dst.get("e") or 0))
                elif isinstance(dst, (list, tuple)) and len(dst) >= 2:
                    out[(int(s), int(e))] = (int(dst[0]), int(dst[1]))
            except (TypeError, ValueError):
                continue
    return out


def dump_mapping(mapping: dict) -> dict:
    """{(1,13): (2,1)} → {"1": {"13": {"season":2,"episode":1}}}（JSON 友好）"""
    out: dict = {}
    for (s, e), (vs, ve) in sorted(mapping.items()):
        out.setdefault(str(s), {})[str(e)] = {"season": vs, "episode": ve}
    return out


# ---------------------------------------------------------------------------
# 轻量规则回放（调试器 / 自测用）
# ---------------------------------------------------------------------------

_RULE_RE = re.compile(r"^@\?\{\[(.*?)\]\}\s*=>\s*\{\[(.*?)\]\}$")


def _conditions_ok(conds: dict, season: int, episode: int, tmdb_id,
                   mtype: str = "tv", year: str = "", filename: str = "") -> bool:
    """与 RenderEngine 一致：所有出现的条件必须同时成立。"""
    if "tmdbid" in conds and conds["tmdbid"] != str(tmdb_id):
        return False
    if "type" in conds and conds["type"] != mtype:
        return False
    if "year" in conds and conds["year"] != str(year):
        return False
    if "s" in conds and str(season) != conds["s"]:
        return False
    if "e" in conds:
        if "-" in conds["e"]:
            a, b = (int(x) for x in conds["e"].split("-"))
            if not (a <= episode <= b):
                return False
        elif str(episode) != conds["e"]:
            return False
    if "includes" in conds and conds["includes"].lower() not in (filename or "").lower():
        return False
    return True


def _eval_math(expr: str, episode: int) -> int:
    text = str(expr).upper().replace("EP", str(episode))
    if not re.match(r"^[\d\s\+\-\*\/\%\(\)\.]+$", text):
        raise ValueError(f"非法表达式: {expr}")
    return int(eval(text, {"__builtins__": {}}, {}))


def apply_rules_to_episode(rules_text: str, season: int, episode: int, tmdb_id,
                           mtype: str = "tv", year: str = "", filename: str = "") -> tuple:
    """按渲染词文本回放，返回 (season, episode)。

    语义与 `RenderEngine.apply_rules` 对齐：按顺序逐条判定，命中即就地修改，
    后续规则读到的是修改后的值（这也是「一次只命中最匹配的那条」的前提）。
    """
    s, e = int(season), int(episode)
    for line in (rules_text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = _RULE_RE.match(line)
        if not m:
            continue
        conds = {kv.split("=", 1)[0].strip().lower(): kv.split("=", 1)[1].strip()
                 for kv in m.group(1).split(";") if "=" in kv}
        if not _conditions_ok(conds, s, e, tmdb_id, mtype, year, filename):
            continue
        mods = {kv.split("=", 1)[0].strip().lower(): kv.split("=", 1)[1].strip()
                for kv in m.group(2).split(";") if "=" in kv}
        if "s" in mods:
            s = int(mods["s"])
        if "e" in mods:
            e = _eval_math(mods["e"], e)
    return s, e
