"""
Base storage interface.

All storage implementations (memory, postgres, etc.) must implement this interface.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from ingestor.core.models.chunk import Chunk
from ingestor.core.models.file_summary import FileSummary
from ingestor.core.models.module_summary import ModuleSummary


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

    @abstractmethod
    async def search_vector(
        self, 
        vector: List[float], 
        top_k: int = 10,
        filter_by_file: Optional[str] = None
    ) -> List[Chunk]:
        """Vector similarity search."""
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

    @abstractmethod
    async def get_files_metadata(self, file_paths: List[str]) -> Dict[str, Dict]:
        """Get metadata for multiple files in batch."""
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
    async def delete_file_summary(self, file_path: str) -> None:
        """Delete a file summary by path."""
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
    async def initialize(self) -> None:
        """Explicitly initialize the storage (create tables, etc)."""
        pass

    @abstractmethod
    async def clear(self) -> None:
        """Clear all storage."""
        pass
