from typing import List

from ingestor.pipeline.impl.enrich import EnrichStage as EnrichStageImpl
from ingestor.pipeline.multisource.stages.processor_stage import ProcessorStage
from ingestor.core.models.chunk import Chunk


class EnrichChunksStage(ProcessorStage):
    def __init__(self, llm, lock_manager, max_workers: int = 2):
        super().__init__("enrich_chunks", max_workers)
        self.enricher = EnrichStageImpl(llm, lock_manager)

    async def process(self, chunks: List[Chunk]) -> List[Chunk]:
        valid_chunks = [c for c in chunks if c.content and c.content.strip()]
        if not valid_chunks:
            return chunks # Возвращаем как есть, но без обработки

        return await self.enricher.run(valid_chunks)
