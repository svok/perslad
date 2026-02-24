from typing import List

from ingestor.pipeline.models.stage_def import StageDef
from ingestor.pipeline.stages.enrich_stage import EnrichStage
from ingestor.pipeline.stages.parse_stage import ParseProcessorStage
from ingestor.pipeline.stages.indexing_stage import IndexingStage
from ingestor.pipeline.stages.incremental_filter_stage import IncrementalFilterStage


class IndexationPipelineBuilder:
    """Отвечает за описание структуры пайплайна"""

    @staticmethod
    def get_default_definitions() -> List[StageDef]:
        return [
            StageDef(
                name="filter",
                stage_class=IncrementalFilterStage,
                factory=lambda ctx: IncrementalFilterStage(ctx.storage, batch_size=100, max_wait=3.0)
            ),
            StageDef(
                name="enrich",
                stage_class=EnrichStage,
                factory=lambda ctx: EnrichStage(ctx.workspace_path, ctx.config.get("enrich_workers", 2))
            ),
            StageDef(
                name="parse",
                stage_class=ParseProcessorStage,
                factory=lambda ctx: ParseProcessorStage(
                    max_workers=ctx.config.get("parse_workers", 1),
                    text_splitter_helper=ctx.text_splitter_helper
                )
            ),
            # Chunk enrichment disabled for now (requires LLM)
            StageDef(
                name="indexing",
                stage_class=IndexingStage,
                factory=lambda ctx: IndexingStage(
                    vector_store=ctx.vector_store,
                    embed_model=ctx.embed_model,
                    storage=ctx.storage,
                    batch_size=100,  # TODO: move to config
                    max_workers=ctx.config.get("indexing_workers", 2)
                )
            ),
            # File summary creation moved out of pipeline (handled separately)
        ]
