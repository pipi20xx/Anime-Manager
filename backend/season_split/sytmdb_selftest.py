# -*- coding: utf-8 -*-
"""离线自测：`python -m season_split.sytmdb_selftest`（在 backend 目录下运行）。

不联网、不接数据库：只验证「SYTMDB 剧集组 → 映射表 → 渲染词」这段纯函数，
以及导入后规则能否 1:1 回放、编辑器再保存一次会不会改形。
重点覆盖：S0 特别篇照搬、自定义顺序、环形置换（两阶段）、重复集、无改动判定。
"""

from __future__ import annotations

from . import compiler, sytmdb_source

_OK, _FAIL = [], []


def check(name: str, cond: bool, detail: str = ""):
    (_OK if cond else _FAIL).append(name)
    print(("  ✅ " if cond else "  ❌ ") + name + (f"  {detail}" if detail and not cond else ""))


def eq(name: str, got, want):
    check(name, got == want, f"\n     got={got!r}\n     want={want!r}")


def group(order: int, name: str, episodes, season: int = 1):
    return {
        "name": name,
        "order": order,
        "air_date": "",
        "episodes": [
            {"season_number": season, "episode_number": ep, "order": i}
            for i, ep in enumerate(episodes)
        ],
    }


def raw_group(order: int, name: str, coords):
    """coords = [(season, episode), ...]，按给定顺序写进 order 字段。"""
    return {
        "name": name,
        "order": order,
        "air_date": "",
        "episodes": [
            {"season_number": s, "episode_number": e, "order": i}
            for i, (s, e) in enumerate(coords)
        ],
    }


def episode_group(*groups) -> dict:
    return {"id": "0", "description": "", "groups": list(groups)}


def payload_of(raw: dict, tmdb_id: int = 100001, status: str = "active") -> dict:
    return sytmdb_source.build_rule({"id": tmdb_id, "name": "测试番"}, raw, status)


def mapping_of(payload: dict):
    return {
        (int(season), int(episode)): (dst["season"], dst["episode"])
        for season, eps in payload["mapping_json"].items()
        for episode, dst in eps.items()
    }


def replay_ok(payload: dict) -> bool:
    words = payload["render_words"]
    return all(
        compiler.apply_rules_to_episode(words, season, episode, payload["tmdb_id"]) == want
        for (season, episode), want in mapping_of(payload).items()
    )


def resave_matches(payload: dict) -> bool:
    """模拟编辑器保存：只用 groups + overrides + excluded 重算，看是否等价。"""
    mapping = mapping_of(payload)
    again = compiler.mapping_from_groups(
        payload["groups_json"], sorted(mapping), payload["overrides_json"], payload["excluded_json"]
    )
    return again == mapping


# ---------------------------------------------------------------------------
# 用例
# ---------------------------------------------------------------------------

def case_two_seasons():
    print("\n[1] 单季 24 集拆成两季（最常见的 SYTMDB 剧集组）")
    raw = episode_group(group(1, "第 1 季", range(1, 13)), group(2, "第 2 季", range(13, 25)))
    built = payload_of(raw)
    payload, stats = built["payload"], built["stats"]

    eq("映射: S1E13 → S2E1", mapping_of(payload)[(1, 13)], (2, 1))
    eq("映射: S1E24 → S2E12", mapping_of(payload)[(1, 24)], (2, 12))
    eq("覆盖面", stats["episode_total"], 24)
    eq("规则条数", stats["rule_count"], 1)
    check("会改动", stats["will_change"])
    check("渲染词回放 1:1", replay_ok(payload))
    check("再保存一次不变形", resave_matches(payload))
    eq("组名沿用 SYTMDB", payload["groups_json"][1]["name"], "第 2 季")


def case_three_seasons():
    print("\n[2] 60 集拆三季（药屋少女那种）")
    raw = episode_group(
        group(1, "第 1 季", range(1, 25)),
        group(2, "第 2 季", range(25, 49)),
        group(3, "第 3 季", range(49, 61)),
    )
    payload = payload_of(raw)["payload"]
    eq("S1E25 → S2E1", mapping_of(payload)[(1, 25)], (2, 1))
    eq("S1E60 → S3E12", mapping_of(payload)[(1, 60)], (3, 12))
    eq("规则条数", len([l for l in payload["render_words"].splitlines() if l.startswith("@?")]), 2)
    check("渲染词回放 1:1", replay_ok(payload))


def case_specials_included():
    print("\n[3] 组里混了 S0 特别篇（必须照搬，不能丢）")
    raw = episode_group(
        group(1, "第 1 季", range(1, 13)),
        raw_group(2, "第 2 季", [(1, 13), (0, 1), (1, 14)]),
    )
    built = payload_of(raw)
    payload, stats = built["payload"], built["stats"]
    eq("特别篇计数", stats["specials"], 1)
    eq("S1E13 → S2E1", mapping_of(payload)[(1, 13)], (2, 1))
    eq("S0E1 也进了第 2 季（顺序里排第 2）", mapping_of(payload)[(0, 1)], (2, 2))
    eq("S1E14 → S2E3", mapping_of(payload)[(1, 14)], (2, 3))
    eq("总集数含特别篇", stats["episode_total"], 15)
    check("渲染词回放 1:1", replay_ok(payload))
    check("再保存一次不变形（overrides 兜底）", resave_matches(payload))


def case_duplicates():
    print("\n[4] 源里同一集出现两次（SYTMDB 手滑）")
    raw = episode_group(
        raw_group(1, "第 1 季", [(1, 1), (1, 1), (1, 2)]),
        group(2, "第 2 季", [3, 4]),
    )
    payload, stats = payload_of(raw)["payload"], payload_of(raw)["stats"]
    eq("去重后集数", stats["episode_total"], 4)
    eq("重复集计数", stats["duplicates"], 1)
    eq("S1E2 → S1E2（重复集不占编号）", mapping_of(payload)[(1, 2)], (1, 2))
    eq("S1E3 → S2E1", mapping_of(payload)[(1, 3)], (2, 1))
    check("渲染词回放 1:1", replay_ok(payload))


def case_single_group_reorder():
    print("\n[5] 只有一个组，只是 DIY 调了顺序（旧实现会误判「无需拆分」）")
    raw = episode_group(raw_group(1, "第 1 季", [(1, 2), (1, 1), (1, 3)]))
    built = payload_of(raw)
    payload, stats = built["payload"], built["stats"]
    eq("组数", stats["group_count"], 1)
    check("仍然判定「会改动」", stats["will_change"])
    eq("S1E2 → S1E1", mapping_of(payload)[(1, 2)], (1, 1))
    eq("S1E1 → S1E2", mapping_of(payload)[(1, 1)], (1, 2))
    check("渲染词回放 1:1", replay_ok(payload))


def case_cyclic_order():
    print("\n[6] 环形置换（1→3→2→1，单遍规则表达不了，用临时季号两阶段）")
    raw = episode_group(raw_group(1, "第 1 季", [(1, 2), (1, 3), (1, 1)]))
    built = payload_of(raw, status="active")
    payload, stats = built["payload"], built["stats"]
    check("没有降级成草稿", stats["status"] == "active", stats["status"])
    eq("S1E2 → S1E1", mapping_of(payload)[(1, 2)], (1, 1))
    eq("S1E3 → S1E2", mapping_of(payload)[(1, 3)], (1, 2))
    eq("S1E1 → S1E3", mapping_of(payload)[(1, 1)], (1, 3))
    eq("两阶段 → 规则翻倍", stats["rule_count"], 6)
    check("渲染词回放 1:1", replay_ok(payload))


def case_identity():
    print("\n[7] 剧集组与 TMDB 原始季一致（不该产生偏移）")
    raw = episode_group(group(1, "第 1 季", range(1, 13)), group(2, "第 2 季", range(1, 13), season=2))
    stats = payload_of(raw)["stats"]
    check("判定为无改动", not stats["will_change"])
    eq("无规则", stats["rule_count"], 0)
    check("给出提示", any("一致" in w for w in stats["warnings"]), str(stats["warnings"]))


def case_normalize():
    print("\n[8] 剧集组清洗（写回 SYTMDB 时用）")
    raw = episode_group(group(1, "第一季", [3, 1, 2]), group(2, "第二季", [4]))
    normalized = sytmdb_source.normalize_group_json(raw, 42)
    eq("episodes 顺序遵循源 order（自定义观看顺序不能被排序覆盖）",
       [e["episode_number"] for e in normalized["groups"][0]["episodes"]], [3, 1, 2])
    eq("组内 order 重新编号", [e["order"] for e in normalized["groups"][0]["episodes"]], [0, 1, 2])
    eq("id 为字符串", normalized["id"], "42")
    eq("组名保留", normalized["groups"][0]["name"], "第一季")


def main():
    for case in (
        case_two_seasons, case_three_seasons, case_specials_included,
        case_duplicates, case_single_group_reorder, case_cyclic_order,
        case_identity, case_normalize,
    ):
        case()
    print(f"\n通过 {len(_OK)} 项，失败 {len(_FAIL)} 项")
    if _FAIL:
        print("失败项：" + "、".join(_FAIL))
    return 1 if _FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
