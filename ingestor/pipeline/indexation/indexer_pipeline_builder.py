from dataclasses import dataclass
from typing import List, Callable, Type

from .indexer_pipeline_context import IndexationPipelineContext
from ingestor.pipeline.stages.embed_stage import EmbedChunksStage
from ingestor.pipeline.stages.enrich_chunks_stage import EnrichChunksStage
from ingestor.pipeline.stages.enrich_stage import EnrichStage
from ingestor.pipeline.stages.file_summary_stage import FileSummaryStage
from ingestor.pipeline.stages.parse_stage import ParseProcessorStage
from ingestor.pipeline.stages.persist_stage import PersistChunksStage
from ingestor.pipeline.base.processor_stage import ProcessorStage


@dataclass
class StageDef:
    name: str
    stage_class: Type[ProcessorStage]
    factory: Callable[[IndexationPipelineContext], ProcessorStage]

class IndexationPipelineBuilder:
    """Отвечает за описание структуры пайплайна"""

    @staticmethod
    def get_default_definitions() -> List[StageDef]:
        return [
            StageDef(
                name="enrich",
                stage_class=EnrichStage,
                factory=lambda ctx: EnrichStage(ctx.workspace_path, ctx.config["enrich_workers"])
            ),
            StageDef(
                name="parse",
                stage_class=ParseProcessorStage,
                factory=lambda ctx: ParseProcessorStage(
                    max_workers=ctx.config["parse_workers"],
                    text_splitter_helper=ctx.text_splitter_helper
                )
            ),
            StageDef(
                name="chunk_enrich",
                stage_class=EnrichChunksStage,
                factory=lambda ctx: EnrichChunksStage(ctx.llm, ctx.lock_manager, ctx.config["chunk_enrich_workers"])
            ),
            StageDef(
                name="embed",
                stage_class=EmbedChunksStage,
                factory=lambda ctx: EmbedChunksStage(ctx.embed_url, ctx.embed_api_key, ctx.config["embed_workers"])
            ),
            StageDef(
                name="persist",
                stage_class=PersistChunksStage,
                factory=lambda ctx: PersistChunksStage(ctx.storage, ctx.config["persist_workers"])
            ),
            StageDef(
                name="file_summary",
                stage_class=FileSummaryStage,
                factory=lambda ctx: FileSummaryStage(ctx.storage, ctx.workspace_path, ctx.config["file_summary_workers"])
            ),
        ]
