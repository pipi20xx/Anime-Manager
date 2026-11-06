"""季号校准阶段：用 TMDB 季表把规则层解析出的季号/集数校一遍（不依赖 AI）。

三种模式（配置项 `season_resolve_mode`）：
- `off`    ：完全不跑
- `shadow` ：只做推算并写日志，**不修改任何结果**（观察准确率用）
- `on`     ：强证据下不一致时采纳（默认；弱证据只记录不应用）

放在 MatcherStage 之后：那时 `ctx.tmdb_data` 已就绪，多数情况下里面就带 `seasons`。
"""

from __future__ import annotations

import re
import time
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from ..context import RecognitionContext
from ..season_resolver import MIN_FRAGMENT, _name_fragment_score, resolve_season
from tmdbmatefull.manager import TmdbMateFullManager

VALID_MODES = ("off", "shadow", "on")

# 判定理由 → 中文标签（日志 / 前端展示用）
_REASON_LABELS = {
    "no-seasons": "无季表",
    "single-season": "唯一季",
    "single-season-merge": "疑似合并季",
    "name-match": "季名对齐",
    "title-suffix": "标题尾数",
    "marker": "季标",
    "year-match": "年份对齐",
    "boundary:per-season": "季度内边界",
    "boundary:absolute": "绝对集数换算",
    "boundary:year-offset": "跨年续播偏移",
    "boundary:year-calendar": "跨年续播偏移(日历)",
    "latest-by-air-date": "首播日期",
    "ambiguous": "证据不足",
}

# 季名对齐单独解决不了、需要引用 BGM 别名的「兜底理由」
_BGM_RETRY_REASONS = frozenset({
    "boundary:per-season", "boundary:absolute", "latest-by-air-date", "ambiguous",
})

# TMDB genres 里出现这些体裁名即视为动画（BGM 只服务动画）
_ANIMATION_GENRES = frozenset({"动画", "animation", "anime", "アニメ", "アニメーション"})

# 多语言季名缓存：{tmdb_id: (时间戳, seasons)}。
# 补季名要额外两次请求（en-US / ja-JP），同一个剧集不该每次都补。
_NAME_CACHE: Dict[str, Tuple[float, List[Dict[str, Any]]]] = {}
_NAME_TTL = 24 * 3600


class SeasonStage:
    @staticmethod
    def _mode(ctx: RecognitionContext) -> str:
        raw = ctx.kwargs.get("season_resolve_mode")
        if raw is None:
            raw = ctx.config.get("season_resolve_mode", "shadow")
        mode = str(raw or "shadow").strip().lower()
        return mode if mode in VALID_MODES else "shadow"

    @staticmethod
    def _seasons_signature(seasons: List[Dict[str, Any]]) -> tuple:
        """季表指纹，用于判断档案季表是否真的变了（避免无谓写库）。"""
        rows = []
        for item in seasons or []:
            try:
                number = int(item.get("season_number"))
            except (TypeError, ValueError):
                number = -1
            rows.append((
                number,
                item.get("episode_count"),
                str(item.get("name") or ""),
                str(item.get("name_en") or ""),
                str(item.get("name_ja") or ""),
                str(item.get("air_date") or ""),
            ))
        return tuple(sorted(rows))

    @staticmethod
    async def _refresh_archive(
        ctx: RecognitionContext,
        tmdb_id: str,
        media_type: str,
    ):
        """走统一的全量刷新入口（与「元数据资产 → 刷新」同一条路）。

        重新抓取 TMDB 全量数据并整行覆盖入库，只保留 custom_title（固定标题）。
        """
        try:
            await TmdbMateFullManager.fetch_and_ingest(str(tmdb_id), media_type, force=True)
            ctx.log("┣ [季号校准] 🔄 已通过统一入口全量刷新数据中心档案")
        except Exception as exc:
            ctx.log(f"┃ [季号校准] ⚠️ 全量刷新数据中心档案失败: {type(exc).__name__}: {exc}")

    @staticmethod
    async def _get_seasons(ctx: RecognitionContext, mode: str):
        """拿到季表：已有 → 联网详情(7 天缓存) → 本地数据中心档案兜底。

        指纹命中 / 锁定 ID 这两条路给到的 `ctx.tmdb_data` 只有 id + type，
        没有季表；不补取的话季号校准在「记忆加速」场景下等于不存在。

        判断「档案是否过期」不依赖档案里的 status / in_production——那字段
        本身就存在同一份过期档案里，Ended 之后又出新季会被漏掉。这里直接
        拿 7 天缓存的云端季表做基准比对，不一致就触发统一全量刷新。
        """
        seasons = ctx.tmdb_data.get("seasons")
        if isinstance(seasons, list) and seasons:
            return seasons

        tmdb_id = ctx.tmdb_data.get("id") or getattr(ctx.meta, "forced_tmdbid", None)
        media_type = str(ctx.tmdb_data.get("type") or "tv")
        if not tmdb_id:
            return None

        # 1) 读本地永久档案（免费）
        try:
            archive = await ctx.full_db.get_deep_meta(str(tmdb_id), media_type)
        except Exception:
            archive = None
        archive_seasons = None
        if isinstance(archive, dict):
            archive_seasons = archive.get("seasons")
            if not isinstance(archive_seasons, list):
                archive_seasons = None

        # 2) 联网详情作为「新鲜基准」——7 天缓存，多数是 DB 命中，不会真打 API。
        try:
            details = await ctx.tmdb_client.get_subject_details(str(tmdb_id), media_type)
        except Exception as exc:  # 网络异常不该影响识别
            ctx.log(f"┣ [季号校准] ⚠️ 拉取季表失败: {type(exc).__name__}: {exc}")
            details = None
        online_seasons = (details or {}).get("seasons")
        if isinstance(online_seasons, list) and online_seasons:
            ctx.tmdb_data["seasons"] = online_seasons
            if archive_seasons is not None:
                if SeasonStage._seasons_signature(online_seasons) != SeasonStage._seasons_signature(archive_seasons):
                    await SeasonStage._refresh_archive(ctx, str(tmdb_id), media_type)
                    ctx.log("┣ [季号校准] 🔄 档案季表与云端不一致，已触发统一全量刷新")
            else:
                ctx.log("┣ [季号校准] 已补取季表（前置阶段未提供）")
            return online_seasons

        # 3) 联网失败/无季表时，退回档案（过期季表总比没有强）
        if archive_seasons:
            ctx.tmdb_data["seasons"] = archive_seasons
            ctx.log("┣ [季号校准] ⚠️ 联网取季表失败，回退本地数据中心档案（季表可能过期）")
            return archive_seasons
        return None

    @staticmethod
    async def _season_episodes(
        ctx: RecognitionContext,
        seasons: List[Dict[str, Any]],
        file_year: Any,
    ) -> Dict[int, List[Dict[str, Any]]]:
        """拉「首播年早于文件名年份」的季的逐集数据（跨年续播只可能发生在这些季里）。

        只在需要时调用（季号已定 + 有年份 + 有集数），且带 6 小时缓存。
        为避免老剧一次拉一堆，只看最近两年内的季，最多 3 季。
        """
        try:
            year = int(float(file_year))
        except (TypeError, ValueError):
            return {}
        tmdb_id = str(ctx.tmdb_data.get("id") or getattr(ctx.meta, "forced_tmdbid", "") or "")
        if not tmdb_id:
            return {}

        result: Dict[int, List[Dict[str, Any]]] = {}
        ordered = sorted(
            seasons or [],
            key=lambda item: (item.get("season_number") or 0),
        )
        for item in ordered:
            try:
                number = int(item.get("season_number"))
            except (TypeError, ValueError):
                continue
            if number <= 0:
                continue
            air = str(item.get("air_date") or "")
            try:
                season_year = date.fromisoformat(air[:10]).year
            except (TypeError, ValueError):
                continue
            # 首播年不早于文件年份 → 不存在「续播」，跳过
            if season_year >= year or year - season_year > 2:
                continue
            try:
                data = await ctx.tmdb_client.get_season_episodes(tmdb_id, number, ctx.logs)
            except Exception as exc:  # 逐集数据拿不到不该影响识别
                ctx.log(f"┃ [季号校准] ⚠️ 拉取 S{number} 逐集数据失败: {type(exc).__name__}")
                continue
            episodes = (data or {}).get("episodes") or []
            if episodes:
                result[number] = episodes
            if len(result) >= 3:
                break
        if result:
            ctx.log(f"┃ [季号校准] 🔎 已补取逐集播出日期（{'、'.join(f'S{n}' for n in sorted(result))}），用于跨年续播判定")
        return result

    @staticmethod
    def _needs_multilingual_names(
        seasons: List[Dict[str, Any]], title_parts: List[Any]
    ) -> bool:
        """现有季名里有没有一季能和标题对上？全对不上才需要补 en/ja。

        两种常见情况都会判定为「需要补」：
        - zh-CN 下只有「第 2 季」这种序号名；
        - 中文季名有辨识度（「飙马野郎篇」），但文件名是英文（Steel Ball Run），跨语种对不上。
        """
        for item in seasons:
            names = [item.get("name"), item.get("name_en"), item.get("name_ja")]
            if _name_fragment_score(title_parts, names) >= MIN_FRAGMENT:
                return False
        return True

    @staticmethod
    async def _ensure_season_names(
        ctx: RecognitionContext,
        seasons: List[Dict[str, Any]],
        title_parts: List[Any],
    ) -> List[Dict[str, Any]]:
        """补一次 en-US / ja-JP 的季名。

        TMDB 的季名是本地化的：zh-CN 下常常只有「第 2 季」，真正的辨识信息
        （`Cyberpunk: Edgerunners 2`、``actII -Second Season-``）只在 en/ja 里。
        不补这一步，季名对齐这条最强证据在真实链路上等于不存在。
        """
        if not seasons:
            return seasons
        if not SeasonStage._needs_multilingual_names(seasons, title_parts):
            return seasons

        tmdb_id = str(ctx.tmdb_data.get("id") or "")
        if not tmdb_id:
            return seasons

        cached = _NAME_CACHE.get(tmdb_id)
        if cached and time.time() - cached[0] < _NAME_TTL:
            return cached[1]

        fetch = getattr(ctx.tmdb_client, "_fetch", None)
        if fetch is None:
            return seasons

        localized: Dict[int, Dict[str, str]] = {}
        for lang, key in (("en-US", "name_en"), ("ja-JP", "name_ja")):
            try:
                result = await fetch(f"/tv/{tmdb_id}", {"language": lang})
            except Exception as exc:  # 补季名失败不该影响识别
                ctx.log(f"┣ [季号校准] ⚠️ 补季名({lang}) 失败: {type(exc).__name__}")
                continue
            payload = result[0] if isinstance(result, tuple) else result
            for item in (payload or {}).get("seasons") or []:
                number = item.get("season_number")
                name = (item.get("name") or "").strip()
                if number is not None and name:
                    localized.setdefault(int(number), {})[key] = name

        if not localized:
            return seasons

        merged = []
        for item in seasons:
            try:
                number = int(item.get("season_number"))
            except (TypeError, ValueError):
                merged.append(item)
                continue
            merged.append({**item, **localized.get(number, {})})

        _NAME_CACHE[tmdb_id] = (time.time(), merged)
        ctx.log("┣ [季号校准] 已补全多语言季名（现有季名与标题对不上）")
        return merged

    @staticmethod
    def _is_animation(ctx: RecognitionContext) -> bool:
        """只有动画才引用 BGM。"""
        genres = [str(g or "").strip().lower() for g in (ctx.tmdb_data.get("genres") or [])]
        if any(g in _ANIMATION_GENRES for g in genres):
            return True
        if not genres:
            return str(ctx.tmdb_data.get("original_language") or "") == "ja"
        return False

    @staticmethod
    async def _bgm_aliases(ctx: RecognitionContext, title_parts: List[Any]) -> List[str]:
        """用标题关键词去 BGM 拿「别名」（罗马音/汉字/英文等），跨文字桥接用。

        搜索走 `discover()`：它内部有 MetaCacheManager 统一缓存（首页 24h）。
        识别引擎里那个 `search_subject()` 是未缓存的裸 POST，不在这里用。
        """
        keyword = next(
            (p for p in title_parts if isinstance(p, str) and p.strip()),
            None,
        )
        if not keyword:
            return []
        try:
            result = await ctx.bangumi_client.discover(
                {"keyword": keyword, "page": 1, "sort_by": "match"}, ctx
            )
        except Exception as exc:
            ctx.log(f"┃ [季号校准] ⚠️ BGM 搜索失败: {type(exc).__name__}")
            return []
        items = (result or {}).get("results") or []
        if not items:
            return []
        subject_id = items[0].get("id")
        if not subject_id:
            return []
        try:
            return await ctx.bangumi_client.get_subject_aliases(subject_id, ctx)
        except Exception as exc:
            ctx.log(f"┃ [季号校准] ⚠️ BGM 取别名失败: {type(exc).__name__}")
            return []

    @staticmethod
    async def run(ctx: RecognitionContext):
        mode = SeasonStage._mode(ctx)
        if mode == "off":
            return

        meta = ctx.meta
        if not ctx.tmdb_data or meta is None:
            return
        if str(ctx.tmdb_data.get("type") or "tv") != "tv":
            return

        # 标题候选：特权标题最贴近原文，processed_name/en_name/cn_name 可能已被
        # 内核当成噪声剥掉尾部序号（"Cyberpunk Edgerunners 2" → "Cyberpunk Edgerunners"）
        title_parts = [
            getattr(meta, "privileged_title", None),
            meta.processed_name,
            meta.en_name,
            meta.cn_name,
        ]

        seasons = await SeasonStage._get_seasons(ctx, mode)
        if not seasons:
            ctx.log(f"┗ [季号校准] ⏭️ 跳过：TMDB 无季表数据（{mode}）")
            return

        seasons = await SeasonStage._ensure_season_names(ctx, seasons, title_parts)

        decision = resolve_season(
            seasons,
            filename=ctx.filename,
            title_parts=title_parts,
            raw_episode=meta.begin_episode,
            ref_date=ctx.kwargs.get("season_ref_date"),
            file_year=getattr(meta, "year", None),
        )

        # BGM 别名二次判定：TMDB 季名单独解决不了（落到边界/首播日期/模糊）且是动画时，
        # 用标题去 BGM 拿「别名」，把罗马音/汉字/英文别名补进候选再跑一次。
        if decision.reason in _BGM_RETRY_REASONS and SeasonStage._is_animation(ctx):
            aliases = await SeasonStage._bgm_aliases(ctx, title_parts)
            if aliases:
                ctx.log(f"┃ [季号校准] 🪄 引用 BGM 别名（{len(aliases)} 条）二次判定")
                ctx.log("┃   · BGM别名: " + " | ".join(aliases[:6]))
                retry = resolve_season(
                    seasons,
                    filename=ctx.filename,
                    title_parts=[*title_parts, *aliases],
                    raw_episode=meta.begin_episode,
                    ref_date=ctx.kwargs.get("season_ref_date"),
                    file_year=getattr(meta, "year", None),
                )
                # 只有二次判定给出更「实」的证据（季名/季标/年份等）时才替换兜底结果
                if retry.season is not None and retry.reason not in _BGM_RETRY_REASONS:
                    decision = retry

        # 跨年续播偏移：TMDB 把 split cour 并成一季时，新年份续播的集数又会从 1 数起。
        # 需要逐集 air_date（/tv/{id}/season/{n}，6h 缓存），只在「已定季 + 有文件名年份 +
        # 有集数」时才补一步，避免无谓请求。
        if decision.season is not None and getattr(meta, "year", None) and meta.begin_episode:
            episodes_map = await SeasonStage._season_episodes(ctx, seasons, meta.year)
            if episodes_map:
                retry = resolve_season(
                    seasons,
                    filename=ctx.filename,
                    title_parts=title_parts,
                    raw_episode=meta.begin_episode,
                    ref_date=ctx.kwargs.get("season_ref_date"),
                    file_year=getattr(meta, "year", None),
                    season_episodes=episodes_map,
                )
                if retry.reason in ("boundary:year-offset", "boundary:year-calendar"):
                    ctx.log(f"┃ [季号校准] 🧮 {retry.detail}")
                    decision = retry
                    # 有 TMDB 分段标记的偏移本身就是强证据（会直接应用）；
                    # 只有「整季没标记、纯按日历跨年推」的才默认只记录，
                    # 需要显式打开 season_year_offset_apply 才应用。
                    if retry.reason == "boundary:year-calendar" and bool(
                        ctx.config.get("season_year_offset_apply", False)
                    ):
                        decision.confidence = "high"
                        ctx.log("┃ [季号校准] ⚙️ 已按配置把「日历跨年推断」也视为强证据（会改集数）")

        label = _REASON_LABELS.get(decision.reason, decision.reason)

        ctx.season_resolution = {
            "season": decision.season,
            "episode": decision.episode,
            "reason": decision.reason,
            "reason_label": label,
            "confidence": decision.confidence,
            "detail": decision.detail,
            "align": decision.align,
            "mode": mode,
            "before": {
                "season": meta.begin_season,
                "episode": meta.begin_episode,
            },
            "applied": False,
            "applied_reason": "",
        }

        # 比对明细：把「标题候选 × 各季季名」都摆出来，方便人工核对
        if decision.align:
            for line in decision.align.splitlines():
                ctx.log(f"┃   · {line}")

        if decision.season is None:
            ctx.log(f"┗ [季号校准] ⏭️ 未定（{label}）：{decision.detail}")
            return

        current = meta.begin_season
        current_episode = meta.begin_episode
        # 集数也可能被校正（跨年续播偏移 / 绝对集数换算），所以「季号不变」不等于「无需应用」
        episode_change = (
            decision.episode is not None
            and current_episode is not None
            and decision.episode != current_episode
        )
        if current == decision.season and not episode_change:
            ctx.season_resolution["applied_reason"] = "一致"
            ctx.log(f"┗ [季号校准] ✅ 一致 S{decision.season}（{label}）：{decision.detail}")
            return

        target = f"S{decision.season}" + (f"E{decision.episode}" if episode_change else "")
        origin = f"S{current if current is not None else '?'}" + (
            f"E{current_episode}" if current_episode is not None else ""
        )
        ctx.log(
            f"┣ [季号校准] {label}({decision.reason}) → {target}"
            f"（原 {origin}）· {decision.detail}"
        )

        if mode != "on":
            ctx.season_resolution["applied_reason"] = "shadow"
            ctx.log(f"┗ [季号校准] ⚙️ 仅记录不应用（season_resolve_mode={mode}）")
            return

        # on 模式：只自动应用强证据；弱证据（如首播日期推算）仍只记录，避免误改老季
        if decision.confidence != "high":
            ctx.season_resolution["applied_reason"] = "弱证据不应用"
            ctx.log(f"┗ [季号校准] ⚙️ 弱证据（{label}）：仅记录不应用")
            return

        meta.begin_season = decision.season
        if (
            decision.episode is not None
            and decision.episode != meta.begin_episode
            and not getattr(meta, "is_batch", False)
        ):
            ctx.log(
                f"┣ [季号校准] 集数同步: E{meta.begin_episode} → E{decision.episode}"
            )
            meta.begin_episode = decision.episode
        ctx.season_resolution["applied"] = True
        ctx.log("┗ [季号校准] ✅ 已应用")
