from dataclasses import dataclass
from typing import List, Callable, Type
from .pipeline_context import StageContext
from .stages.processor_stage import ProcessorStage
from .stages.enrich_stage import EnrichStage
from .stages.parse_stage import ParseProcessorStage
from .stages.enrich_chunks_stage import EnrichChunksStage
from .stages.embed_stage import EmbedChunksStage
from .stages.persist_stage import PersistChunksStage
from .stages.file_summary_stage import FileSummaryStage

@dataclass
class StageDef:
    name: str
    stage_class: Type[ProcessorStage]
    factory: Callable[[StageContext], ProcessorStage]

class PipelineBuilder:
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
                factory=lambda ctx: ParseProcessorStage(ctx.config["parse_workers"])
            ),
            # StageDef(
            #     name="chunk_enrich",
            #     stage_class=EnrichChunksStage,
            #     factory=lambda ctx: EnrichChunksStage(ctx.llm, ctx.lock_manager, ctx.config["chunk_enrich_workers"])
            # ),
            # StageDef(
            #     name="embed",
            #     stage_class=EmbedChunksStage,
            #     factory=lambda ctx: EmbedChunksStage(ctx.embed_url, ctx.embed_api_key, ctx.config["embed_workers"])
            # ),
            # StageDef(
            #     name="persist",
            #     stage_class=PersistChunksStage,
            #     factory=lambda ctx: PersistChunksStage(ctx.storage, ctx.config["persist_workers"])
            # ),
            # StageDef(
            #     name="file_summary",
            #     stage_class=FileSummaryStage,
            #     factory=lambda ctx: FileSummaryStage(ctx.storage, ctx.config["file_summary_workers"])
            # ),
        ]
