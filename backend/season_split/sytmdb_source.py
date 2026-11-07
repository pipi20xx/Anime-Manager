# -*- coding: utf-8 -*-
"""番剧分季拆分 · SYTMDB 剧集组导入源。

SYTMDB（sy1024 / 容器 emby-sytmdb）把「一部番怎么分成多季」存成剧集组文件::

    {"description": "", "id": "220542",
     "groups": [{"name": "第 1 季", "air_date": "", "order": 1,
                 "episodes": [{"episode_number": 1, "season_number": 1, "order": 0}, ...]}]}

本模块只做三件事，**不依赖 TMDB 重新生成**：

1. 拉「所有带剧集组的条目」——官方筛选参数 ``GET /api/items/tmdb-tv?has_episode_group=yes``。
   老版本 SYTMDB 的后端（routers/items.py 只认 search_term/source/poster_status/genre/
   year/month/sort_by/page/limit）会静默忽略这个参数，所以再按 ``has_episode_group`` 字段
   兜底过滤一次，两个版本都能用。
2. 把 SYTMDB 的分组原样翻译成映射表 ``(原始季, 原始集) → (虚拟季, 虚拟集)``：
   组里的 ``order`` 就是组内最终集号（0 起），因此结果是「那边写的是什么，这里就是什么」。
   **S0 特别篇也照搬**（渲染词用 `s=0;e=N` 一样能表达），只有重复集会被去重。
3. 由映射表反推渲染词，并用 ``compiler.apply_rules_to_episode`` 回放自检，
   保证注入识别链路的规则能 1:1 还原映射表。

渲染词的四层回退（都能 1:1 回放才采用）：

1. 紧凑区间：``@?{[tmdbid=..;type=tv;e=13-24]} => {[s=2;e=EP-12]}``
2. 带季号 + 季号倒序：源里跨季集号重叠时用（避免规则互相二次改写）
3. 混合：区间规则（S≥1）+ 逐集规则（S0 特别篇 / 乱序集）
4. 全逐集：任意置换都能表达；有环时用「临时季号」两阶段搬运（A→临时→B）
"""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

import httpx

from . import compiler

DEFAULT_PORT = 8121
DEFAULT_PAGE_SIZE = 200
# 两阶段搬运用的临时季号起点（真实季号不会有这么大）
TEMP_SEASON_BASE = 9000


# ---------------------------------------------------------------------------
# 地址 / 请求
# ---------------------------------------------------------------------------

def base_url(addr: str) -> str:
    """把配置里的地址补全成 http://host:port（无端口时按 SYTMDB 默认 8121）。"""
    text = (addr or "").strip().rstrip("/")
    if not text:
        raise ValueError("未配置 SYTMDB 地址（系统设置 → SYTMDB）")
    if "://" not in text:
        text = f"http://{text}"
    scheme, _, rest = text.partition("://")
    host = rest.split("/", 1)[0]
    tail = rest[len(host):]
    has_port = ":" in host.rsplit("]", 1)[-1]  # 兼容 IPv6 字面量
    # 只有 http / 裸主机名才补 SYTMDB 默认端口；https 不补（多半是反代在 443 上）
    if not has_port and scheme.lower() != "https":
        host = f"{host}:{DEFAULT_PORT}"
    return f"{scheme}://{host}{tail}"


def _headers(token: str = "") -> Dict[str, str]:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value or "").strip().lower() in ("1", "true", "yes", "on")


# ---------------------------------------------------------------------------
# 读取 SYTMDB
# ---------------------------------------------------------------------------

async def fetch_tmdb_tv_items(addr: str, token: str = "",
                              page_size: int = DEFAULT_PAGE_SIZE,
                              max_pages: int = 100) -> Tuple[List[dict], int]:
    """遍历 ``/api/items/tmdb-tv``，返回 (带剧集组的条目, 服务端报告的总数)。"""
    base = base_url(addr)
    items: List[dict] = []
    total = 0
    async with httpx.AsyncClient(timeout=30) as client:
        for page in range(1, max_pages + 1):
            params = {
                "page": page,
                "limit": page_size,
                "has_episode_group": "yes",  # 新版 SYTMDB 原生筛选；老版忽略
            }
            resp = await client.get(f"{base}/api/items/tmdb-tv",
                                    params=params, headers=_headers(token))
            resp.raise_for_status()
            data = resp.json() or {}
            batch = data.get("items") or []
            try:
                total = int(data.get("total_items") or total or 0)
            except (TypeError, ValueError):
                pass
            items.extend(batch)
            if not data.get("has_more") or not batch:
                break

    matched = [item for item in items
               if _truthy(item.get("has_episode_group")) and str(item.get("id") or "").strip()]
    return matched, total


async def fetch_episode_group(addr: str, token: str, tmdb_id: int) -> dict:
    """读取单个番的剧集组 JSON；不存在时返回空结构。"""
    base = base_url(addr)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{base}/api/tv/{int(tmdb_id)}/episodegroup",
                                headers=_headers(token))
        if resp.status_code == 404:
            return {"id": str(tmdb_id), "description": "", "groups": []}
        resp.raise_for_status()
        data = resp.json() or {}
    if isinstance(data, list):  # 个别版本直接返回分组数组
        data = {"groups": data}
    if not isinstance(data, dict):
        data = {}
    return data


# ---------------------------------------------------------------------------
# 剧集组 → 映射表 / 分组
# ---------------------------------------------------------------------------

def mapping_from_group_json(raw: dict, include_specials: bool = True) -> Tuple[Dict[Tuple[int, int], Tuple[int, int]], dict]:
    """剧集组 → 映射表 + 统计。

    - 组内 ``order`` 就是最终集号（0 起），所以结果就是「那边写的是什么，这里就是什么」；
    - **S0 特别篇默认保留**（``include_specials=True``）：源把它放进第 N 组，
      就映射成 ``S0Exx → SNEx``，规则用 ``s=0`` 条件照样能表达；
    - 同一 ``(季, 集)`` 在源里出现两次时保留第一次（第二处记进 duplicates），
      重复集不占编号，编号始终从 1 连续排下去。
    """
    mapping: Dict[Tuple[int, int], Tuple[int, int]] = {}
    info: dict = {"duplicates": [], "specials": 0, "invalid": []}
    for group in (raw or {}).get("groups") or []:
        try:
            order = int(group.get("order") or 0)
        except (TypeError, ValueError):
            continue
        if order <= 0:
            continue
        episodes = list(group.get("episodes") or [])
        episodes.sort(key=lambda e: int(e.get("order") or 0))
        index = 0
        for ep in episodes:
            try:
                season = int(ep.get("season_number") or 0)
                episode = int(ep.get("episode_number") or 0)
            except (TypeError, ValueError):
                continue
            if season < 0 or episode < 1:
                info["invalid"].append({"season": season, "episode": episode, "order": order})
                continue
            if season == 0:
                if not include_specials:
                    info["specials"] += 1
                    continue
                info["specials"] += 1
            if (season, episode) in mapping:
                info["duplicates"].append({"season": season, "episode": episode, "order": order})
                continue
            index += 1
            mapping[(season, episode)] = (order, index)
    return mapping, info


def names_from_group_json(raw: dict) -> Dict[int, str]:
    names: Dict[int, str] = {}
    for group in (raw or {}).get("groups") or []:
        try:
            order = int(group.get("order") or 0)
        except (TypeError, ValueError):
            continue
        if order > 0:
            names[order] = str(group.get("name") or f"第 {order} 季")
    return names


def groups_from_mapping(mapping: Dict[Tuple[int, int], Tuple[int, int]],
                        names: Optional[Dict[int, str]] = None) -> List[dict]:
    """映射表 → 规则库的分组定义（每组取首尾 (季, 集) 坐标）。"""
    names = names or {}
    per: Dict[int, List[Tuple[int, int, int]]] = {}
    for (season, episode), (virt_s, virt_e) in mapping.items():
        per.setdefault(int(virt_s), []).append((int(virt_e), int(season), int(episode)))
    groups: List[dict] = []
    for virt_s in sorted(per):
        items = sorted(per[virt_s])
        first_s, first_e = items[0][1], items[0][2]
        last_s, last_e = items[-1][1], items[-1][2]
        groups.append({
            "order": virt_s,
            "name": names.get(virt_s) or f"第 {virt_s} 季",
            "start": {"s": first_s, "e": first_e},
            "end": {"s": last_s, "e": last_e},
        })
    return groups


def changed_pairs(mapping: Dict[Tuple[int, int], Tuple[int, int]]) -> List[Tuple[Tuple[int, int], Tuple[int, int]]]:
    """真正会被改写的集（原坐标 ≠ 目标坐标）。"""
    return [((s, e), (vs, ve)) for (s, e), (vs, ve) in sorted(mapping.items()) if (s, e) != (vs, ve)]


def needs_overrides(mapping: Dict[Tuple[int, int], Tuple[int, int]]) -> bool:
    """分组区间能不能精确表达这份映射；不能就只能靠 overrides 保真。

    三种情况表达不了：含 S0 特别篇（编辑器按 TMDB 季结构画区间）、
    组内顺序与季集坐标顺序不一致、目标集号有跳号。
    """
    if any(season < 1 for season, _episode in mapping):
        return True
    per: Dict[int, List[Tuple[int, int, int]]] = {}
    for (season, episode), (virt_s, virt_e) in mapping.items():
        per.setdefault(int(virt_s), []).append((int(virt_e), int(season), int(episode)))
    for items in per.values():
        ordered = sorted(items)
        if [(s, e) for _ve, s, e in ordered] != sorted((s, e) for _ve, s, e in ordered):
            return True
        # 目标集号必须从 1 连续，否则区间重算会错位
        if [ve for ve, _s, _e in ordered] != list(range(1, len(ordered) + 1)):
            return True
    return False


def flat_overrides(mapping: Dict[Tuple[int, int], Tuple[int, int]]) -> Dict[str, dict]:
    """映射表 → `mapping_from_groups` 认识的 overrides（扁平 "季-集" 键）。

    只在分组区间表达不了源数据时才写，作用是让「编辑器里再保存一次」也不会把映射改形。
    """
    return {
        f"{season}-{episode}": {"s": virt_s, "e": virt_e}
        for (season, episode), (virt_s, virt_e) in sorted(mapping.items())
    }


# ---------------------------------------------------------------------------
# 映射表 → 渲染词
# ---------------------------------------------------------------------------

def _header(tmdb_id: int, title: str) -> str:
    return f"# [自动分季] {title or tmdb_id} TMDB:{tmdb_id} 依据=SYTMDB {date.today().isoformat()}"


def _replay_ok(tmdb_id: int, mapping: Dict[Tuple[int, int], Tuple[int, int]], words: str) -> bool:
    for (season, episode), want in mapping.items():
        if compiler.apply_rules_to_episode(words, season, episode, tmdb_id) != want:
            return False
    return True


def _words_qualified(tmdb_id: int, title: str,
                     mapping: Dict[Tuple[int, int], Tuple[int, int]]) -> str:
    """每个原始季都带 s= 限定，且按季号倒序排列（只处理 S≥1）。

    带 s= 是为了让「同一集号在不同季」不会互相命中；倒序是因为
    RenderEngine 逐条就地修改，后面的规则会读到改过的季号，
    倒序可保证「S3→S4」的结果不会被 S4 的规则二次改写。
    """
    positive = {k: v for k, v in mapping.items() if k[0] >= 1}
    if not positive:
        return ""
    lines = [_header(tmdb_id, title)]
    for season in sorted({key[0] for key in positive}, reverse=True):
        sub = {k: v for k, v in positive.items() if k[0] == season}
        text = compiler.generate_render_words(tmdb_id, title, "SYTMDB", sub, None, use_includes=False)
        for line in text.splitlines():
            if not line.startswith("@?"):
                continue
            head, sep, tail = line.partition("]}")
            if sep and ";s=" not in head:
                head = head.replace("type=tv;", f"type=tv;s={season};", 1)
            lines.append(head + sep + tail)
    return "\n".join(lines)


def _rule_exact(tmdb_id: int, season: int, episode: int, virt_s: int, virt_e: int) -> str:
    return f"@?{{[tmdbid={tmdb_id};type=tv;s={season};e={episode}]}} => {{[s={virt_s};e={virt_e}]}}"


def _exact_rules(tmdb_id: int,
                 pairs: List[Tuple[Tuple[int, int], Tuple[int, int]]]) -> Tuple[List[str], bool]:
    """逐集规则，按「谁的条件等于谁的结果」排序；有环时改用两阶段搬运。

    返回 (规则行, 是否用了两阶段)。
    """
    pairs = [((s, e), (vs, ve)) for (s, e), (vs, ve) in pairs if (s, e) != (vs, ve)]
    if not pairs:
        return [], False

    index_of = {src: i for i, (src, _dst) in enumerate(pairs)}
    after: Dict[int, set] = {i: set() for i in range(len(pairs))}  # i 必须排在 after[i] 之前
    for i, (_src, dst) in enumerate(pairs):
        j = index_of.get(dst)
        if j is not None and j != i:
            after[j].add(i)

    state: Dict[int, int] = {}
    order: List[int] = []
    cyclic = False

    def visit(i: int) -> None:
        nonlocal cyclic
        flag = state.get(i, 0)
        if flag == 1:
            cyclic = True
            return
        if flag == 2:
            return
        state[i] = 1
        for prev in sorted(after[i]):
            visit(prev)
        state[i] = 2
        order.append(i)

    for i in range(len(pairs)):
        visit(i)

    if not cyclic:
        return [_rule_exact(tmdb_id, src[0], src[1], dst[0], dst[1]) for src, dst in
                (pairs[i] for i in order)], False

    # 有环：不能一遍改到位。先全部搬进「临时季号」，再从临时季号落到目标。
    phase_a: List[str] = []
    phase_b: List[str] = []
    for src, dst in pairs:
        temp = TEMP_SEASON_BASE + src[0]
        phase_a.append(f"@?{{[tmdbid={tmdb_id};type=tv;s={src[0]};e={src[1]}]}} => {{[s={temp}]}}")
        phase_b.append(_rule_exact(tmdb_id, temp, src[1], dst[0], dst[1]))
    return phase_a + phase_b, True


def generate_words(tmdb_id: int, title: str,
                   mapping: Dict[Tuple[int, int], Tuple[int, int]]) -> Tuple[str, List[str], bool]:
    """映射表 → 渲染词。返回 (渲染词, 提示, 是否 1:1 回放通过)。

    四层回退：紧凑 → 带季号倒序 → 混合（区间 + 逐集） → 全逐集（含两阶段）。
    """
    warnings: List[str] = []
    changed = changed_pairs(mapping)
    if not changed:
        warnings.append("剧集组与 TMDB 原始季结构一致，没有需要改写的集")
        return _header(tmdb_id, title), warnings, True

    has_specials = any(src[0] < 1 for src, _dst in changed)

    # 1) 紧凑区间（源里没有 S0、且集号连续）
    if not has_specials:
        words = compiler.generate_render_words(
            tmdb_id, title, "SYTMDB", mapping, None, use_includes=False
        )
        if _replay_ok(tmdb_id, mapping, words):
            return words, warnings, True

    # 2) 带季号 + 季号倒序（只覆盖 S≥1；没有 S0 时可直接用）
    qualified = _words_qualified(tmdb_id, title, mapping)
    if qualified and not has_specials and _replay_ok(tmdb_id, mapping, qualified):
        warnings.append("源数据存在跨季集号重叠，已改为带季号限定并按季号倒序的写法")
        return qualified, warnings, True

    # 3) 混合：区间规则（S≥1）+ 逐集补 S0 / 乱序集
    positive = {k: v for k, v in mapping.items() if k[0] >= 1}
    specials = {k: v for k, v in mapping.items() if k[0] < 1}
    if qualified and specials and _replay_ok(tmdb_id, positive, qualified):
        extra, two_phase = _exact_rules(tmdb_id, changed_pairs(specials))
        combined = "\n".join([qualified] + extra) if extra else qualified
        if _replay_ok(tmdb_id, mapping, combined):
            note = f"{len(specials)} 集 S0 特别篇用逐集规则落进对应季"
            if two_phase:
                note += "（含环形置换，用临时季号两阶段搬运）"
            warnings.append(note)
            return combined, warnings, True

    # 4) 全逐集
    lines, two_phase = _exact_rules(tmdb_id, changed)
    words = "\n".join([_header(tmdb_id, title)] + lines)
    if _replay_ok(tmdb_id, mapping, words):
        note = "源剧集组是自定义顺序，已改为逐集精确规则"
        if two_phase:
            note = "源剧集组存在环形置换，已用临时季号两阶段搬运（逐集规则）"
        if has_specials:
            note += f"，其中 {len(specials)} 集是 S0 特别篇"
        warnings.append(note)
        return words, warnings, True

    warnings.append("规则回放自检未通过，导入后请到工作台手动确认")
    return words, warnings, False


# ---------------------------------------------------------------------------
# 组装成规则库能直接落库的 payload
# ---------------------------------------------------------------------------

def normalize_group_json(raw: dict, tmdb_id: int) -> dict:
    """把 SYTMDB 原文清洗成稳定结构（写回 SYTMDB 时可直接用）。"""
    groups: List[dict] = []
    for group in (raw or {}).get("groups") or []:
        try:
            order = int(group.get("order") or 0)
        except (TypeError, ValueError):
            continue
        if order <= 0:
            continue
        episodes = list(group.get("episodes") or [])
        episodes.sort(key=lambda e: int(e.get("order") or 0))
        cleaned = []
        for index, ep in enumerate(episodes):
            try:
                season = int(ep.get("season_number") or 0)
                episode = int(ep.get("episode_number") or 0)
            except (TypeError, ValueError):
                continue
            cleaned.append({"episode_number": episode, "season_number": season, "order": index})
        groups.append({
            "name": str(group.get("name") or f"第 {order} 季"),
            "air_date": str(group.get("air_date") or ""),
            "order": order,
            "episodes": cleaned,
        })
    return {
        "id": str(tmdb_id),
        "description": str((raw or {}).get("description") or ""),
        "groups": groups,
    }


def build_rule(item: dict, raw: dict, status: str = "active") -> dict:
    """SYTMDB 条目 + 剧集组 → 落库 payload（字段与 store.upsert_rule 对齐）。"""
    tmdb_id = int(item.get("id"))
    title = str(item.get("name") or f"TMDB {tmdb_id}")
    mapping, info = mapping_from_group_json(raw)
    if not mapping:
        raise ValueError("剧集组里没有任何剧集（空分组）")

    names = names_from_group_json(raw)
    groups = groups_from_mapping(mapping, names)
    words, warnings, replay_ok = generate_words(tmdb_id, title, mapping)
    rule_count = len([line for line in words.splitlines() if line.startswith("@?")])
    changed = changed_pairs(mapping)
    specials_included = sum(1 for src, _dst in changed if src[0] < 1)
    if info["duplicates"]:
        warnings.append(f"源里有 {len(info['duplicates'])} 处重复集，已保留第一次出现")
    if specials_included:
        warnings.append(
            f"{specials_included} 集 S0 特别篇已完整写入规则与剧集组（Emby 显示照旧）；"
            "但识别引擎把「季 0」当季 1 处理，s=0 的规则实际不会命中，特别篇不会改名"
        )
    if needs_overrides(mapping):
        warnings.append("分组区间表达不了这份映射（含特别篇/乱序），已写 overrides 锁住逐集结果")

    if not replay_ok:
        warnings.append("规则回放自检未通过，已强制存为草稿（不会注入识别）")
        status = "draft"

    payload = {
        "tmdb_id": tmdb_id,
        "title": title,
        "status": status,
        "reference": "sytmdb",
        "groups_json": groups,
        "names_json": {str(k): v for k, v in names.items()},
        "overrides_json": flat_overrides(mapping) if needs_overrides(mapping) else {},
        "excluded_json": [],
        "mapping_json": compiler.dump_mapping(mapping),
        "group_json": normalize_group_json(raw, tmdb_id),
        "render_words": words,
        "tmdb_hash": "",
        "episode_total": len(mapping),
    }
    return {
        "payload": payload,
        "stats": {
            "tmdb_id": tmdb_id,
            "title": title,
            "year": item.get("year"),
            "source": item.get("source"),
            "group_count": len(groups),
            "episode_total": len(mapping),
            "changed_episodes": len(changed),
            "specials": specials_included,
            "duplicates": len(info["duplicates"]),
            "rule_count": rule_count,
            "replay_ok": replay_ok,
            "status": status,
            "will_change": bool(changed),
            "needs_overrides": bool(payload["overrides_json"]),
            "warnings": warnings,
        },
    }


async def collect_candidates(addr: str, token: str,
                             concurrency: int = 8) -> Tuple[List[dict], int, List[dict]]:
    """列出所有带剧集组的番 + 统计（不落库，供导入对话框勾选）。"""
    items, total = await fetch_tmdb_tv_items(addr, token)
    sem = asyncio.Semaphore(max(1, concurrency))
    errors: List[dict] = []

    async def one(item: dict) -> Optional[dict]:
        tmdb_id = int(item.get("id"))
        async with sem:
            try:
                raw = await fetch_episode_group(addr, token, tmdb_id)
            except Exception as e:  # 单个失败不影响整表
                errors.append({"tmdb_id": tmdb_id, "title": item.get("name"), "error": str(e)})
                return None
        mapping, info = mapping_from_group_json(raw)
        changed = changed_pairs(mapping)
        return {
            "tmdb_id": tmdb_id,
            "title": str(item.get("name") or f"TMDB {tmdb_id}"),
            "year": item.get("year"),
            "source": item.get("source"),
            "group_count": len(groups_from_mapping(mapping, names_from_group_json(raw))),
            "episode_total": len(mapping),
            "changed_episodes": len(changed),
            "specials": sum(1 for src, _dst in changed if src[0] < 1),
            "duplicates": len(info["duplicates"]),
            "will_change": bool(changed),
        }

    rows = await asyncio.gather(*[one(item) for item in items])
    return [r for r in rows if r], total, errors
