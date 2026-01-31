"""
PostgreSQL storage adapter.

Persistent storage with asyncpg driver. Supports pgvector for embeddings.
"""

import asyncpg
from typing import List, Optional, Dict
from dataclasses import asdict
from pgvector.asyncpg import register_vector
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

from ingestor.adapters.base_storage import BaseStorage
from ingestor.app.storage import Chunk, FileSummary, ModuleSummary
from ingestor.app.config.storage import storage
from ingestor.app.config.llm import llm


class PostgreSQLStorage(BaseStorage):
    """
    PostgreSQL storage implementation with pgvector support.

    Requires:
    - PostgreSQL 16+ with pgvector extension
    - Tables will be auto-created on first run
    """

    def __init__(self) -> None:
        self._engine = None
        self._conn = None

    async def _init_db(self) -> None:
        """Initialize database connection and create tables."""
        if self._engine is not None:
            return

        conn_string = (
            f"postgresql://{storage.POSTGRES_USER}:{storage.POSTGRES_PASSWORD}"
            f"@{storage.POSTGRES_HOST}:{storage.POSTGRES_PORT}/{storage.POSTGRES_DB}"
        )

        self._engine = create_async_engine(
            conn_string,
            echo=(storage.ENV == "dev"),
            pool_size=10,
            max_overflow=20,
        )

        self._conn = await self._engine.connect()

        # Register pgvector extension if enabled
        if storage.USE_PGVECTOR:
            await register_vector(self._conn)

        # Create tables if not exist
        await self._create_tables()

    async def _create_tables(self) -> None:
        """Create database tables if they don't exist."""
        tables_sql = """
        CREATE TABLE IF NOT EXISTS chunks (
            id TEXT PRIMARY KEY,
            file_path TEXT NOT NULL,
            content TEXT NOT NULL,
            start_line INTEGER NOT NULL,
            end_line INTEGER NOT NULL,
            chunk_type TEXT NOT NULL,
            summary TEXT,
            purpose TEXT,
            embedding FLOAT[1536]  -- pgvector column
        );

        CREATE INDEX IF NOT EXISTS idx_chunks_file_path ON chunks(file_path);

        CREATE TABLE IF NOT EXISTS file_summaries (
            file_path TEXT PRIMARY KEY,
            summary TEXT NOT NULL,
            chunk_ids TEXT[]
        );

        CREATE TABLE IF NOT EXISTS module_summaries (
            module_path TEXT PRIMARY KEY,
            summary TEXT NOT NULL,
            file_paths TEXT[]
        );
        """

        await self._conn.execute(tables_sql)

    # === Chunks ===

    async def save_chunk(self, chunk: Chunk) -> None:
        await self._init_db()

        await self._conn.execute(
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
            chunk.id,
            chunk.file_path,
            chunk.content,
            chunk.start_line,
            chunk.end_line,
            chunk.chunk_type,
            chunk.summary,
            chunk.purpose,
            chunk.embedding,
        )

    async def save_chunks(self, chunks: List[Chunk]) -> None:
        await self._init_db()

        for chunk in chunks:
            await self.save_chunk(chunk)

    async def get_chunk(self, chunk_id: str) -> Optional[Chunk]:
        await self._init_db()

        row = await self._conn.fetchrow(
            "SELECT * FROM chunks WHERE id = $1",
            chunk_id,
        )

        if not row:
            return None

        return Chunk(
            id=row["id"],
            file_path=row["file_path"],
            content=row["content"],
            start_line=row["start_line"],
            end_line=row["end_line"],
            chunk_type=row["chunk_type"],
            summary=row["summary"],
            purpose=row["purpose"],
            embedding=row["embedding"],
            metadata={},
        )

    async def get_chunks_by_file(self, file_path: str) -> List[Chunk]:
        await self._init_db()

        rows = await self._conn.fetch(
            "SELECT * FROM chunks WHERE file_path = $1 ORDER BY start_line",
            file_path,
        )

        return [
            Chunk(
                id=row["id"],
                file_path=row["file_path"],
                content=row["content"],
                start_line=row["start_line"],
                end_line=row["end_line"],
                chunk_type=row["chunk_type"],
                summary=row["summary"],
                purpose=row["purpose"],
                embedding=row["embedding"],
                metadata={},
            )
            for row in rows
        ]

    async def get_all_chunks(self) -> List[Chunk]:
        await self._init_db()

        rows = await self._conn.fetch("SELECT * FROM chunks ORDER BY file_path, start_line")

        return [
            Chunk(
                id=row["id"],
                file_path=row["file_path"],
                content=row["content"],
                start_line=row["start_line"],
                end_line=row["end_line"],
                chunk_type=row["chunk_type"],
                summary=row["summary"],
                purpose=row["purpose"],
                embedding=row["embedding"],
                metadata={},
            )
            for row in rows
        ]

    # === File Summaries ===

    async def save_file_summary(self, summary: FileSummary) -> None:
        await self._init_db()

        await self._conn.execute(
            """
            INSERT INTO file_summaries (file_path, summary, chunk_ids)
            VALUES ($1, $2, $3)
            ON CONFLICT (file_path) DO UPDATE SET
                summary = EXCLUDED.summary,
                chunk_ids = EXCLUDED.chunk_ids
            """,
            summary.file_path,
            summary.summary,
            summary.chunk_ids,
        )

    async def get_file_summary(self, file_path: str) -> Optional[FileSummary]:
        await self._init_db()

        row = await self._conn.fetchrow(
            "SELECT * FROM file_summaries WHERE file_path = $1",
            file_path,
        )

        if not row:
            return None

        return FileSummary(
            file_path=row["file_path"],
            summary=row["summary"],
            chunk_ids=row["chunk_ids"],
            metadata={},
        )

    async def get_all_file_summaries(self) -> List[FileSummary]:
        await self._init_db()

        rows = await self._conn.fetch("SELECT * FROM file_summaries")

        return [
            FileSummary(
                file_path=row["file_path"],
                summary=row["summary"],
                chunk_ids=row["chunk_ids"],
                metadata={},
            )
            for row in rows
        ]

    # === Module Summaries ===

    async def save_module_summary(self, summary: ModuleSummary) -> None:
        await self._init_db()

        await self._conn.execute(
            """
            INSERT INTO module_summaries (module_path, summary, file_paths)
            VALUES ($1, $2, $3)
            ON CONFLICT (module_path) DO UPDATE SET
                summary = EXCLUDED.summary,
                file_paths = EXCLUDED.file_paths
            """,
            summary.module_path,
            summary.summary,
            summary.file_paths,
        )

    async def get_module_summary(self, module_path: str) -> Optional[ModuleSummary]:
        await self._init_db()

        row = await self._conn.fetchrow(
            "SELECT * FROM module_summaries WHERE module_path = $1",
            module_path,
        )

        if not row:
            return None

        return ModuleSummary(
            module_path=row["module_path"],
            summary=row["summary"],
            file_paths=row["file_paths"],
            metadata={},
        )

    async def get_all_module_summaries(self) -> List[ModuleSummary]:
        await self._init_db()

        rows = await self._conn.fetch("SELECT * FROM module_summaries")

        return [
            ModuleSummary(
                module_path=row["module_path"],
                summary=row["summary"],
                file_paths=row["file_paths"],
                metadata={},
            )
            for row in rows
        ]

    # === Stats ===

    async def get_stats(self) -> Dict:
        await self._init_db()

        chunks = await self._conn.fetchval("SELECT COUNT(*) FROM chunks")
        file_summaries = await self._conn.fetchval("SELECT COUNT(*) FROM file_summaries")
        module_summaries = await self._conn.fetchval("SELECT COUNT(*) FROM module_summaries")
        chunks_with_embeddings = await self._conn.fetchval(
            "SELECT COUNT(*) FROM chunks WHERE embedding IS NOT NULL"
        )
        chunks_with_summary = await self._conn.fetchval(
            "SELECT COUNT(*) FROM chunks WHERE summary IS NOT NULL"
        )

        return {
            "chunks": chunks,
            "file_summaries": file_summaries,
            "module_summaries": module_summaries,
            "chunks_with_embeddings": chunks_with_embeddings,
            "chunks_with_summary": chunks_with_summary,
        }

    async def clear(self) -> None:
        await self._init_db()

        await self._conn.execute("DELETE FROM chunks")
        await self._conn.execute("DELETE FROM file_summaries")
        await self._conn.execute("DELETE FROM module_summaries")

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
        if self._engine:
            await self._engine.dispose()

    async def __aenter__(self):
        await self._init_db()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
