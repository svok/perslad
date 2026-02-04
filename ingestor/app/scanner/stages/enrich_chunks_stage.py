from typing import List, Optional

from ingestor.app.pipeline.enrich import EnrichStage as EnrichStageImpl
from ingestor.app.scanner.stages.processor_stage import ProcessorStage
from ingestor.app.storage import Chunk


class EnrichChunksStage(ProcessorStage):
    def __init__(self, llm, lock_manager, max_workers: int = 2):
        super().__init__("enrich_chunks", max_workers)
        self.enricher = EnrichStageImpl(llm, lock_manager)

    async def process(self, batch: List[List[Chunk]]) -> List[Chunk]:
        # Flatten
        all_chunks = [chunk for file_chunks in batch for chunk in file_chunks]
        # Batch processing
        return await self.enricher.run(all_chunks)
