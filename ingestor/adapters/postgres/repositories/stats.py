"""
Stats repository for PostgreSQL.

Now uses PGVectorStore table (chunks_vectors) for chunk statistics.
"""

import asyncio
from typing import Dict
from ingestor.adapters.postgres.connection import PostgresConnection
from ingestor.config import storage_config


class StatsRepository:
    def __init__(self, connection: PostgresConnection):
        self._conn = connection
        # PGVectorStore adds 'data_' prefix to the table name
        self._actual_table = f"data_{storage_config.VECTOR_STORE_TABLE_NAME}"

    async def get_stats(self) -> Dict:
        # Run in parallel
        results = await asyncio.gather(
            self._get_total_chunks(),
            self._get_total_file_summaries(),
            self._get_total_module_summaries(),
            self._get_chunks_with_embeddings(),
            self._get_chunks_with_summary(),
            return_exceptions=True
        )
        
        # Unpack, handling errors gracefully
        keys = ["chunks", "file_summaries", "module_summaries", "chunks_with_embeddings", "chunks_with_summary"]
        stats = {}
        for i, key in enumerate(keys):
            res = results[i]
            stats[key] = res if isinstance(res, int) else 0
            
        return stats

    async def _get_total_chunks(self) -> int:
        return await self._conn.execute_query(
            f"SELECT COUNT(*) FROM {self._actual_table}",
            fetch='val'
        )

    async def _get_total_file_summaries(self) -> int:
        return await self._conn.execute_query(
            "SELECT COUNT(*) FROM file_summaries",
            fetch='val'
        )

    async def _get_total_module_summaries(self) -> int:
        return await self._conn.execute_query(
            "SELECT COUNT(*) FROM module_summaries",
            fetch='val'
        )

    async def _get_chunks_with_embeddings(self) -> int:
        # All chunks in vector store should have embeddings
        return await self._get_total_chunks()

    async def _get_chunks_with_summary(self) -> int:
        # Count chunks where metadata_->>'summary' is not null
        return await self._conn.execute_query(
            f"SELECT COUNT(*) FROM {self._actual_table} WHERE metadata_->>'summary' IS NOT NULL",
            fetch='val'
        )

    async def clear_all(self) -> None:
        await self._conn.initialize()
        async with self._conn.pool.acquire() as conn:
            async with conn.transaction():
                # Clear vector store table
                await conn.execute(f"DELETE FROM {self._actual_table}")
                # Clear relational data
                await conn.execute("DELETE FROM file_summaries")
                await conn.execute("DELETE FROM module_summaries")
