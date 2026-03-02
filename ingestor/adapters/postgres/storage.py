"""
PostgreSQL storage adapter facade.

Uses PGVectorStore for chunks (vector storage) and repositories for summaries.
No separate chunks table - all chunks are in the vector store table.
"""

from typing import List, Optional, Dict

from ingestor.core.ports.storage import BaseStorage
from ingestor.core.models.chunk import Chunk
from ingestor.core.models.file_summary import FileSummary
from ingestor.core.models.module_summary import ModuleSummary

from ingestor.adapters.postgres.connection import PostgresConnection
from ingestor.adapters.postgres.repositories.summary import FileSummaryRepository, ModuleSummaryRepository
from ingestor.adapters.postgres.repositories.stats import StatsRepository
from ingestor.config import storage_config

# Import PGVectorStore - will be available in container where llama-index-vector-stores-postgres is installed
try:
    from llama_index.vector_stores.postgres import PGVectorStore
    from llama_index.core.vector_stores.types import (
        MetadataFilter, 
        MetadataFilters, 
        FilterOperator,
        VectorStoreQuery
    )
except ImportError as e:
    # Provide clear error message
    import sys
    print(f"ERROR: Cannot import PGVectorStore. Make sure llama-index-vector-stores-postgres is installed.", file=sys.stderr)
    print(f"Install with: pip install llama-index-vector-stores-postgres>=0.7.3", file=sys.stderr)
    raise ImportError(f"PGVectorStore import failed: {e}") from e


class PostgreSQLStorage(BaseStorage):
    """
    PostgreSQL storage implementation using PGVectorStore for chunks.
    
    Chunks are stored in the vector store table (chunks_vectors) with metadata.
    File and module summaries are stored in separate relational tables.
    """

    def __init__(self) -> None:
        self._conn = PostgresConnection()
        self._file_summaries = FileSummaryRepository(self._conn)
        self._module_summaries = ModuleSummaryRepository(self._conn)
        self._stats = StatsRepository(self._conn)
        
        # Initialize vector store if pgvector enabled
        if storage_config.USE_PGVECTOR:
            sync_conn_str = f"postgresql://{storage_config.POSTGRES_USER}:{storage_config.POSTGRES_PASSWORD}@{storage_config.POSTGRES_HOST}:{storage_config.POSTGRES_PORT}/{storage_config.POSTGRES_DB}"
            async_conn_str = f"postgresql+asyncpg://{storage_config.POSTGRES_USER}:{storage_config.POSTGRES_PASSWORD}@{storage_config.POSTGRES_HOST}:{storage_config.POSTGRES_PORT}/{storage_config.POSTGRES_DB}"
            self._vector_store = PGVectorStore(
                connection_string=sync_conn_str,
                async_connection_string=async_conn_str,
                table_name=storage_config.VECTOR_STORE_TABLE_NAME,
                embed_dim=storage_config.PGVECTOR_DIMENSIONS,
                indexed_metadata_keys={("file_path", "text")} if storage_config.USE_PGVECTOR else None,
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

    # === Chunks (via Vector Store) ===

    async def get_chunks_by_file(self, file_path: str) -> List[Chunk]:
        """
        Get all chunks for a file from the vector store.
        
        Uses metadata filter on file_path to query the vector store.
        """
        if self._vector_store is None:
            raise RuntimeError("Vector store not initialized. Enable USE_PGVECTOR in config.")
        
        # Build filter for file_path
        filters = MetadataFilters(
            filters=[MetadataFilter(
                key="file_path",
                operator=FilterOperator.EQ,
                value=file_path,
            )]
        )
        
        # Query with no embedding (just filter), request many results
        query = VectorStoreQuery(
            query_embedding=None,  # No similarity, just retrieval by metadata
            similarity_top_k=1000,  # Large enough to get all chunks
            filters=filters,
        )
        
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
            metadata_filter = MetadataFilter(
                key="file_path",
                operator=FilterOperator.EQ,
                value=filter_by_file,
            )
            filters = MetadataFilters(filters=[metadata_filter])
        
        # Build query
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

    async def delete_chunks_by_file_paths(self, file_paths: List[str]) -> None:
        """
        Delete all chunks for given file paths from the vector store.
        
        Uses direct SQL DELETE on the vector store table with metadata filter.
        """
        if self._vector_store is None:
            raise RuntimeError("Vector store not initialized. Enable USE_PGVECTOR in config.")
        
        # Direct SQL delete on the vector store table (metadata_->>'file_path')
        actual_table = f"data_{storage_config.VECTOR_STORE_TABLE_NAME}"
        for file_path in file_paths:
            query = f"""
                DELETE FROM {actual_table}
                WHERE metadata_->>'file_path' = $1
            """
            await self._conn.execute_query(query, file_path)

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

    async def get_files_metadata(self, file_paths: List[str]) -> Dict[str, Dict]:
        return await self._file_summaries.get_batch_metadata(file_paths)
    
    # === File Management ===

    async def delete_file_summaries(self, file_paths: List[str]) -> None:
        await self._file_summaries.delete_by_files(file_paths)

    async def get_file_metadata(self, file_path: str) -> Optional[Dict]:
        return await self._file_summaries.get_metadata(file_path)

    async def delete_file_summary(self, file_path: str) -> None:
        await self._file_summaries.delete(file_path)

    async def update_file_metadata(self, file_path: str, mtime: float, checksum: str) -> None:
        await self._file_summaries.update_metadata(file_path, mtime, checksum)

     # === Stats ===

    async def get_stats(self) -> Dict:
        return await self._stats.get_stats()
    
    async def get_embedding_dimension(self) -> int:
        """
        Get embedding dimension from configuration.
        
        For PostgreSQL, this is the dimension specified for the vector store.
        """
        return storage_config.PGVECTOR_DIMENSIONS
     
    async def clear(self) -> None:
        """Clear all storage (vector store, file_summaries, module_summaries, stats)."""
        # Clear vector store chunks
        if self._vector_store:
            # Delete all nodes from vector store
            await self._vector_store.adelete(filters=None)  # Delete all
        
        # Clear relational data
        await self._file_summaries.clear()
        await self._module_summaries.clear()
        await self._stats.clear()
