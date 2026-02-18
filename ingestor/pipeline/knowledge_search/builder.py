from typing import List

from ingestor.pipeline.models.stage_def import StageDef
from ingestor.pipeline.stages.embed_chunks_stage import EmbedChunksStage
from ingestor.pipeline.stages.query_parse_stage import QueryParseStage
from ingestor.pipeline.stages.search_db_stage import SearchDBStage


class KnowledgeSearchPipelineBuilder:
    """Билдер пайплайна поиска"""
    
    @staticmethod
    def get_default_definitions() -> List[StageDef]:
        return [
            StageDef(
                name="query_parse",
                stage_class=QueryParseStage,
                factory=lambda ctx: QueryParseStage(
                    max_workers=1,
                    text_splitter_helper=ctx.text_splitter_helper
                )
            ),
            StageDef(
                name="embed",
                stage_class=EmbedChunksStage,
                factory=lambda ctx: EmbedChunksStage(
                    max_workers=ctx.config.get("embed_workers", 2),
                    embed_model=ctx.embed_model
                )
            ),
            StageDef(
                name="search_db",
                stage_class=SearchDBStage,
                factory=lambda ctx: SearchDBStage(
                    ctx.storage,
                    max_workers=1
                )
            )
        ]
