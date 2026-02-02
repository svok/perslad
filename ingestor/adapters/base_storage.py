"""
Base storage interface.

All storage implementations (memory, postgres, etc.) must implement this interface.
"""

from abc import ABC, abstractmethod
from typing import Dict
from typing import List, Optional

from ingestor.app.storage import Chunk, FileSummary, ModuleSummary


class BaseStorage(ABC):
    """
    Abstract base class for storage implementations.
    """

    # === Chunks ===

    @abstractmethod
    async def save_chunk(self, chunk: Chunk) -> None:
        """Save a single chunk."""
        pass

    @abstractmethod
    async def save_chunks(self, chunks: List[Chunk]) -> None:
        """Save multiple chunks."""
        pass

    @abstractmethod
    async def get_chunk(self, chunk_id: str) -> Optional[Chunk]:
        """Get a single chunk by ID."""
        pass

    @abstractmethod
    async def get_chunks_by_file(self, file_path: str) -> List[Chunk]:
        """Get all chunks for a file."""
        pass

    @abstractmethod
    async def get_all_chunks(self) -> List[Chunk]:
        """Get all chunks."""
        pass

    # === File Summaries ===

    @abstractmethod
    async def save_file_summary(self, summary: FileSummary) -> None:
        """Save a file summary."""
        pass

    @abstractmethod
    async def get_file_summary(self, file_path: str) -> Optional[FileSummary]:
        """Get a file summary by path."""
        pass

    @abstractmethod
    async def get_all_file_summaries(self) -> List[FileSummary]:
        """Get all file summaries."""
        pass

    # === Module Summaries ===

    @abstractmethod
    async def save_module_summary(self, summary: ModuleSummary) -> None:
        """Save a module summary."""
        pass

    @abstractmethod
    async def get_module_summary(self, module_path: str) -> Optional[ModuleSummary]:
        """Get a module summary by path."""
        pass

    @abstractmethod
    async def get_all_module_summaries(self) -> List[ModuleSummary]:
        """Get all module summaries."""
        pass

    # === File Management ===

    @abstractmethod
    async def delete_chunks_by_file_paths(self, file_paths: List[str]) -> None:
        """Delete all chunks for given file paths."""
        pass

    @abstractmethod
    async def delete_file_summaries(self, file_paths: List[str]) -> None:
        """Delete file summaries for given file paths."""
        pass

    @abstractmethod
    async def get_file_metadata(self, file_path: str) -> Optional[Dict]:
        """Get file metadata (mtime, checksum, size)."""
        pass

    @abstractmethod
    async def update_file_metadata(self, file_path: str, mtime: float, checksum: str) -> None:
        """Update file metadata in database."""
        pass

    # === Stats ===

    @abstractmethod
    async def get_stats(self) -> Dict:
        """Get storage statistics."""
        pass

    @abstractmethod
    async def clear(self) -> None:
        """Clear all storage."""
        pass
