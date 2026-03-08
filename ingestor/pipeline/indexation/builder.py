from typing import List

from ingestor.pipeline.models.stage_def import StageDef
from ingestor.pipeline.stages.enrich_stage import EnrichStage
from ingestor.pipeline.stages.parse_stage import ParseProcessorStage
from ingestor.pipeline.stages.indexing_stage import IndexingStage
from ingestor.pipeline.stages.incremental_filter_stage import IncrementalFilterStage
from ingestor.pipeline.stages.file_summary_stage import FileSummaryStage
from ingestor.pipeline.stages.enrich_chunks_stage import EnrichChunksStage
from ingestor.pipeline.stages.module_summary_stage import ModuleSummaryStage


class IndexationPipelineBuilder:
    """Отвечает за описание структуры пайплайна"""

    @staticmethod
    def get_default_definitions() -> List[StageDef]:
        return [
            StageDef(
                name="filter",
                stage_class=IncrementalFilterStage,
                factory=lambda ctx: IncrementalFilterStage(
                    storage=ctx.storage,
                    batch_size=ctx.config.get("filter_batch_size", 100),
                    max_wait=ctx.config.get("filter_max_wait", 3.0)
                )
            ),
            StageDef(
                name="enrich",
                stage_class=EnrichStage,
                factory=lambda ctx: EnrichStage(
                    ctx.workspace_path,
                    max_workers=ctx.config.get("enrich_workers", 2)
                )
            ),
            StageDef(
                name="parse",
                stage_class=ParseProcessorStage,
                factory=lambda ctx: ParseProcessorStage(
                    max_workers=ctx.config.get("parse_workers", 1),
                    text_splitter_helper=ctx.text_splitter_helper
                )
            ),
            # Enrich chunks with LLM-generated summaries
            StageDef(
                name="enrich_chunks",
                stage_class=EnrichChunksStage,
                factory=lambda ctx: EnrichChunksStage(
                    llm=ctx.llm,
                    lock_manager=ctx.lock_manager,
                    max_workers=ctx.config.get("enrich_chunks_workers", 2),
                    enable_thinking=False
                )
            ),
            StageDef(
                name="indexing",
                stage_class=IndexingStage,
                factory=lambda ctx: IndexingStage(
                    vector_store=ctx.vector_store,
                    embed_model=ctx.embed_model,
                    batch_size=ctx.config.get("indexing_batch_size", 100),
                    max_workers=ctx.config.get("indexing_workers", 2)
                )
            ),
            # File summary stage - creates file_summary records with LLM-generated summary
            StageDef(
                name="file_summary",
                stage_class=FileSummaryStage,
                factory=lambda ctx: FileSummaryStage(
                    storage=ctx.storage,
                    workspace_path=ctx.workspace_path,
                    llm=ctx.llm,
                    lock_manager=ctx.lock_manager,
                    max_workers=ctx.config.get("file_summary_workers", 2)
                )
            ),
            # Module summary stage - aggregates file summaries into module-level summaries
            StageDef(
                name="module_summary",
                stage_class=ModuleSummaryStage,
                factory=lambda ctx: ModuleSummaryStage(
                    storage=ctx.storage,
                    workspace_path=ctx.workspace_path,
                    llm=ctx.llm,
                    lock_manager=ctx.lock_manager,
                    max_workers=ctx.config.get("file_summary_workers", 2)  # reuse same workers
                )
            ),
        ]
