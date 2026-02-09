"""
PostgreSQL storage adapter facade.

Delegates to specific repositories.
"""

from typing import List, Optional, Dict

from ingestor.core.ports.storage import BaseStorage
from ingestor.core.models.chunk import Chunk
from ingestor.core.models.file_summary import FileSummary
from ingestor.core.models.module_summary import ModuleSummary

from ingestor.adapters.postgres.connection import PostgresConnection
from ingestor.adapters.postgres.repositories.chunk import ChunkRepository
from ingestor.adapters.postgres.repositories.summary import FileSummaryRepository, ModuleSummaryRepository
from ingestor.adapters.postgres.repositories.stats import StatsRepository


class PostgreSQLStorage(BaseStorage):
    """
    PostgreSQL storage implementation facade.
    """

    def __init__(self, operation_timeout: float = 60.0) -> None:
        self._conn = PostgresConnection(operation_timeout)
        self._chunks = ChunkRepository(self._conn)
        self._file_summaries = FileSummaryRepository(self._conn)
        self._module_summaries = ModuleSummaryRepository(self._conn)
        self._stats = StatsRepository(self._conn)

    async def initialize(self) -> None:
        """Explicitly initialize the storage."""
        await self._conn.initialize()

    async def close(self) -> None:
        await self._conn.close()

    async def __aenter__(self):
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    # === Chunks ===

    async def save_chunk(self, chunk: Chunk) -> None:
        await self._chunks.save(chunk)

    async def save_chunks(self, chunks: List[Chunk]) -> None:
        await self._chunks.save_batch(chunks)

    async def get_chunk(self, chunk_id: str) -> Optional[Chunk]:
        return await self._chunks.get(chunk_id)

    async def get_chunks_by_file(self, file_path: str) -> List[Chunk]:
        return await self._chunks.get_by_file(file_path)

    async def get_all_chunks(self) -> List[Chunk]:
        return await self._chunks.get_all()

    # === File Summaries ===

    async def save_file_summary(self, summary: FileSummary) -> None:
        await self._file_summaries.save(summary)

    async def get_file_summary(self, file_path: str) -> Optional[FileSummary]:
        return await self._file_summaries.get(file_path)

    async def get_all_file_summaries(self) -> List[FileSummary]:
        return await self._file_summaries.get_all()

    # === Module Summaries ===

    async def save_module_summary(self, summary: ModuleSummary) -> None:
        await self._module_summaries.save(summary)

    async def get_module_summary(self, module_path: str) -> Optional[ModuleSummary]:
        return await self._module_summaries.get(module_path)

    async def get_all_module_summaries(self) -> List[ModuleSummary]:
        return await self._module_summaries.get_all()

    # === File Management ===

    async def delete_chunks_by_file_paths(self, file_paths: List[str]) -> None:
        await self._chunks.delete_by_files(file_paths)

    async def delete_file_summaries(self, file_paths: List[str]) -> None:
        await self._file_summaries.delete_by_files(file_paths)

    async def get_file_metadata(self, file_path: str) -> Optional[Dict]:
        return await self._file_summaries.get_metadata(file_path)

    async def update_file_metadata(self, file_path: str, mtime: float, checksum: str) -> None:
        await self._file_summaries.update_metadata(file_path, mtime, checksum)
        
    async def get_embedding_dimension(self) -> int:
        return await self._chunks.get_embedding_dimension()

    # === Stats & Lifecycle ===

    async def get_stats(self) -> Dict:
        return await self._stats.get_stats()

    async def clear(self) -> None:
        await self._stats.clear_all()
