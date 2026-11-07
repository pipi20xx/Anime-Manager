# -*- coding: utf-8 -*-
"""离线自测：`python -m season_split.selftest`（在 backend 目录下运行）。

不联网、不接数据库、不依赖项目其他模块 —— 只验证算法与编译器。
覆盖：移植过来的 Lens 主流程、五种分组依据、排除集、去重、规则语义回放。
"""

from __future__ import annotations

import asyncio
import re
from datetime import date, timedelta

from . import compiler, grouping
from .models import SeasonEntry, SeriesEntry
from .splitter import SeasonSplitter, remove_duplicate_episodes

TMDB_ID = 100001
_OK, _FAIL = [], []


def check(name: str, cond: bool, detail: str = ""):
    (_OK if cond else _FAIL).append(name)
    print(("  ✅ " if cond else "  ❌ ") + name + (f"  {detail}" if detail and not cond else ""))


def eq(name: str, got, want):
    check(name, got == want, f"\n     got={got!r}\n     want={want!r}")


# ---------------------------------------------------------------------------
# 规则语义回放：直接用生产代码里的 apply_rules_to_episode（与 RenderEngine 语义对齐）
# ---------------------------------------------------------------------------

def simulate(rules_text: str, season: int, episode: int, tmdb_id=TMDB_ID, filename: str = ""):
    return compiler.apply_rules_to_episode(rules_text, season, episode, tmdb_id,
                                           filename=filename)


# ---------------------------------------------------------------------------
# 假数据
# ---------------------------------------------------------------------------

def weekly(start: str, count: int, season: int = 1, finale_at=(), gap_after=None):
    """生成逐集数据；gap_after={集号: 额外天数}。"""
    base = date.fromisoformat(start)
    eps, cur = [], base
    for i in range(1, count + 1):
        if i > 1:
            cur = cur + timedelta(days=7)
        if gap_after and (i - 1) in gap_after:
            cur = cur + timedelta(days=gap_after[i - 1])
        eps.append({
            "episode_number": i,
            "season_number": season,
            "air_date": cur.isoformat(),
            "name": f"第 {i} 集",
            "episode_type": "finale" if i in finale_at else "standard",
            "overview": "",
            "still_path": "",
            "vote_average": 0,
            "id": season * 1000 + i,
        })
    return {"season_number": season, "episodes": eps, "name": f"第 {season} 季"}


class FakeTMDB:
    def __init__(self, tv_show, seasons: dict):
        self.tv_show = tv_show
        self.seasons = seasons

    async def tv_detail(self, tmdb_id):
        return self.tv_show if int(tmdb_id) == int(self.tv_show["id"]) else None

    async def season_detail(self, tmdb_id, season):
        return self.seasons.get(int(season))

    async def movie_detail(self, movie_id):
        return None


class FakeTVDB:
    def __init__(self, entry):
        self.entry = entry

    async def get_series_entry(self, tvdb_id):
        return self.entry


class NullBangumi:
    async def search(self, *a, **k):
        return []

    def extract_season_number(self, *a, **k):
        return 1

    async def season_info(self, item):
        return None

    async def is_first_episode_sequential(self, sid):
        return True


def tv_show_single_season(count: int):
    return {
        "id": TMDB_ID,
        "name": "测试番",
        "original_name": "Test Anime",
        "first_air_date": "2024-01-05",
        "origin_country": ["JP"],
        "genres": [{"id": 16, "name": "动画"}],
        "number_of_seasons": 1,
        "seasons": [{"season_number": 1, "episode_count": count,
                     "air_date": "2024-01-05", "name": "第 1 季"}],
        "external_ids": {"tvdb_id": 555},
        "vote_average": 8.0,
        "poster_path": "/p.jpg",
        "overview": "简介",
    }


# ---------------------------------------------------------------------------
# 用例
# ---------------------------------------------------------------------------

def case_lens_pipeline():
    print("\n[1] Lens 主流程移植：TMDB S1×26 + TVDB 定义 12+14")
    tv_show = tv_show_single_season(26)
    tmdb = FakeTMDB(tv_show, {1: weekly("2024-01-05", 26)})
    tvdb = FakeTVDB(SeriesEntry("测试番", [SeasonEntry(1, 12, "第 1 季"), SeasonEntry(2, 14, "第 2 季")]))
    logs = []
    sp = SeasonSplitter(tmdb, lambda lvl, msg: logs.append(f"{lvl}:{msg}"))

    logic = asyncio.run(sp.process_tv(TMDB_ID, {}, ["tvdb"], tvdb, NullBangumi(), False))
    check("识别为需要拆分", logic is not None)
    eq("拆出 2 个虚拟季", len(logic.seasons), 2)
    eq("S1 集数=12", logic.seasons[0].episode_count(), 12)
    eq("S2 集数=14", logic.seasons[1].episode_count(), 14)

    org = logic.org_map()
    eq("S1E13 → S2E1", org[(1, 13)], (2, 1))
    eq("S1E26 → S2E14", org[(1, 26)], (2, 14))
    eq("S1E1 不变", org[(1, 1)], (1, 1))
    eq("依据标注=tvdb", sp.last_reference_name, "tvdb")

    words = compiler.generate_render_words(TMDB_ID, "测试番", "tvdb", org)
    expect = f"@?{{[tmdbid={TMDB_ID};type=tv;e=13-26]}} => {{[s=2;e=EP-12]}}"
    check("生成 1 条分段规则", expect in words, words)
    check("没有多余的季限定", "s=1;" not in words, words)

    # 回放：规则跑出来的结果必须与映射表完全一致
    bad = []
    for (s, e), (vs, ve) in org.items():
        if simulate(words, s, e) != (vs, ve):
            bad.append(((s, e), simulate(words, s, e), (vs, ve)))
    eq("规则回放 == 映射表（26 集）", bad, [])

    # 组 JSON
    gj = compiler.logic_to_group_json(logic, TMDB_ID)
    eq("剧集组 2 组", len(gj["groups"]), 2)
    eq("组2首集=S1E13", gj["groups"][1]["episodes"][0],
       {"episode_number": 13, "season_number": 1, "order": 0})
    eq("组2末集=S1E26", gj["groups"][1]["episodes"][-1],
       {"episode_number": 26, "season_number": 1, "order": 13})


def case_consistent():
    print("\n[2] 结构本来就一致：不产生任何计划")
    tv_show = tv_show_single_season(12)
    tmdb = FakeTMDB(tv_show, {1: weekly("2024-01-05", 12)})
    tvdb = FakeTVDB(SeriesEntry("测试番", [SeasonEntry(1, 12)]))
    sp = SeasonSplitter(tmdb, lambda *a: None)
    logic = asyncio.run(sp.process_tv(TMDB_ID, {}, ["tvdb"], tvdb, NullBangumi(), False))
    eq("返回 None（无需拆分）", logic, None)


def case_gap_grouping():
    print("\n[3] 间隔切分：12 集 + 90 天空档 + 14 集 → 2 组，且与参照源结果一致")
    raw = [weekly("2024-01-05", 26, gap_after={12: 90})]
    flat = grouping.flatten(raw)
    eq("摊平 26 集", len(flat), 26)
    eq("第 13 集日期跳空", flat[12]["air_date"], "2024-06-27")

    groups = grouping.from_gap(flat, 45)
    eq("切出 2 组", len(groups), 2)
    eq("切点在 S1E12 之后", groups[0]["end"], {"s": 1, "e": 12})
    eq("第 2 组起点", groups[1]["start"], {"s": 1, "e": 13})
    eq("分组无告警", grouping.validate(groups, flat), [])

    mapping = compiler.mapping_from_groups(groups, flat)
    eq("S1E13 → S2E1", mapping[(1, 13)], (2, 1))
    eq("S1E26 → S2E14", mapping[(1, 26)], (2, 14))

    words = compiler.generate_render_words(
        TMDB_ID, "测试番", "gap", mapping, compiler.season_years_from_mapping(mapping, flat))
    check("等价于参照源生成的规则",
          f"@?{{[tmdbid={TMDB_ID};type=tv;e=13-26]}} => {{[s=2;e=EP-12]}}" in words, words)
    check("同一年份对应两季 → 不生成 includes 规则（Lens 原样行为）",
          "未生成 includes 规则" in words, words)

    bad = [((s, e), simulate(words, s, e), v) for (s, e), v in mapping.items()
           if simulate(words, s, e) != v]
    eq("规则回放 == 映射表", bad, [])


def case_includes_year():
    print("\n[3b] 跨年番：按首播年份生成 includes 规则（匹配文件名，不依赖 meta.year）")
    raw = [weekly("2023-10-06", 12), weekly("2024-01-05", 14, season=1)]
    # 跨年时 TMDB 仍是 S1，用集号写死第二 cour
    for i, ep in enumerate(raw[1]["episodes"], start=13):
        ep["episode_number"] = i
    flat = grouping.flatten(raw)
    groups = grouping.from_year(flat)
    eq("按年份切出 2 组", len(groups), 2)
    mapping = compiler.mapping_from_groups(groups, flat)
    years = compiler.season_years_from_mapping(mapping, flat)
    eq("第 2 季首播年份=2024", years.get(2), 2024)

    words = compiler.generate_render_words(TMDB_ID, "测试番", "gap", mapping, years)
    check("含 includes=2023 规则", "includes=2023]} => {[s=1]}" in words, words)
    check("含 includes=2024 规则", "includes=2024]} => {[s=2]}" in words, words)
    eq("文件名含 2024 → 季号=2", simulate(words, 1, 5, filename="[2024] 测试番 - 05"), (2, 5))
    eq("文件名无年份 → 不纠正", simulate(words, 1, 5), (1, 5))


def case_exclusion():
    print("\n[4] 排除集（总集篇 S1E12）：留在洞里的集不动，后续集号不串")
    raw = [weekly("2024-01-05", 26, gap_after={12: 90})]
    flat = grouping.flatten(raw)
    groups = grouping.from_gap(flat, 45)
    mapping = compiler.mapping_from_groups(groups, flat, excluded=[(1, 12)])
    check("被排除的集不在映射里", (1, 12) not in mapping)
    eq("S1E13 仍然是 S2E1", mapping[(1, 13)], (2, 1))

    words = compiler.generate_render_words(TMDB_ID, "测试番", "gap", mapping)
    eq("排除集回放后保持原编号", simulate(words, 1, 12), (1, 12))
    eq("排除集之后仍正确", simulate(words, 1, 14), (2, 2))
    eq("未覆盖区间不出规则（1-11 段偏移为 0）",
       [l for l in words.splitlines() if l.startswith("@?")],
       [f"@?{{[tmdbid={TMDB_ID};type=tv;e=13-26]}} => {{[s=2;e=EP-12]}}"])


def case_three_seasons():
    print("\n[5] 三季：36 集按 12+12+12 重灌")
    raw = [weekly("2024-01-05", 36)]
    flat = grouping.flatten(raw)
    groups = grouping.from_counts(flat, [12, 12, 12])
    eq("3 组", len(groups), 3)
    mapping = compiler.mapping_from_groups(groups, flat)
    eq("S1E25 → S3E1", mapping[(1, 25)], (3, 1))
    words = compiler.generate_render_words(TMDB_ID, "测试番", "manual", mapping)
    rules = [l for l in words.splitlines() if l.startswith("@?")]
    eq("2 条规则", len(rules), 2)
    bad = [((s, e), simulate(words, s, e), v) for (s, e), v in mapping.items()
           if simulate(words, s, e) != v]
    eq("规则回放 == 映射表", bad, [])


def case_dedupe():
    print("\n[6] 同日跨季去重")
    s1 = weekly("2024-01-05", 12)
    s2 = weekly("2024-03-22", 1, season=2)  # 与 S1E12 同一天
    s2["episodes"][0]["name"] = "更完整的名字"
    s2["episodes"][0]["overview"] = "有简介"
    merged = remove_duplicate_episodes([s1, s2])
    eq("去重后只剩 1 季", len(merged), 1)
    eq("保留最早槽位的季集号", (merged[0]["episodes"][11]["season_number"],
                              merged[0]["episodes"][11]["episode_number"]), (1, 12))
    eq("内容取更完整者", merged[0]["episodes"][11]["name"], "更完整的名字")


def case_finale_and_year():
    print("\n[7] finale 切分 / 年份切分 / 固定集数")
    flat = grouping.flatten([weekly("2024-01-05", 24, finale_at=(12, 24))])
    groups = grouping.from_finale(flat)
    eq("finale 切成 2 组", len(groups), 2)
    eq("第 1 组止于 E12", groups[0]["end"], {"s": 1, "e": 12})

    flat2 = grouping.flatten([weekly("2023-10-06", 26)])
    gy = grouping.from_year(flat2)
    eq("跨年切成 2 组", len(gy), 2)
    eq("第一组止于 2023 最后一集", gy[0]["end"]["e"], 13)

    gf = grouping.from_fixed(flat2, 13)
    eq("固定 13 集 → 2 组", len(gf), 2)


def case_roundtrip():
    print("\n[8] 映射 ⇄ 分组 / JSON 往返")
    raw = [weekly("2024-01-05", 26, gap_after={12: 90})]
    flat = grouping.flatten(raw)
    mapping = compiler.mapping_from_groups(grouping.from_gap(flat, 45), flat)

    back = compiler.groups_from_mapping(mapping)
    eq("回推 2 组", len(back), 2)
    eq("回推第 2 组起点", back[1]["start"], {"s": 1, "e": 13})

    dumped = compiler.dump_mapping(mapping)
    eq("dump 格式", dumped["1"]["13"], {"season": 2, "episode": 1})
    eq("parse 往返", compiler.parse_mapping_json(dumped), mapping)

    gj = compiler.group_json_from_mapping(TMDB_ID, mapping)
    eq("剧集组 2 组", len(gj["groups"]), 2)
    eq("剧集组 order 从 0 起", gj["groups"][1]["episodes"][0]["order"], 0)


def case_overflow():
    print("\n[9] 定义集数少于实际：多出来的并入新季（不静默丢集）")
    flat = grouping.flatten([weekly("2024-01-05", 26)])
    groups = grouping.from_counts(flat, [12, 12])
    eq("3 组（定义 2 组 + 溢出 1 组）", len(groups), 3)
    eq("溢出组 2 集", (groups[2]["start"], groups[2]["end"]),
       ({"s": 1, "e": 25}, {"s": 1, "e": 26}))
    check("validate 不报未覆盖", grouping.validate(groups, flat) == [], grouping.validate(groups, flat))


def case_absolute():
    print("\n[10] 连番号折算（TMDB 已分季，发布侧按 1..N 连续编号）")
    flat = grouping.flatten([weekly("2024-01-05", 12, season=1),
                             weekly("2025-01-10", 12, season=2)])

    lines = compiler.absolute_rule_lines(TMDB_ID, flat)
    eq("只生成 1 条跨季规则", len(lines), 1)
    eq("规则文本", lines[0], f"@?{{[tmdbid={TMDB_ID};type=tv;e=13-24]}} => {{[s=2;e=EP-12]}}")

    rules = "\n".join(lines)
    eq("第 13 集 → S2E1", simulate(rules, 1, 13), (2, 1))
    eq("第 24 集 → S2E12", simulate(rules, 1, 24), (2, 12))
    eq("第 12 集 不变", simulate(rules, 1, 12), (1, 12))
    eq("S2E1 不被二次改写", simulate(rules, 2, 1), (2, 1))
    eq("第 25 集 不变（TMDB 没有这一集）", simulate(rules, 1, 25), (1, 25))

    # 单季：连番号与 TMDB 坐标一致，不该生成任何规则
    flat_one = grouping.flatten([weekly("2024-01-05", 24, season=1)])
    eq("单季 → 不生成规则", compiler.absolute_rule_lines(TMDB_ID, flat_one), [])

    # 三季：第二条规则
    flat_three = grouping.flatten([weekly("2024-01-05", 12, season=1),
                                   weekly("2024-10-04", 12, season=2),
                                   weekly("2025-10-03", 12, season=3)])
    lines_three = compiler.absolute_rule_lines(TMDB_ID, flat_three)
    eq("三季 → 2 条规则", len(lines_three), 2)
    eq("三季第 25 集 → S3E1", simulate("\n".join(lines_three), 1, 25), (3, 1))

    # 自动生成用的是「恒等分组 + 追加渲染词」，所以分组回编译必须还是恒等映射
    identity = {(int(e["season_number"]), int(e["episode_number"])):
                (int(e["season_number"]), int(e["episode_number"])) for e in flat}
    groups = compiler.groups_from_mapping(identity)
    eq("恒等分组 = 2 段", len(groups), 2)
    eq("第 1 段起止", (groups[0]["start"], groups[0]["end"]),
       ({"s": 1, "e": 1}, {"s": 1, "e": 12}))
    eq("第 2 段起止", (groups[1]["start"], groups[1]["end"]),
       ({"s": 2, "e": 1}, {"s": 2, "e": 12}))
    eq("恒等分组回编译 = 恒等映射", compiler.mapping_from_groups(groups, flat), identity)


def main():
    print("=" * 72)
    print("番剧分季 · 离线自测")
    print("=" * 72)
    for fn in (case_lens_pipeline, case_consistent, case_gap_grouping, case_includes_year,
               case_exclusion, case_three_seasons, case_dedupe, case_finale_and_year,
               case_roundtrip, case_overflow, case_absolute):
        fn()

    print("\n" + "=" * 72)
    print(f"通过 {len(_OK)} / 失败 {len(_FAIL)}")
    if _FAIL:
        for name in _FAIL:
            print("  ❌", name)
        raise SystemExit(1)
    print("全部通过 ✅")


if __name__ == "__main__":
    main()
