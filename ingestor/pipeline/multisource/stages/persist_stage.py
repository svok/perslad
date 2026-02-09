from typing import List

from ingestor.adapters import BaseStorage
from ingestor.pipeline.multisource.stages.processor_stage import ProcessorStage
from ingestor.core.models.chunk import Chunk


class PersistChunksStage(ProcessorStage):
    def __init__(self, storage: BaseStorage, max_workers: int = 2):
        super().__init__("persist", max_workers)
        self.storage = storage

    async def process(self, chunks: List[Chunk]) -> List[Chunk]:
        await self.storage.save_chunks(chunks)
        return chunks
