"""
Stage 6: Persist

Задача: сохранить chunks в storage.
NO LLM.
"""

from typing import List

from infra.logger import get_logger
from ingestor.app.storage import Chunk, InMemoryStorage

log = get_logger("ingestor.pipeline.persist")


class PersistStage:
    """
    Сохраняет чанки в storage.
    """

    def __init__(self, storage: InMemoryStorage) -> None:
        self.storage = storage

    async def run(self, chunks: List[Chunk]) -> None:
        """
        Сохраняет все чанки.
        """
        log.info("persist.start", chunks_count=len(chunks))
        
        await self.storage.save_chunks(chunks)
        
        stats = await self.storage.get_stats()
        log.info("persist.complete", stats=stats)
