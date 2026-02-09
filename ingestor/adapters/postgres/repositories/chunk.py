"""
Chunk repository for PostgreSQL.
"""

from typing import List, Optional
from ingestor.core.models.chunk import Chunk
from ingestor.adapters.postgres.connection import PostgresConnection
from ingestor.adapters.postgres.mappers import PostgresMapper
from ingestor.app.config.storage import storage as storage_config
from infra.logger import get_logger

log = get_logger("ingestor.storage.postgres.chunks")


class ChunkRepository:
    def __init__(self, connection: PostgresConnection):
        self._conn = connection

    async def save(self, chunk: Chunk) -> None:
        await self._conn.execute_query(
            """
            INSERT INTO chunks (
                id, file_path, content, start_line, end_line, chunk_type,
                summary, purpose, embedding
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (id) DO UPDATE SET
                file_path = EXCLUDED.file_path,
                content = EXCLUDED.content,
                start_line = EXCLUDED.start_line,
                end_line = EXCLUDED.end_line,
                chunk_type = EXCLUDED.chunk_type,
                summary = EXCLUDED.summary,
                purpose = EXCLUDED.purpose,
                embedding = EXCLUDED.embedding
            """,
            chunk.id, chunk.file_path, chunk.content, chunk.start_line, 
            chunk.end_line, chunk.chunk_type, chunk.summary, chunk.purpose, chunk.embedding
        )

    async def save_batch(self, chunks: List[Chunk]) -> None:
        if not chunks:
            return

        await self._conn.initialize()
        log.info("postgres.save_chunks.start", count=len(chunks))

        data = [
            (
                c.id, c.file_path, c.content, c.start_line,
                c.end_line, c.chunk_type, c.summary, c.purpose,
                c.embedding
            )
            for c in chunks
        ]

        query = """
            INSERT INTO chunks (
                id, file_path, content, start_line, end_line, chunk_type,
                summary, purpose, embedding
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (id) DO UPDATE SET
                file_path = EXCLUDED.file_path,
                content = EXCLUDED.content,
                start_line = EXCLUDED.start_line,
                end_line = EXCLUDED.end_line,
                chunk_type = EXCLUDED.chunk_type,
                summary = EXCLUDED.summary,
                purpose = EXCLUDED.purpose,
                embedding = EXCLUDED.embedding
        """

        try:
            async with self._conn.pool.acquire() as conn:
                if storage_config.USE_PGVECTOR:
                    from pgvector.asyncpg import register_vector
                    await register_vector(conn)

                await conn.executemany(query, data)

            log.info("postgres.save_chunks.complete", count=len(chunks))
        except Exception as e:
            log.error("postgres.save_chunks.failed", error=str(e), exc_info=True)
            raise

    async def get(self, chunk_id: str) -> Optional[Chunk]:
        row = await self._conn.execute_query(
            "SELECT * FROM chunks WHERE id = $1", 
            chunk_id, 
            fetch='row'
        )
        if not row:
            return None
        return PostgresMapper.map_chunk(row)

    async def get_by_file(self, file_path: str) -> List[Chunk]:
        rows = await self._conn.execute_query(
            "SELECT * FROM chunks WHERE file_path = $1 ORDER BY start_line",
            file_path,
            fetch='all'
        )
        return [PostgresMapper.map_chunk(row) for row in rows]

    async def get_all(self) -> List[Chunk]:
        rows = await self._conn.execute_query(
            "SELECT * FROM chunks ORDER BY file_path, start_line",
            fetch='all'
        )
        return [PostgresMapper.map_chunk(row) for row in rows]

    async def delete_by_files(self, file_paths: List[str]) -> None:
        await self._conn.execute_query(
            "DELETE FROM chunks WHERE file_path = ANY($1)",
            file_paths
        )

    async def get_embedding_dimension(self) -> int:
        return await self._conn.execute_query(
            """
            SELECT atttypmod
            FROM pg_attribute pa
            JOIN pg_class pc ON pa.attrelid = pc.oid
            WHERE pc.relname = 'chunks' AND pa.attname = 'embedding'
            """,
            fetch='val'
        ) or 0
