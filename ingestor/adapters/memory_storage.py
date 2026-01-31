"""
Memory storage adapter.

In-process in-memory storage. Fast and simple for development.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import asyncio

from ingestor.adapters.base_storage import BaseStorage
from ingestor.app.storage import Chunk, FileSummary, ModuleSummary
from ingestor.app.config.storage import storage


@dataclass
class MemoryStorage(BaseStorage):
    """
    In-process in-memory storage implementation.

    Uses same data structure as original InMemoryStorage for consistency.
    """

    def __init__(self) -> None:
        self._chunks: Dict[str, Chunk] = {}
        self._file_summaries: Dict[str, FileSummary] = {}
        self._module_summaries: Dict[str, ModuleSummary] = {}
        self._lock = asyncio.Lock()

    # === Chunks ===

    async def save_chunk(self, chunk: Chunk) -> None:
        async with self._lock:
            self._chunks[chunk.id] = chunk

    async def save_chunks(self, chunks: List[Chunk]) -> None:
        async with self._lock:
            for chunk in chunks:
                self._chunks[chunk.id] = chunk

    async def get_chunk(self, chunk_id: str) -> Optional[Chunk]:
        async with self._lock:
            return self._chunks.get(chunk_id)

    async def get_chunks_by_file(self, file_path: str) -> List[Chunk]:
        async with self._lock:
            return [
                chunk for chunk in self._chunks.values()
                if chunk.file_path == file_path
            ]

    async def get_all_chunks(self) -> List[Chunk]:
        async with self._lock:
            return list(self._chunks.values())

    # === File Summaries ===

    async def save_file_summary(self, summary: FileSummary) -> None:
        async with self._lock:
            self._file_summaries[summary.file_path] = summary

    async def get_file_summary(self, file_path: str) -> Optional[FileSummary]:
        async with self._lock:
            return self._file_summaries.get(file_path)

    async def get_all_file_summaries(self) -> List[FileSummary]:
        async with self._lock:
            return list(self._file_summaries.values())

    # === Module Summaries ===

    async def save_module_summary(self, summary: ModuleSummary) -> None:
        async with self._lock:
            self._module_summaries[summary.module_path] = summary

    async def get_module_summary(self, module_path: str) -> Optional[ModuleSummary]:
        async with self._lock:
            return self._module_summaries.get(module_path)

    async def get_all_module_summaries(self) -> List[ModuleSummary]:
        async with self._lock:
            return list(self._module_summaries.values())

    # === Stats ===

    async def get_stats(self) -> Dict:
        async with self._lock:
            return {
                "chunks": len(self._chunks),
                "file_summaries": len(self._file_summaries),
                "module_summaries": len(self._module_summaries),
                "chunks_with_embeddings": sum(
                    1 for c in self._chunks.values() if c.embedding is not None
                ),
                "chunks_with_summary": sum(
                    1 for c in self._chunks.values() if c.summary is not None
                ),
            }

    async def clear(self) -> None:
        async with self._lock:
            self._chunks.clear()
            self._file_summaries.clear()
            self._module_summaries.clear()
