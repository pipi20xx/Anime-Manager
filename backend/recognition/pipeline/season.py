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
from typing import Any, Dict, List, Tuple

from ..context import RecognitionContext
from ..season_resolver import MIN_FRAGMENT, _name_fragment_score, resolve_season

VALID_MODES = ("off", "shadow", "on")

# 判定理由 → 中文标签（日志 / 前端展示用）
_REASON_LABELS = {
    "no-seasons": "无季表",
    "single-season": "唯一季",
    "name-match": "季名对齐",
    "title-suffix": "标题尾数",
    "marker": "季标",
    "year-match": "年份对齐",
    "boundary:per-season": "季度内边界",
    "boundary:absolute": "绝对集数换算",
    "latest-by-air-date": "首播日期",
    "ambiguous": "证据不足",
}

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
    async def _get_seasons(ctx: RecognitionContext, mode: str):
        """拿到季表：已有 → 本地数据中心档案 → 联网详情（有缓存）。

        指纹命中 / 锁定 ID 这两条路给到的 `ctx.tmdb_data` 只有 id + type，
        没有季表；不补取的话季号校准在「记忆加速」场景下等于不存在。
        """
        seasons = ctx.tmdb_data.get("seasons")
        if isinstance(seasons, list) and seasons:
            return seasons

        tmdb_id = ctx.tmdb_data.get("id") or getattr(ctx.meta, "forced_tmdbid", None)
        media_type = str(ctx.tmdb_data.get("type") or "tv")
        if not tmdb_id:
            return None

        # 1) 本地数据中心档案（免费）
        try:
            archive = await ctx.full_db.get_deep_meta(str(tmdb_id), media_type)
        except Exception:
            archive = None
        if isinstance(archive, dict):
            seasons = archive.get("seasons")
            if isinstance(seasons, list) and seasons:
                ctx.tmdb_data["seasons"] = seasons
                ctx.log("┣ [季号校准] 季表来自本地数据中心档案")
                return seasons

        # 2) 联网详情（MetaCacheManager 有缓存，重复调用不一定是网络请求）
        try:
            details = await ctx.tmdb_client.get_subject_details(str(tmdb_id), media_type)
        except Exception as exc:  # 网络异常不该影响识别
            ctx.log(f"┣ [季号校准] ⚠️ 拉取季表失败: {type(exc).__name__}: {exc}")
            return None
        seasons = (details or {}).get("seasons")
        if isinstance(seasons, list) and seasons:
            ctx.tmdb_data["seasons"] = seasons
            ctx.log("┣ [季号校准] 已补取季表（前置阶段未提供）")
            return seasons
        return None

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

        # 标题候选：特权标题最贴近原文，processed_name/en_name/cn_name 可能已被
        decision = resolve_season(
            seasons,
            filename=ctx.filename,
            title_parts=title_parts,
            raw_episode=meta.begin_episode,
            ref_date=ctx.kwargs.get("season_ref_date"),
            file_year=getattr(meta, "year", None),
        )

        label = _REASON_LABELS.get(decision.reason, decision.reason)

        ctx.season_resolution = {
            "season": decision.season,
            "episode": decision.episode,
            "reason": decision.reason,
            "reason_label": label,
            "confidence": decision.confidence,
            "detail": decision.detail,
            "mode": mode,
            "before": {
                "season": meta.begin_season,
                "episode": meta.begin_episode,
            },
            "applied": False,
            "applied_reason": "",
        }

        if decision.season is None:
            ctx.log(f"┗ [季号校准] ⏭️ 未定（{label}）：{decision.detail}")
            return

        current = meta.begin_season
        if current == decision.season:
            ctx.season_resolution["applied_reason"] = "一致"
            ctx.log(f"┗ [季号校准] ✅ 一致 S{decision.season}（{label}）：{decision.detail}")
            return

        ctx.log(
            f"┣ [季号校准] {label}({decision.reason}) → S{decision.season}"
            f"（原 S{current if current is not None else '?'}）· {decision.detail}"
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
