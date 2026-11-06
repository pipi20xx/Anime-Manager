# -*- coding: utf-8 -*-
"""番剧分季拆分 · 自动生成分组（纯函数，无 I/O）。

五种依据，全部输出同一种结构，供前端编辑器直接绑定：

    groups = [
        {"order": 1, "name": "第 1 季", "start": {"s": 1, "e": 1}, "end": {"s": 1, "e": 12}},
        {"order": 2, "name": "第 2 季", "start": {"s": 1, "e": 13}, "end": {"s": 1, "e": 26}},
    ]

start/end 用原始坐标 (s, e) 表达，区间含义是「摊平后（播出顺序）连续的一段」。
"""

from __future__ import annotations

from datetime import date
from typing import Optional

DEFAULT_GAP_DAYS = 45


def _air_date(ep: dict) -> Optional[date]:
    text = str((ep or {}).get("air_date") or "").strip()
    if len(text) >= 10:
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            return None
    return None


def flatten(raw_seasons: list) -> list:
    """把多个原始季打平成按播出日期排序的集列表（无日期的排最后）。

    与 splitter._flatten_and_sort 同样的排序规则，只是不就地改写原始数据。
    """
    all_eps: list = []
    for season in raw_seasons or []:
        sn = season.get("season_number")
        if sn is None:
            continue
        sn = int(sn)
        for ep in season.get("episodes") or []:
            item = dict(ep)
            item["season_number"] = sn
            all_eps.append(item)
    return sorted(all_eps, key=lambda e: (not bool(e.get("air_date")), e.get("air_date") or ""))


def _bound(ep: dict) -> dict:
    return {"s": int(ep.get("season_number") or 0), "e": int(ep.get("episode_number") or 0)}


def _build(chunks: list, names: Optional[dict] = None) -> list:
    """把若干「集的切片」包装成 groups。空切片自动丢弃。"""
    names = names or {}
    groups = []
    order = 0
    for chunk in chunks:
        if not chunk:
            continue
        order += 1
        groups.append({
            "order": order,
            "name": names.get(order) or f"第 {order} 季",
            "start": _bound(chunk[0]),
            "end": _bound(chunk[-1]),
        })
    return groups


def _chunk_by_count(flat: list, counts: list) -> tuple:
    """按集数切片；返回 (chunks, 剩余集)。"""
    chunks, idx = [], 0
    for n in counts:
        n = int(n or 0)
        if n <= 0:
            continue
        if idx >= len(flat):
            break
        chunks.append(flat[idx: idx + n])
        idx += n
    return chunks, flat[idx:]


# ---------------------------------------------------------------------------
# 五种依据
# ---------------------------------------------------------------------------

def from_counts(flat: list, counts: list, names: Optional[dict] = None) -> list:
    """① 参照源集数（TVDB / Bangumi / CureTMDb 给出的每季集数）。"""
    chunks, rest = _chunk_by_count(flat, counts)
    if rest:
        chunks.append(rest)  # 实际集数多于定义时，多出来的并入一个新季（由调用方告警）
    return _build(chunks, names)


def from_reference_entry(entry, flat: list) -> list:
    """① 的便捷入口：SeriesEntry → groups。"""
    if entry is None or not getattr(entry, "seasons", None):
        return []
    seasons = sorted(entry.seasons, key=lambda s: s.season_number)
    counts = [s.episode_count for s in seasons]
    names = {i + 1: (s.name or f"第 {s.season_number} 季") for i, s in enumerate(seasons)}
    return from_counts(flat, counts, names)


def from_gap(flat: list, gap_days: int = DEFAULT_GAP_DAYS) -> list:
    """② 播出间隔：相邻两集首播间隔 > gap_days 处切一刀。

    split cour 的天然特征（两 cour 之间通常空 1~3 个月），
    在没有可用参照源时这是最稳的一条。
    """
    if not flat:
        return []
    chunks: list = [[flat[0]]]
    prev = _air_date(flat[0])
    for ep in flat[1:]:
        cur = _air_date(ep)
        cut = False
        if prev is not None and cur is not None:
            cut = (cur - prev).days > int(gap_days)
        if cut:
            chunks.append([ep])
        else:
            chunks[-1].append(ep)
        if cur is not None:
            prev = cur
    return _build(chunks)


def from_year(flat: list) -> list:
    """③ 播出年份：跨年处切分（年番 / 跨年番）。"""
    chunks: list = []
    prev_year = None
    for ep in flat:
        d = _air_date(ep)
        year = d.year if d else prev_year
        if not chunks or (year is not None and prev_year is not None and year != prev_year):
            chunks.append([ep])
        else:
            chunks[-1].append(ep)
        if year is not None:
            prev_year = year
    return _build(chunks)


def from_finale(flat: list) -> list:
    """④ 季结局标记：episode_type == "finale" 之后切分。"""
    chunks: list = []
    for ep in flat:
        if not chunks:
            chunks.append([ep])
        else:
            chunks[-1].append(ep)
        if str(ep.get("episode_type") or "") == "finale":
            chunks.append([])
    chunks = [c for c in chunks if c]
    return _build(chunks)


def from_fixed(flat: list, size: int = 12) -> list:
    """⑤ 固定集数：每 N 集一季（手工兜底）。"""
    size = max(1, int(size or 12))
    chunks = [flat[i:i + size] for i in range(0, len(flat), size)]
    return _build(chunks)


def from_cuts(flat: list, cut_after: list) -> list:
    """按「在某一集之后切」生成分组（编辑器手动拆分点的底层实现）。

    cut_after: [(s, e), ...] 在该集之后断开。
    """
    cuts = {(int(s), int(e)) for s, e in (cut_after or [])}
    chunks: list = []
    for ep in flat:
        if not chunks:
            chunks.append([ep])
        else:
            chunks[-1].append(ep)
        if (int(ep.get("season_number") or 0), int(ep.get("episode_number") or 0)) in cuts:
            chunks.append([])
    chunks = [c for c in chunks if c]
    return _build(chunks)


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------

def gaps(flat: list, mark_days: int = 21) -> list:
    """给前端画「间隔虚线」用：[{after: {s,e}, days: n}, ...]"""
    mark_days = int(mark_days or 21)
    out = []
    prev = None
    prev_ep = None
    for ep in flat:
        cur = _air_date(ep)
        if prev is not None and cur is not None and prev_ep is not None:
            delta = (cur - prev).days
            if delta > mark_days:
                out.append({"after": _bound(prev_ep), "days": delta})
        if cur is not None:
            prev = cur
            prev_ep = ep
    return out


def validate(groups: list, flat: list) -> list:
    """检查分组是否覆盖全部集、是否重叠、是否有空组。返回告警文本列表。"""
    warns: list = []
    if not groups:
        return ["没有生成任何分组"]
    order_index = {(int(ep.get("season_number") or 0), int(ep.get("episode_number") or 0)): i
                   for i, ep in enumerate(flat)}
    spans: list = []
    for g in groups:
        try:
            a = order_index[(int(g["start"]["s"]), int(g["start"]["e"]))]
            b = order_index[(int(g["end"]["s"]), int(g["end"]["e"]))]
        except (KeyError, TypeError):
            warns.append(f"第 {g.get('order')} 季的起止集不在 TMDB 数据里")
            continue
        if b < a:
            a, b = b, a
        spans.append((a, b, g.get("order")))
    spans.sort()
    for i in range(1, len(spans)):
        if spans[i][0] <= spans[i - 1][1]:
            warns.append(f"第 {spans[i - 1][2]} 季与第 {spans[i][2]} 季范围重叠")
    covered = set()
    for a, b, _ in spans:
        covered.update(range(a, b + 1))
    missing = [flat[i] for i in range(len(flat)) if i not in covered]
    if missing:
        head = ", ".join(f"S{m.get('season_number')}E{m.get('episode_number')}" for m in missing[:5])
        warns.append(f"有 {len(missing)} 集未被任何分组覆盖（{head}{'…' if len(missing) > 5 else ''}）")
    return warns
