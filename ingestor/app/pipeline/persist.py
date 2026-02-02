"""
Stage 6: Persist

Задача: сохранить chunks в storage.
NO LLM.
"""

from typing import List

from infra.logger import get_logger
from ingestor.adapters import BaseStorage
from ingestor.app.storage import Chunk, InMemoryStorage

log = get_logger("ingestor.pipeline.persist")


class PersistStage:
    """
    Сохраняет чанки в storage.
    """

    def __init__(self, storage: BaseStorage) -> None:
        self.storage = storage

    async def run(self, chunks: List[Chunk]) -> None:
        """
        Сохраняет все чанки.
        """
        log.info("persist.start", chunks_count=len(chunks), first_chunk_id=chunks[0].id if chunks else None, first_file_path=chunks[0].file_path[:50] if chunks and chunks[0].file_path else None)
        
        log.info("persist.before_save_chunks")
        await self.storage.save_chunks(chunks)
        log.info("persist.after_save_chunks")
        
        stats = await self.storage.get_stats()
        log.info("persist.complete", stats=stats)
