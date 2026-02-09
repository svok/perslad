"""
PostgreSQL connection pool management.
"""

import asyncio
from typing import Optional, Any
import asyncpg
from pgvector.asyncpg import register_vector
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from infra.logger import get_logger
from ingestor.app.config.storage import storage as storage_config

log = get_logger("ingestor.storage.postgres.connection")


class PostgresConnection:
    """Manages PostgreSQL connection pool."""

    def __init__(self, operation_timeout: float = 60.0) -> None:
        self._pool: Optional[asyncpg.Pool] = None
        self._operation_timeout = operation_timeout

    @property
    def pool(self) -> asyncpg.Pool:
        """Get the connection pool. Raises error if not initialized."""
        if self._pool is None:
            raise RuntimeError("Database not initialized")
        return self._pool

    async def initialize(self) -> None:
        """Initialize connection pool and database schema."""
        await self._init_pool()

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((OSError, asyncpg.PostgresConnectionError)),
        reraise=True
    )
    async def _init_pool(self) -> None:
        """Initialize database connection pool."""
        if self._pool is not None and not self._pool._closed:
            return

        log.info("postgres.init.start")
        
        conn_string = (
            f"postgresql://{storage_config.POSTGRES_USER}:{storage_config.POSTGRES_PASSWORD}"
            f"@{storage_config.POSTGRES_HOST}:{storage_config.POSTGRES_PORT}/{storage_config.POSTGRES_DB}"
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

            async with self._pool.acquire() as conn:
                await self._setup_extensions(conn)
                await self._create_schema(conn)
            
            log.info("postgres.init.complete")

        except Exception as e:
            log.error("postgres.init.failed", error=str(e))
            if self._pool:
                await self._pool.close()
                self._pool = None
            raise

    async def _setup_extensions(self, conn: asyncpg.Connection) -> None:
        """Register extensions like pgvector."""
        if storage_config.USE_PGVECTOR:
            await register_vector(conn)
            log.info("postgres.init.pgvector_registered")

    async def _create_schema(self, conn: asyncpg.Connection) -> None:
        """Create database tables."""
        log.info("postgres.create_schema.start")
        
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
                embedding vector({storage_config.PGVECTOR_DIMENSIONS})
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
        
        # Module summaries table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS module_summaries (
                module_path TEXT PRIMARY KEY,
                summary TEXT NOT NULL,
                file_paths TEXT[]
            );
        """)
        
        log.info("postgres.create_schema.complete")

    async def execute_query(self, query: str, *args, fetch: str = None, timeout: float = 10.0) -> Any:
        """Execute a query with logging and timeout."""
        await self._init_pool()
        
        try:
            log.debug("postgres.query.start", query=query[:50])
            
            async with asyncio.timeout(timeout):
                async with self.pool.acquire(timeout=5.0) as conn:
                    if fetch == 'val':
                        result = await conn.fetchval(query, *args)
                    elif fetch == 'row':
                        result = await conn.fetchrow(query, *args)
                    elif fetch == 'all':
                        result = await conn.fetch(query, *args)
                    else:
                        result = await conn.execute(query, *args)
                    
                    return result
                        
        except asyncio.TimeoutError:
            log.error("postgres.timeout", query=query[:50], timeout=timeout)
            raise TimeoutError(f"Database operation timed out after {timeout}s")
        except Exception as e:
            log.error("postgres.query_error", error=str(e), query=query[:50])
            raise

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
            self._pool = None
