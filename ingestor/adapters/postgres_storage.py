"""
PostgreSQL storage adapter.

Persistent storage with asyncpg driver. Supports pgvector for embeddings.
"""

import asyncio
import json
from typing import List, Optional, Dict, Any

import asyncpg
from pgvector.asyncpg import register_vector
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from infra.logger import get_logger
from ingestor.adapters.base_storage import BaseStorage
from ingestor.app.config.storage import storage
from ingestor.app.storage import Chunk, FileSummary, ModuleSummary

log = get_logger("ingestor.storage.postgres")


class PostgreSQLStorage(BaseStorage):
    """
    PostgreSQL storage implementation with pgvector support.
    
    Features:
    - Automatic connection pool management
    - Robust error handling and retries
    - Pgvector support for embeddings
    - JSONB metadata handling
    """

    def __init__(self, operation_timeout: float = 60.0) -> None:
        self._pool: Optional[asyncpg.Pool] = None
        self._operation_timeout = operation_timeout

    async def initialize(self) -> None:
        """Explicitly initialize the storage (create tables, etc)."""
        await self._init_db()

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((OSError, asyncpg.PostgresConnectionError)),
        reraise=True
    )
    async def _init_db(self) -> None:
        """Initialize database connection pool and create tables."""
        if self._pool is not None and not self._pool._closed:
            return

        log.info("postgres.init.start")
        
        conn_string = (
            f"postgresql://{storage.POSTGRES_USER}:{storage.POSTGRES_PASSWORD}"
            f"@{storage.POSTGRES_HOST}:{storage.POSTGRES_PORT}/{storage.POSTGRES_DB}"
        )

        try:
            self._pool = await asyncpg.create_pool(
                conn_string,
                min_size=2,
                max_size=10,
                timeout=30.0,
                command_timeout=self._operation_timeout
            )
            log.info("postgres.init.pool_created")

            # Register extensions and create schema
            async with self._pool.acquire() as conn:
                if storage.USE_PGVECTOR:
                    await register_vector(conn)
                    log.info("postgres.init.pgvector_registered")
                
                await self._create_tables(conn)
            
            log.info("postgres.init.complete")

        except Exception as e:
            log.error("postgres.init.failed", error=str(e))
            if self._pool:
                await self._pool.close()
                self._pool = None
            raise

    async def _create_tables(self, conn: asyncpg.Connection) -> None:
        """Create database tables if they don't exist."""
        log.info("postgres.create_tables.start")
        
        # Chunks table
        await conn.execute(f"""
            CREATE TABLE IF NOT EXISTS chunks (
                id TEXT PRIMARY KEY,
                file_path TEXT NOT NULL,
                content TEXT NOT NULL,
                start_line INTEGER NOT NULL,
                end_line INTEGER NOT NULL,
                chunk_type TEXT NOT NULL,
                summary TEXT,
                purpose TEXT,
                embedding vector({storage.PGVECTOR_DIMENSIONS})
            );
            CREATE INDEX IF NOT EXISTS idx_chunks_file_path ON chunks(file_path);
        """)

        # File summaries table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS file_summaries (
                file_path TEXT PRIMARY KEY,
                summary TEXT NOT NULL,
                chunk_ids TEXT[],
                metadata JSONB DEFAULT '{}'::jsonb,
                checksum TEXT DEFAULT '',
                mtime FLOAT DEFAULT 0
            );
        """)
        
        # Migrations
        try:
            await conn.execute("ALTER TABLE file_summaries ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb")
            await conn.execute("ALTER TABLE file_summaries ADD COLUMN IF NOT EXISTS checksum TEXT DEFAULT ''")
            await conn.execute("ALTER TABLE file_summaries ADD COLUMN IF NOT EXISTS mtime FLOAT DEFAULT 0")
        except Exception:
            pass

        # Module summaries table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS module_summaries (
                module_path TEXT PRIMARY KEY,
                summary TEXT NOT NULL,
                file_paths TEXT[]
            );
        """)
        
        log.info("postgres.create_tables.complete")

    async def _execute_query(self, query: str, *args, fetch: str = None, timeout: float = 10.0) -> Any:
        """
        Execute a query with aggressive timeout and logging.
        """
        await self._init_db()
        
        try:
            log.info("postgres.query.start", query=query[:50])
            
            async with asyncio.timeout(timeout):
                async with self._pool.acquire(timeout=5.0) as conn:
                    log.info("postgres.query.acquired", query=query[:50])
                    
                    if fetch == 'val':
                        result = await conn.fetchval(query, *args)
                    elif fetch == 'row':
                        result = await conn.fetchrow(query, *args)
                    elif fetch == 'all':
                        result = await conn.fetch(query, *args)
                    else:
                        result = await conn.execute(query, *args)
                    
                    log.info("postgres.query.done", query=query[:50])
                    return result
                        
        except asyncio.TimeoutError:
            log.error("postgres.timeout", query=query[:50], timeout=timeout)
            raise TimeoutError(f"Database operation timed out after {timeout}s")
        except Exception as e:
            log.error("postgres.query_error", error=str(e), query=query[:50])
            raise
                        
    # === Chunks ===

    async def save_chunk(self, chunk: Chunk) -> None:
        await self._execute_query(
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

    async def save_chunks(self, chunks: List[Chunk]) -> None:
        if not chunks:
            return

        await self._init_db()
        log.info("postgres.save_chunks.start", count=len(chunks))

        # Подготовка данных для массовой вставки
        data = [
            (
                c.id, c.file_path, c.content, c.start_line,
                c.end_line, c.chunk_type, c.summary, c.purpose,
                c.embedding  # Убедитесь, что это List[float] или None
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
                                            embedding = EXCLUDED.embedding \
                """

        try:
            async with self._pool.acquire() as conn:
                # ВАЖНО: Если используете pgvector, регистрация должна быть здесь,
                # если она не прошла успешно глобально
                if storage.USE_PGVECTOR:
                    from pgvector.asyncpg import register_vector
                    await register_vector(conn)

                await conn.executemany(query, data)

            log.info("postgres.save_chunks.complete", count=len(chunks))
        except Exception as e:
            log.error("postgres.save_chunks.failed", error=str(e), exc_info=True)
            raise

    async def get_chunk(self, chunk_id: str) -> Optional[Chunk]:
        row = await self._execute_query(
            "SELECT * FROM chunks WHERE id = $1", 
            chunk_id, 
            fetch='row'
        )
        if not row:
            return None
        return self._map_chunk(row)

    async def get_chunks_by_file(self, file_path: str) -> List[Chunk]:
        rows = await self._execute_query(
            "SELECT * FROM chunks WHERE file_path = $1 ORDER BY start_line",
            file_path,
            fetch='all'
        )
        return [self._map_chunk(row) for row in rows]

    async def get_all_chunks(self) -> List[Chunk]:
        rows = await self._execute_query(
            "SELECT * FROM chunks ORDER BY file_path, start_line",
            fetch='all'
        )
        return [self._map_chunk(row) for row in rows]

    def _map_chunk(self, row: Any) -> Chunk:
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

    # === File Summaries ===

    async def save_file_summary(self, summary: FileSummary) -> None:
        metadata = summary.metadata

        # Явно упаковываем параметры в кортеж, чтобы они не перекрывали fetch/timeout
        query = """
                INSERT INTO file_summaries (file_path, summary, chunk_ids, metadata, mtime, checksum)
                VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (file_path) DO UPDATE SET
                    summary = EXCLUDED.summary,
                    chunk_ids = EXCLUDED.chunk_ids,
                    metadata = EXCLUDED.metadata,
                    mtime = EXCLUDED.mtime,
                    checksum = EXCLUDED.checksum
                """

        # Передаем аргументы через *args, а fetch/timeout — как именованные
        await self._execute_query(
            query,
            summary.file_path,        # $1
            summary.summary,          # $2
            summary.chunk_ids,        # $3
            json.dumps(summary.metadata),                 # $4
            metadata.get("mtime", 0), # $5
            metadata.get("checksum", ""), # $6
            fetch=None                # Явно указываем, что это не результат fetch
        )

    async def get_file_summary(self, file_path: str) -> Optional[FileSummary]:
        row = await self._execute_query(
            "SELECT * FROM file_summaries WHERE file_path = $1",
            file_path,
            fetch='row'
        )
        if not row:
            return None
        return self._map_file_summary(row)

    async def get_all_file_summaries(self) -> List[FileSummary]:
        log.info("postgres.get_all_file_summaries.start")
        # Cast JSONB to text to avoid asyncpg ClientRead deadlock
        rows = await self._execute_query(
            "SELECT file_path, summary, chunk_ids, metadata::text as metadata_json, mtime, checksum FROM file_summaries",
            fetch='all',
            timeout=5.0
        )
        log.info("postgres.get_all_file_summaries.fetched", count=len(rows))
        
        results = []
        for row in rows:
            try:
                meta = json.loads(row["metadata_json"]) if row.get("metadata_json") else {}
                if "mtime" in row:
                    meta["mtime"] = row["mtime"]
                if "checksum" in row:
                    meta["checksum"] = row["checksum"]
                    
                results.append(FileSummary(
                    file_path=row["file_path"],
                    summary=row["summary"],
                    chunk_ids=list(row["chunk_ids"]) if row["chunk_ids"] else [],
                    metadata=meta,
                ))
            except Exception as e:
                log.warning("postgres.map_file_summary.failed", file=row.get("file_path"), error=str(e))
                continue
        
        return results

    def _map_file_summary(self, row: Any) -> FileSummary:
        meta = row["metadata"]
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except json.JSONDecodeError:
                meta = {}
        elif meta is None:
            meta = {}
            
        # Ensure mtime/checksum are in metadata if present in columns
        if "mtime" in row:
            meta["mtime"] = row["mtime"]
        if "checksum" in row:
            meta["checksum"] = row["checksum"]
            
        return FileSummary(
            file_path=row["file_path"],
            summary=row["summary"],
            chunk_ids=row["chunk_ids"],
            metadata=meta,
        )

    async def update_file_metadata(self, file_path: str, mtime: float, checksum: str) -> None:
        """Update file metadata in database."""
        meta = {
            "mtime": mtime,
            "checksum": checksum,
            "size": 0 
        }
        await self._execute_query(
             """
            INSERT INTO file_summaries (file_path, summary, chunk_ids, metadata, mtime, checksum)
            VALUES ($1, '', '{}', $2, $3, $4)
            ON CONFLICT (file_path) DO UPDATE SET
                metadata = file_summaries.metadata || $2,
                mtime = EXCLUDED.mtime,
                checksum = EXCLUDED.checksum
            """,
            file_path,
            json.dumps(meta),
            mtime,
            checksum
        )

    async def delete_chunks_by_file_paths(self, file_paths: List[str]) -> None:
        await self._execute_query(
            "DELETE FROM chunks WHERE file_path = ANY($1)",
            file_paths
        )

    async def delete_file_summaries(self, file_paths: List[str]) -> None:
        await self._execute_query(
            "DELETE FROM file_summaries WHERE file_path = ANY($1)",
            file_paths
        )

        log.info("postgres.delete_file_summaries", paths=file_paths)

    async def get_file_metadata(self, file_path: str) -> Optional[Dict]:
        row = await self._execute_query(
            "SELECT * FROM file_summaries WHERE file_path = $1",
            file_path,
            fetch='row'
        )
        if not row:
            return None
        
        return {
            "file_path": row["file_path"],
            "mtime": row.get("mtime", 0),
            "checksum": row.get("checksum", ""),
            "size": 0, # Size usually in metadata
        }

    # Removed duplicate update_file_metadata implementation
    # The correct implementation is above in Metadata & Cleanup section

    async def get_embedding_dimension(self) -> int:
        return await self._execute_query(
            """
            SELECT atttypmod
            FROM pg_attribute pa
            JOIN pg_class pc ON pa.attrelid = pc.oid
            WHERE pc.relname = 'chunks' AND pa.attname = 'embedding'
            """,
            fetch='val'
        ) or 0

    # === Stats & Lifecycle ===

    async def get_stats(self) -> Dict:
        # Run in parallel
        results = await asyncio.gather(
            self._execute_query("SELECT COUNT(*) FROM chunks", fetch='val'),
            self._execute_query("SELECT COUNT(*) FROM file_summaries", fetch='val'),
            self._execute_query("SELECT COUNT(*) FROM module_summaries", fetch='val'),
            self._execute_query("SELECT COUNT(*) FROM chunks WHERE embedding IS NOT NULL", fetch='val'),
            self._execute_query("SELECT COUNT(*) FROM chunks WHERE summary IS NOT NULL", fetch='val'),
            return_exceptions=True
        )
        
        # Unpack, handling errors gracefully
        keys = ["chunks", "file_summaries", "module_summaries", "chunks_with_embeddings", "chunks_with_summary"]
        stats = {}
        for i, key in enumerate(keys):
            res = results[i]
            stats[key] = res if isinstance(res, int) else 0
            
        return stats

    async def clear(self) -> None:
        await self._init_db()
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("DELETE FROM chunks")
                await conn.execute("DELETE FROM file_summaries")
                await conn.execute("DELETE FROM module_summaries")

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
            self._pool = None

    async def __aenter__(self):
        await self._init_db()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    # Stub for interface compatibility
    async def save_module_summary(self, summary: ModuleSummary) -> None:
        pass
    
    async def get_module_summary(self, module_path: str) -> Optional[ModuleSummary]:
        return None
        
    async def get_all_module_summaries(self) -> List[ModuleSummary]:
        return []