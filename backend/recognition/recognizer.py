import time
import logging
from typing import Tuple, Dict, Any, List

from .context import RecognitionContext
from .pipeline.parser import ParserStage
from .pipeline.matcher import MatcherStage
from .pipeline.season import SeasonStage
from .pipeline.enricher import EnrichmentStage
from .pipeline.maintenance import MaintenanceStage
from .renderer import ResultRenderer

class RecognitionWorkflow:
    """
    Recognition Orchestrator (Layer 3)
    High-level pipeline management.
    """
    def __init__(self, ctx: RecognitionContext):
        self.ctx = ctx

    async def run(self) -> Dict[str, Any]:
        # 1. 基础解析阶段 (Kernel + AI + Rules)
        await ParserStage.run(self.ctx)
        
        # 2. 元数据匹配阶段 (Fingerprint + FullDB + Cloud)
        await MatcherStage.run(self.ctx)

        # 2.5 番剧分季自动生成（开关开启且需要拆分时，自动生成并启用规则，当场注入渲染词）
        await self._auto_season_split()

        # 3. 季号校准阶段 (TMDB 季表 → 确定性推算，不依赖 AI；默认影子模式只写日志)
        await SeasonStage.run(self.ctx)

        # 4. 深度字段补全阶段 (Local Override + Enrichment + Auto-Ingest)
        await EnrichmentStage.run(self.ctx)
        
        # 5. 后处理与维护阶段 (Fingerprint Sync + Cache Update)
        await MaintenanceStage.run(self.ctx)
        
        # 6. 渲染与汇报阶段
        return await ResultRenderer.apply_to_context(self.ctx)

    async def _auto_season_split(self) -> None:
        """番剧分季自动生成（识别链路内的同步前置步骤，失败只记日志不影响识别）。"""
        try:
            tmdb_data = self.ctx.tmdb_data or {}
            tmdb_id = tmdb_data.get("id") or getattr(self.ctx.meta, "forced_tmdbid", None)
            if not tmdb_id:
                return
            media_type = str(tmdb_data.get("type") or "").lower()
            if not media_type and self.ctx.meta is not None:
                mt = getattr(self.ctx.meta, "type", None)
                media_type = str(getattr(mt, "value", mt) or "").lower()
            if media_type and media_type != "tv":
                return

            from season_split import service as season_split_service
            from season_split import store as season_split_store

            record = await season_split_service.auto_generate_rule(int(tmdb_id), entry=self.ctx.entry)
            if not record:
                return

            if record.get("blacklisted"):
                self.ctx.log(f"┃ [分季] 🚫 该番无需拆分，已自动加入黑名单（TMDB {tmdb_id}）")
                return

            words = (record.get("render_words") or "").strip()
            if not words:
                return
            for line in words.splitlines():
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    self.ctx.all_render.append(season_split_store.SPLIT_MARKER + stripped)
            if record.get("absolute"):
                self.ctx.log(
                    f"┃ [分季] 🧮 该番无需分季，已按 TMDB 季边界生成「连番号折算」规则并生效"
                    f"（TMDB {tmdb_id}，{len(record.get('groups') or [])} 季；不写 SYTMDB）"
                )
            else:
                self.ctx.log(
                    f"┃ [分季] ⚡ 自动生成规则已生效（TMDB {tmdb_id}，"
                    f"依据 {record.get('reference') or '-'}，{len(record.get('groups') or [])} 季）"
                )
            if record.get("pushed_sytmdb"):
                self.ctx.log(f"┃ [分季] 📡 已自动写入 SYTMDB 剧集组（TMDB {tmdb_id}）")
            elif record.get("push_error"):
                self.ctx.log(f"┃ [分季] ⚠️ SYTMDB 剧集组写入失败（已忽略）: {record.get('push_error')}")
        except Exception as e:
            self.ctx.log(f"┃ [分季] ⚠️ 自动生成失败（已忽略）: {e}")

class MovieRecognizer:
    @staticmethod
    async def recognize_full(filename: str, **kwargs) -> Tuple[Dict[str, Any], List[str]]:
        ctx = RecognitionContext(filename, **kwargs)
        workflow = RecognitionWorkflow(ctx)
        result = await workflow.run()
        return result, ctx.logs

    @staticmethod
    def recognize(filename: str, custom_words: List[str] = [], custom_groups: List[str] = [], force_filename: bool = False) -> Tuple[Any, List[str]]:
        # Backward compatibility only for core recognize
        from recognition_engine.kernel import core_recognize
        logs = []
        meta = core_recognize(filename, custom_words, custom_groups, filename, logs, force_filename=force_filename)
        return meta, logs