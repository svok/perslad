"""
Memory storage adapter.

In-process in-memory storage. Fast and simple for development.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
import asyncio

from ingestor.core.ports.storage import BaseStorage
from ingestor.core.models.chunk import Chunk
from ingestor.core.models.file_summary import FileSummary
from ingestor.core.models.module_summary import ModuleSummary


@dataclass
class MemoryStorage(BaseStorage):
    """
    In-process in-memory storage implementation.
    """

    def __init__(self) -> None:
        self._chunks: Dict[str, Chunk] = {}
        self._file_summaries: Dict[str, FileSummary] = {}
        self._module_summaries: Dict[str, ModuleSummary] = {}
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Explicitly initialize the storage (no-op for memory)."""
        pass

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

    # === File Management ===

    async def delete_chunks_by_file_paths(self, file_paths: List[str]) -> None:
        async with self._lock:
            ids_to_remove = [
                cid for cid, c in self._chunks.items()
                if c.file_path in file_paths
            ]
            for cid in ids_to_remove:
                del self._chunks[cid]

    async def delete_file_summaries(self, file_paths: List[str]) -> None:
        async with self._lock:
            for path in file_paths:
                self._file_summaries.pop(path, None)

    async def get_file_metadata(self, file_path: str) -> Optional[Dict]:
        async with self._lock:
            summary = self._file_summaries.get(file_path)
            if not summary:
                return None
            return {
                "file_path": file_path,
                "mtime": summary.metadata.get("mtime", 0),
                "checksum": summary.metadata.get("checksum", ""),
                "size": 0,
            }

    async def update_file_metadata(self, file_path: str, mtime: float, checksum: str) -> None:
        # In-memory implementation of metadata update
        # For memory storage, we usually update metadata via save_file_summary
        # This is a stub if called directly
        async with self._lock:
            summary = self._file_summaries.get(file_path)
            if summary:
                summary.metadata["mtime"] = mtime
                summary.metadata["checksum"] = checksum
            # Note: if summary doesn't exist, we don't create it here for memory storage
            # as it requires other fields. In real flow, save_file_summary is used.

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
