# -*- coding: utf-8 -*-
"""分季功能 · 真实链路自检（需要项目依赖，不需要数据库）。

    cd backend && python -m season_split.integration_check

与 `selftest.py` 的分工：
- `selftest.py` 只跑纯函数内核（零依赖，任何地方都能跑）；
- 本文件验证「接进项目之后」的链路：表定义、真实 RenderEngine 执行编译出的渲染词、
  `all_render` 合流语义、开关 / scope / 黑名单。

不连数据库（只编译 DDL），不发起网络请求。
"""

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

OK: list = []
FAILED: list = []


def check(name: str, cond: bool, detail="") -> None:
    (OK if cond else FAILED).append(name)
    print(("  ✅ " if cond else "  ❌ ") + name + (f"  → {detail}" if detail and not cond else ""))


TMDB = "100001"

RULES = [
    "# [自动分季] 测试番 TMDB:100001 依据=tvdb",
    "@?{[tmdbid=999999;type=tv;e=13-26]} => {[s=9;e=EP-99]}",   # 别的番：必须跳过
    "@?{[tmdbid=100001;type=tv;e=13-26]} => {[s=2;e=EP-12]}",   # 本番：必须命中
    "@?{[tmdbid=100001;type=tv;includes=2024]} => {[s=3]}",     # 年份消歧：靠文件名
]


def make_packet(season: int = 1, episode: int = 13) -> dict:
    return {
        "success": True,
        "final_result": {
            "title": "测试番", "tmdb_id": TMDB, "year": "2024", "category": "剧集",
            "season": season, "episode": episode, "processed_name": "测试番 - 13",
        },
        "raw_meta": {
            "begin_season": season, "begin_episode": episode, "end_episode": None,
            "is_batch": False, "year": "2024", "type": "tv", "tags": [],
        },
        "tmdb_match": {"id": TMDB, "title": "测试番"},
    }


def case_table() -> None:
    print("\n[1] SeasonSplitRule 表定义（PG 方言）")
    from sqlalchemy.dialects import postgresql
    from sqlalchemy.schema import CreateTable

    from models import SeasonSplitRule

    ddl = str(CreateTable(SeasonSplitRule.__table__).compile(dialect=postgresql.dialect()))
    check("表名 season_split_rules", "season_split_rules" in ddl)
    check("tmdb_id 天然主键（不是 SERIAL）",
          "tmdb_id BIGINT" in ddl and "SERIAL" not in ddl, ddl[:200])
    check("JSONB 列", "JSONB" in ddl)
    check("render_words 为 TEXT", "render_words TEXT" in ddl)


def case_engine() -> None:
    print("\n[2] 真实 RenderEngine 执行分季规则")
    from recognition.render.engine import RenderEngine

    async def run(filename: str, season: int, episode: int):
        logs: list = []
        out = await RenderEngine.apply_rules(make_packet(season, episode), filename, RULES, logs, None)
        return (out["final_result"]["season"], out["final_result"]["episode"]), logs

    got, logs = asyncio.run(run("[Sub] 测试番 - 13.mkv", 1, 13))
    check("S1E13 → S2E1", got == (2, 1), got)
    check("别的番的规则未命中", all("s=9" not in l for l in logs if "命中" in l), logs)
    check("有跳过其他番的日志", any("其他番的分季规则" in l for l in logs), logs)

    got, _ = asyncio.run(run("[Sub] 测试番 - 05.mkv", 1, 5))
    check("S1E5 不被区间规则命中", got == (1, 5), got)

    got, _ = asyncio.run(run("[2024] 测试番 - 05.mkv", 1, 5))
    check("文件名含 2024 → includes 规则生效（S3）", got == (3, 5), got)

    out = asyncio.run(RenderEngine.apply_rules(make_packet(), "[Sub] 测试番 - 13.mkv", [], [], None))
    check("空规则表 = 不改动",
          (out["final_result"]["season"], out["final_result"]["episode"]) == (1, 13))

    # 分季规则带 [SPLIT] 标记 → 日志来源应显示 [分季]，与用户私有规则区分
    logs: list = []
    out = asyncio.run(RenderEngine.apply_rules(
        make_packet(), "[Sub] 测试番 - 13.mkv",
        ["[SPLIT]@?{[tmdbid=100001;type=tv;e=13-26]} => {[s=2;e=EP-12]}"], logs, None))
    check("[SPLIT] 规则仍能命中", (out["final_result"]["season"], out["final_result"]["episode"]) == (2, 1))
    check("日志来源标为 [分季]", any("[Render][分季]" in l for l in logs), logs)


def case_processed_name() -> None:
    print("\n[3] 规则改季集不污染 processed_name")
    from recognition.render.engine import RenderEngine
    from recognition.renderer import ResultRenderer

    check("已移除失效的 _refresh_processed_name（原调用的 Renamer.render_name 不存在）",
          not hasattr(ResultRenderer, "_refresh_processed_name"))
    out = asyncio.run(RenderEngine.apply_rules(make_packet(), "[Sub] 测试番 - 13.mkv", RULES, [], None))
    check("季集已改", (out["final_result"]["season"], out["final_result"]["episode"]) == (2, 1))
    check("processed_name 保持原语义", out["final_result"]["processed_name"] == "测试番 - 13")


def case_compile_replay() -> None:
    print("\n[4] 编译出的渲染词在真实引擎里 == 映射表")
    from datetime import date, timedelta

    from recognition.render.engine import RenderEngine
    from season_split import compiler, grouping

    base = date.fromisoformat("2024-01-05")
    flat = grouping.flatten([{
        "season_number": 1,
        "episodes": [
            {"season_number": 1, "episode_number": i,
             "air_date": (base + timedelta(days=7 * (i - 1))).isoformat(),
             "name": f"第 {i} 集", "episode_type": "standard"}
            for i in range(1, 27)
        ],
    }])
    mapping = compiler.mapping_from_groups(grouping.from_counts(flat, [12, 14]), flat)
    rules = compiler.generate_render_words(TMDB, "测试番", "tvdb", mapping).splitlines()

    async def replay(s: int, e: int):
        out = await RenderEngine.apply_rules(
            make_packet(s, e), "[Sub] 测试番 - %02d.mkv" % e, rules, [], None)
        return out["final_result"]["season"], out["final_result"]["episode"]

    bad = [((s, e), asyncio.run(replay(s, e)), want)
           for (s, e), want in sorted(mapping.items()) if asyncio.run(replay(s, e)) != want]
    check("26 集逐集一致", not bad, bad[:5])


def case_switches() -> None:
    print("\n[5] 开关 / scope / 黑名单（并检查 [SPLIT] 标记）")
    from season_split import store

    rule = "@?{[tmdbid=100001;type=tv;e=13-26]} => {[s=2;e=EP-12]}"
    marked = store.SPLIT_MARKER + rule
    store._ROWS = [{"tmdb_id": 100001, "render_words": "# 注释会被过滤\n" + rule}]
    base = {"season_split_mode": "on",
            "season_split_scope": {"organize": True, "subscription": False, "recognition_test": False},
            "season_split_blacklist": []}

    check("on + organize → 注入（带 [SPLIT] 标记、去掉注释）",
          store.as_render_words(base, entry="organize") == [marked],
          store.as_render_words(base, entry="organize"))
    check("scope 关的入口 → 不注入", store.as_render_words(base, entry="subscription") == [])
    check("preview → 不注入", store.as_render_words({**base, "season_split_mode": "preview"}) == [])
    check("off → 不注入", store.as_render_words({**base, "season_split_mode": "off"}) == [])
    check("黑名单 → 不注入",
          store.as_render_words({**base, "season_split_blacklist": [100001]}) == [])
    store._ROWS = []


def case_context() -> None:
    print("\n[6] RecognitionContext.all_render 合流")
    from config_manager import ConfigManager
    from recognition.context import RecognitionContext

    ctx = RecognitionContext("x.mkv")
    local = ctx.config.get("custom_render_words", [])
    remote = [f"[REMOTE]{r}" for r in ConfigManager.get_cached_rules().get("render", [])]
    check("默认入口 = organize", ctx.entry == "organize")
    check("未启用分季时等于原有规则集", ctx.all_render == list(local) + remote)

    check("显式 all_render 生效",
          RecognitionContext("x.mkv", all_render=["A"]).all_render == ["A"])
    check("entry 透传", RecognitionContext("x.mkv", entry="recognition_test").entry == "recognition_test")
    check("传空列表仍回落到本地+远程（保持原 or 语义）",
          len(RecognitionContext("x.mkv", all_render=[]).all_render) >= len(local))


def main() -> None:
    print("=" * 60)
    print("番剧分季 · 真实链路自检")
    print("=" * 60)
    for fn in (case_table, case_engine, case_processed_name,
               case_compile_replay, case_switches, case_context):
        try:
            fn()
        except Exception as e:  # 单例失败不阻断其余
            import traceback
            traceback.print_exc()
            check(f"{fn.__name__} 执行", False, repr(e))

    print("\n" + "=" * 60)
    print(f"通过 {len(OK)} / 失败 {len(FAILED)}")
    if FAILED:
        for name in FAILED:
            print("  ❌", name)
        raise SystemExit(1)
    print("全部通过 ✅")


if __name__ == "__main__":
    main()
