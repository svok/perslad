"""
PostgreSQL storage adapter facade.

Uses vector_store for chunks and repositories for summaries.
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
from ingestor.config import storage_config

# Import PGVectorStore - will be available in container where llama-index-vector-stores-postgres is installed
try:
    from llama_index.vector_stores.postgres import PGVectorStore
except ImportError as e:
    # Provide clear error message
    import sys
    print(f"ERROR: Cannot import PGVectorStore. Make sure llama-index-vector-stores-postgres is installed.", file=sys.stderr)
    print(f"Install with: pip install llama-index-vector-stores-postgres>=0.7.3", file=sys.stderr)
    raise ImportError(f"PGVectorStore import failed: {e}") from e


class PostgreSQLStorage(BaseStorage):
    """
    PostgreSQL storage implementation facade.
    Uses ChunkRepository for chunk storage and vector_store for similarity search.
    """

    def __init__(self, operation_timeout: float = 60.0) -> None:
        self._conn = PostgresConnection(operation_timeout)
        self._chunks = ChunkRepository(self._conn)
        self._file_summaries = FileSummaryRepository(self._conn)
        self._module_summaries = ModuleSummaryRepository(self._conn)
        self._stats = StatsRepository(self._conn)
        
        # Initialize vector store if pgvector enabled
        if storage_config.USE_PGVECTOR:
            sync_conn_str = f"postgresql://{storage_config.POSTGRES_USER}:{storage_config.POSTGRES_PASSWORD}@{storage_config.POSTGRES_HOST}:{
            storage_config.POSTGRES_PORT}/{storage_config.POSTGRES_DB}"
            async_conn_str = f"postgresql+asyncpg://{storage_config.POSTGRES_USER}:{storage_config.POSTGRES_PASSWORD}@{storage_config.
            POSTGRES_HOST}:{storage_config.POSTGRES_PORT}/{storage_config.POSTGRES_DB}"
            self._vector_store = PGVectorStore(
                connection_string=sync_conn_str,
                async_connection_string=async_conn_str,
                table_name=storage_config.VECTOR_STORE_TABLE_NAME,
                embed_dim=storage_config.PGVECTOR_DIMENSIONS,
            )
        else:
            self._vector_store = None

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

    async def search_vector(
        self, 
        vector: List[float], 
        top_k: int = 10,
        filter_by_file: Optional[str] = None
    ) -> List[Chunk]:
        """
        Vector similarity search using PGVector via llama_index.
        """
        if self._vector_store is None:
            raise RuntimeError("Vector store not initialized. Enable USE_PGVECTOR in config.")
        
        # Build filters using MetadataFilters
        filters = None
        if filter_by_file:
            from llama_index.core.vector_stores.types import MetadataFilter, MetadataFilters, FilterOperator
            metadata_filter = MetadataFilter(
                key="file_path",
                operator=FilterOperator.EQ,
                value=filter_by_file,
            )
            filters = MetadataFilters(filters=[metadata_filter])
        
        # Build query
        from llama_index.core.vector_stores.types import VectorStoreQuery
        query = VectorStoreQuery(
            query_embedding=vector,
            similarity_top_k=top_k,
            filters=filters,
        )
        
        # Query vector store
        result = await self._vector_store.aquery(query)
        
        # Convert TextNode to Chunk for backwards compatibility
        chunks = []
        for node in result.nodes:
            chunk = Chunk(
                id=node.node_id,
                file_path=node.metadata.get("file_path", ""),
                content=node.text,
                start_line=node.metadata.get("start_line", 0),
                end_line=node.metadata.get("end_line", 0),
                chunk_type=node.metadata.get("chunk_type", ""),
                summary=node.metadata.get("summary"),
                purpose=node.metadata.get("purpose"),
                embedding=node.embedding,
                metadata=node.metadata,
            )
            chunks.append(chunk)
        
        return chunks

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
        """Delete chunks for given file paths from ChunkRepository table."""
        await self._chunks.delete_by_files(file_paths)

    async def delete_file_summaries(self, file_paths: List[str]) -> None:
        await self._file_summaries.delete_by_files(file_paths)

    async def get_file_metadata(self, file_path: str) -> Optional[Dict]:
        return await self._file_summaries.get_metadata(file_path)

    async def delete_file_summary(self, file_path: str) -> None:
        await self._file_summaries.delete(file_path)

    async def update_file_metadata(self, file_path: str, mtime: float, checksum: str) -> None:
        await self._file_summaries.update_metadata(file_path, mtime, checksum)

    async def get_files_metadata(self, file_paths: List[str]) -> Dict[str, Dict]:
        return await self._file_summaries.get_batch_metadata(file_paths)
    
    async def get_embedding_dimension(self) -> int:
        """
        Get embedding dimension from configuration.
        
        For PostgreSQL, this is the dimension specified for the vector store.
        """
        return storage_config.PGVECTOR_DIMENSIONS
         
    # === Stats & Lifecycle ===

    async def get_stats(self) -> Dict:
        return await self._stats.get_stats()

    async def clear(self) -> None:
        """Clear all storage (chunks, file_summaries, module_summaries, stats)."""
        await self._chunks.clear()
        await self._file_summaries.clear()
        await self._module_summaries.clear()
        await self._stats.clear()

    async def get_embedding_dimension(self) -> int:
        """
        Get embedding dimension from configuration.
        
        For PostgreSQL, this is the dimension specified in PGVectorStore.
        """
        return storage_config.PGVECTOR_DIMENSIONS
