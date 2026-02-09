"""
Stats repository for PostgreSQL.
"""

import asyncio
from typing import Dict
from ingestor.adapters.postgres.connection import PostgresConnection


class StatsRepository:
    def __init__(self, connection: PostgresConnection):
        self._conn = connection

    async def get_stats(self) -> Dict:
        # Run in parallel
        results = await asyncio.gather(
            self._conn.execute_query("SELECT COUNT(*) FROM chunks", fetch='val'),
            self._conn.execute_query("SELECT COUNT(*) FROM file_summaries", fetch='val'),
            self._conn.execute_query("SELECT COUNT(*) FROM module_summaries", fetch='val'),
            self._conn.execute_query("SELECT COUNT(*) FROM chunks WHERE embedding IS NOT NULL", fetch='val'),
            self._conn.execute_query("SELECT COUNT(*) FROM chunks WHERE summary IS NOT NULL", fetch='val'),
            return_exceptions=True
        )
        
        # Unpack, handling errors gracefully
        keys = ["chunks", "file_summaries", "module_summaries", "chunks_with_embeddings", "chunks_with_summary"]
        stats = {}
        for i, key in enumerate(keys):
            res = results[i]
            stats[key] = res if isinstance(res, int) else 0
            
        return stats

    async def clear_all(self) -> None:
        await self._conn.initialize()
        async with self._conn.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("DELETE FROM chunks")
                await conn.execute("DELETE FROM file_summaries")
                await conn.execute("DELETE FROM module_summaries")
