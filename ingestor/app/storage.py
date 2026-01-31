"""
Storage layer для ingestor.

MVP: in-memory хранилище.
Будущее: Postgres, vector DB, etc.

ВАЖНО: storage — внутренняя деталь ingestor.
Agent НИЧЕГО об этом не знает.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import asyncio

from infra.logger import get_logger

log = get_logger("ingestor.storage")


@dataclass
class Chunk:
    """Базовый чанк кода/документации."""
    id: str
    file_path: str
    content: str
    start_line: int
    end_line: int
    chunk_type: str  # "code", "doc", "config"
    
    # Enrichment (from local LLM)
    summary: Optional[str] = None
    purpose: Optional[str] = None
    
    # Embeddings
    embedding: Optional[List[float]] = None
    
    # Metadata
    metadata: Dict = field(default_factory=dict)


@dataclass
class FileSummary:
    """Суммаризация на уровне файла."""
    file_path: str
    summary: str
    chunk_ids: List[str]
    metadata: Dict = field(default_factory=dict)


@dataclass
class ModuleSummary:
    """Суммаризация на уровне модуля/пакета."""
    module_path: str
    summary: str
    file_paths: List[str]
    metadata: Dict = field(default_factory=dict)


class InMemoryStorage:
    """
    In-memory хранилище для MVP.
    
    Позже можно заменить на Postgres/vector DB
    без изменения интерфейса.
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
            log.debug("storage.chunk.saved", chunk_id=chunk.id)

    async def save_chunks(self, chunks: List[Chunk]) -> None:
        async with self._lock:
            for chunk in chunks:
                self._chunks[chunk.id] = chunk
            log.info("storage.chunks.saved", count=len(chunks))

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
            log.debug("storage.file_summary.saved", file=summary.file_path)

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
            log.debug("storage.module_summary.saved", module=summary.module_path)

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
        """Очистка хранилища (для тестов/перезапуска)."""
        async with self._lock:
            self._chunks.clear()
            self._file_summaries.clear()
            self._module_summaries.clear()
            log.info("storage.cleared")
