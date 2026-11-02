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

        # 3. 季号校准阶段 (TMDB 季表 → 确定性推算，不依赖 AI；默认影子模式只写日志)
        await SeasonStage.run(self.ctx)

        # 4. 深度字段补全阶段 (Local Override + Enrichment + Auto-Ingest)
        await EnrichmentStage.run(self.ctx)
        
        # 5. 后处理与维护阶段 (Fingerprint Sync + Cache Update)
        await MaintenanceStage.run(self.ctx)
        
        # 6. 渲染与汇报阶段
        return await ResultRenderer.apply_to_context(self.ctx)

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