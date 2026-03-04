"""
PostgreSQL connection pool management.
"""

import asyncio
from typing import Optional, Any
import asyncpg
from pgvector.asyncpg import register_vector
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    retry_if_exception,
)

from infra.logger import get_logger
from ingestor.config import storage_config

log = get_logger("ingestor.storage.postgres.connection")


class PostgresConnection:
    """Manages PostgreSQL connection pool."""

    def __init__(self) -> None:
        self._pool: Optional[asyncpg.Pool] = None
        # Read configuration from storage_config
        self._operation_timeout = storage_config.POSTGRES_OPERATION_TIMEOUT
        self._pool_min_size = storage_config.POSTGRES_POOL_MIN_SIZE
        self._pool_max_size = storage_config.POSTGRES_POOL_MAX_SIZE
        self._pool_timeout = storage_config.POSTGRES_POOL_TIMEOUT
        self._acquire_timeout = storage_config.POSTGRES_ACQUIRE_TIMEOUT
        self._query_timeout = storage_config.POSTGRES_QUERY_TIMEOUT

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
        reraise=True,
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
            # Create a connection init function that registers vector type
            async def init_connection(conn):
                """Initialize a new connection with vector type registration."""
                if storage_config.USE_PGVECTOR:
                    await register_vector(conn)
                await self._setup_extensions(conn)

            self._pool = await asyncpg.create_pool(
                conn_string,
                min_size=self._pool_min_size,
                max_size=self._pool_max_size,
                timeout=self._pool_timeout,
                command_timeout=self._operation_timeout,
                init=init_connection,
            )  # noqa: E501
            log.info("postgres.init.pool_created")

            # Create schema only once, on the first connection
            async with self._pool.acquire() as conn:
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
        # Note: register_vector is now called in the init_connection function
        # when creating the connection pool
        pass

    async def _create_schema(self, conn) -> None:
        """Create database tables."""
        log.info("postgres.create_schema.start")

        # 1. File summaries table (Parent table)
        # Note: chunk_ids removed as per new architecture
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS file_summaries (
                file_path TEXT PRIMARY KEY,
                summary TEXT NOT NULL,
                metadata JSONB DEFAULT '{}'::jsonb,
                checksum TEXT DEFAULT '',
                mtime FLOAT DEFAULT 0
            );
        """)
        
        # Migration: Drop chunk_ids column if it exists (for existing DBs)
        try:
            await conn.execute("ALTER TABLE file_summaries DROP COLUMN IF EXISTS chunk_ids;")
        except Exception as e:
            log.warning("postgres.schema.migration.drop_chunk_ids.failed", error=str(e))

        # 2. Chunks table removed - using PGVectorStore chunks_vectors instead

        # 3. Module summaries table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS module_summaries (
                module_path TEXT PRIMARY KEY,
                summary TEXT NOT NULL,
                file_paths TEXT[]
            );
        """)

        log.info("postgres.create_schema.complete")

    async def execute_query(
        self, query: str, *args, fetch: Optional[str] = None, timeout: Optional[float] = None
    ) -> Any:
        """Execute a query with logging and timeout."""
        await self._init_pool()
        
        # Use config timeout if not provided
        query_timeout = timeout if timeout is not None else self._query_timeout

        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=0.1, max=1),
            retry=retry_if_exception(lambda e: isinstance(e, (asyncpg.PostgresConnectionError, asyncio.TimeoutError))),
            reraise=True,
        )
        async def _execute_with_retry():
            try:
                log.debug("postgres.query.start", query=query[:50])

                async with asyncio.timeout(query_timeout):
                    async with self.pool.acquire(timeout=self._acquire_timeout) as conn:
                        if fetch == "val":
                            result = await conn.fetchval(query, *args)
                        elif fetch == "row":
                            result = await conn.fetchrow(query, *args)
                        elif fetch == "all":
                            result = await conn.fetch(query, *args)
                        else:
                            result = await conn.execute(query, *args)

                        return result

            except asyncio.TimeoutError:
                log.error("postgres.timeout", query=query[:50], timeout=query_timeout)
                raise TimeoutError(f"Database operation timed out after {query_timeout}s")
            except Exception as e:
                log.error("postgres.query_error", error=str(e), query=query[:50])
                raise

        return await _execute_with_retry()

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
            self._pool = None
