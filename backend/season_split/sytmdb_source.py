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
3. 由映射表反推渲染词，并用 ``compiler.apply_rules_to_episode`` 回放自检，
   保证注入识别链路的规则能 1:1 还原映射表。
"""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

import httpx

from . import compiler

DEFAULT_PORT = 8121
DEFAULT_PAGE_SIZE = 200


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
    if not has_port:
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
# 剧集组 → 映射表 / 分组 / 渲染词
# ---------------------------------------------------------------------------

def mapping_from_group_json(raw: dict) -> Tuple[Dict[Tuple[int, int], Tuple[int, int]], List[dict]]:
    """剧集组 → 映射表 + 被跳过的条目。

    跳过两类：
    - **S0 特别篇**：渲染词的 s= 无法表达季 0，只能放弃（记进 skipped，导入时会提示）
    - **重复集**：同一 (季, 集) 在源里出现两次（SYTMDB 手滑的常见形态），保留第一次
    被跳过的集不占编号，编号始终从 1 连续排下去。
    """
    mapping: Dict[Tuple[int, int], Tuple[int, int]] = {}
    skipped: List[dict] = []
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
            if season < 1 or episode < 1:
                skipped.append({"season": season, "episode": episode, "order": order,
                                "reason": "specials"})
                continue
            if (season, episode) in mapping:
                skipped.append({"season": season, "episode": episode, "order": order,
                                "reason": "duplicate"})
                continue
            index += 1
            mapping[(season, episode)] = (order, index)
    return mapping, skipped


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


def needs_overrides(mapping: Dict[Tuple[int, int], Tuple[int, int]]) -> bool:
    """组内顺序是否与「按季集坐标排序」一致；不一致就只能靠 overrides 保真。"""
    per: Dict[int, List[Tuple[int, int, int]]] = {}
    for (season, episode), (virt_s, virt_e) in mapping.items():
        per.setdefault(int(virt_s), []).append((int(virt_e), int(season), int(episode)))
    for items in per.values():
        by_virt = [(s, e) for _ve, s, e in sorted(items)]
        if by_virt != sorted(by_virt):
            return True
    return False


def flat_overrides(mapping: Dict[Tuple[int, int], Tuple[int, int]]) -> Dict[str, dict]:
    """映射表 → `mapping_from_groups` 认识的 overrides（扁平 "季-集" 键）。

    只在分组表达不了源数据（含 S0 特别篇 / 组内顺序被打乱）时才写，
    作用是让「编辑器里再保存一次」也不会把映射改形。
    """
    return {
        f"{season}-{episode}": {"s": virt_s, "e": virt_e}
        for (season, episode), (virt_s, virt_e) in sorted(mapping.items())
    }


def _replay_ok(tmdb_id: int, mapping: Dict[Tuple[int, int], Tuple[int, int]], words: str) -> bool:
    for (season, episode), want in mapping.items():
        if compiler.apply_rules_to_episode(words, season, episode, tmdb_id) != want:
            return False
    return True


def _words_qualified(tmdb_id: int, title: str, mapping: Dict[Tuple[int, int], Tuple[int, int]]) -> str:
    """每个原始季都带 s= 限定，且按季号倒序排列。

    带 s= 是为了让「同一集号在不同季」不会互相命中；倒序是因为
    RenderEngine 逐条就地修改，后面的规则会读到改过的季号，
    倒序可保证「S3→S4」的结果不会被 S4 的规则二次改写。
    """
    lines = [
        f"# [自动分季] {title or tmdb_id} TMDB:{tmdb_id} 依据=SYTMDB {date.today().isoformat()}"
    ]
    seasons = sorted({key[0] for key in mapping}, reverse=True)
    for season in seasons:
        sub = {k: v for k, v in mapping.items() if k[0] == season}
        text = compiler.generate_render_words(tmdb_id, title, "SYTMDB", sub, None, use_includes=False)
        for line in text.splitlines():
            if not line.startswith("@?"):
                continue
            head, sep, tail = line.partition("]}")
            if sep and ";s=" not in head:
                head = head.replace("type=tv;", f"type=tv;s={season};", 1)
            lines.append(head + sep + tail)
    return "\n".join(lines)


def _words_exact(tmdb_id: int, title: str,
                 mapping: Dict[Tuple[int, int], Tuple[int, int]]) -> str:
    """逐集精确写法：一条规则只命中一个原始集，再按「谁的条件等于谁的结果」排序。

    用于源数据是**自定义观看顺序**（组内集号不单调）的情况：区间规则表达不了置换，
    只能一集一条；排序保证前一条的输出不会被后一条当成输入再改一次。
    有环（1→2、2→1）时直接报错，交由上层降级成草稿。
    """
    pairs = [(s, e, vs, ve) for (s, e), (vs, ve) in sorted(mapping.items())
             if (s, e) != (vs, ve)]
    index_of = {(s, e): i for i, (s, e, _vs, _ve) in enumerate(pairs)}
    after: Dict[int, set] = {i: set() for i in range(len(pairs))}  # i 必须排在 after[i] 之前

    for i, (_s, _e, vs, ve) in enumerate(pairs):
        j = index_of.get((vs, ve))
        if j is not None and j != i:
            after[j].add(i)

    state: Dict[int, int] = {}
    order: List[int] = []

    def visit(i: int) -> None:
        flag = state.get(i, 0)
        if flag == 1:
            raise ValueError("剧集组存在环形置换（A→B→A），渲染词无法表达")
        if flag == 2:
            return
        state[i] = 1
        for prev in sorted(after[i]):
            visit(prev)
        state[i] = 2
        order.append(i)

    for i in range(len(pairs)):
        visit(i)

    lines = [
        f"# [自动分季] {title or tmdb_id} TMDB:{tmdb_id} 依据=SYTMDB {date.today().isoformat()}",
        "# 注意: 源剧集组是自定义顺序，只能逐集给规则",
    ]
    for i in order:
        s, e, vs, ve = pairs[i]
        lines.append(
            f"@?{{[tmdbid={tmdb_id};type=tv;s={s};e={e}]}} => {{[s={vs};e={ve}]}}"
        )
    return "\n".join(lines)


def generate_words(tmdb_id: int, title: str,
                   mapping: Dict[Tuple[int, int], Tuple[int, int]]) -> Tuple[str, List[str]]:
    """生成渲染词：紧凑写法 → 带季号倒序 → 逐集精确，三层都过回放自检。"""
    warnings: List[str] = []
    words = compiler.generate_render_words(
        tmdb_id, title, "SYTMDB", mapping, None, use_includes=False
    )
    if _replay_ok(tmdb_id, mapping, words):
        return words, warnings

    qualified = _words_qualified(tmdb_id, title, mapping)
    if _replay_ok(tmdb_id, mapping, qualified):
        warnings.append("源数据存在跨季/S0 重叠，已改为带季号限定并按季号倒序的写法")
        return qualified, warnings

    try:
        exact = _words_exact(tmdb_id, title, mapping)
    except ValueError as e:
        warnings.append(f"{e}；导入后请到工作台手动确认")
        return qualified, warnings
    if _replay_ok(tmdb_id, mapping, exact):
        warnings.append("源剧集组是自定义观看顺序，已改为逐集精确规则")
        return exact, warnings

    warnings.append("规则回放自检未通过，导入后请先用「映射调试器」抽查")
    return exact, warnings


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
    mapping, skipped = mapping_from_group_json(raw)
    if not mapping:
        raise ValueError("剧集组里没有可用的集（全是 S0 特别篇或空分组）")

    names = names_from_group_json(raw)
    groups = groups_from_mapping(mapping, names)
    words, warnings = generate_words(tmdb_id, title, mapping)
    rule_count = len([line for line in words.splitlines() if line.startswith("@?")])
    if len(groups) <= 1:
        warnings.append("只有 1 个剧集组，导入后不会改变任何季号")
    elif rule_count == 0:
        warnings.append("剧集组与 TMDB 原始季结构一致，不会产生任何季号偏移")
    if needs_overrides(mapping):
        warnings.append("源剧集组含 S0 特别篇或组内顺序被打乱，已用 overrides 锁住逐集映射")
    specials = sum(1 for s in skipped if s.get("reason") == "specials")
    duplicates = len(skipped) - specials
    if specials:
        warnings.append(f"跳过 {specials} 集 S0 特别篇（渲染词无法表达季 0）")
    if duplicates:
        warnings.append(f"跳过 {duplicates} 处重复集（源剧集组里同一集出现了两次）")

    replay_ok = _replay_ok(tmdb_id, mapping, words)
    if not replay_ok:
        warnings.append("规则回放自检未通过（源剧集组是循环置换，现有规则引擎表达不了），已强制存为草稿")
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
            "rule_count": rule_count,
            "replay_ok": replay_ok,
            "status": status,
            "skipped_specials": specials,
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
        mapping, skipped = mapping_from_group_json(raw)
        groups = groups_from_mapping(mapping, names_from_group_json(raw))
        return {
            "tmdb_id": tmdb_id,
            "title": str(item.get("name") or f"TMDB {tmdb_id}"),
            "year": item.get("year"),
            "source": item.get("source"),
            "group_count": len(groups),
            "episode_total": len(mapping),
            "skipped_specials": sum(1 for s in skipped if s.get("reason") == "specials"),
            "need_split": len(groups) > 1 and len(mapping) > 0,
        }

    rows = await asyncio.gather(*[one(item) for item in items])
    return [r for r in rows if r], total, errors
