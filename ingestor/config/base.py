from pydantic import BaseModel, Field
from typing import Optional


class BaseServiceConfig(BaseModel):
    """Base configuration for external services."""
    url: str = Field(..., description="Service URL")
    api_key: str = Field(..., description="API key for authentication")
    model_name: str = Field(..., description="Model name to use")
    timeout: float = Field(default=30.0, description="Request timeout in seconds")
    batch_size: int = Field(default=10, description="Batch size for requests")
    max_workers: int = Field(default=2, description="Maximum worker tasks")


class LLMConfig(BaseServiceConfig):
    """LLM-specific configuration."""
    temperature: float = Field(default=0.1, description="Sampling temperature")
    max_retries: int = Field(default=2, description="Maximum retries for requests")


class EmbeddingConfig(BaseServiceConfig):
    """Embedding-specific configuration."""
    rate_limit_rpm: int = Field(default=100, description="Rate limit in requests per minute")
    max_chars: int = Field(default=8000, description="Maximum characters to embed")
    timeout: float = Field(default=30.0, description="Request timeout for embedding in seconds")


class StorageConfig(BaseModel):
    """Storage configuration."""
    type: str = Field(default="postgres", description="Storage type: postgres or memory")

    # PostgreSQL connection
    postgres_host: str = Field(default="postgres")
    postgres_port: int = Field(default=5432)
    postgres_db: str = Field(default="rag")
    postgres_user: str = Field(default="rag")
    postgres_password: str = Field(default="rag")

    # Vector storage
    use_pgvector: bool = Field(default=True)
    vector_dim: Optional[int] = Field(default=None, description="Embedding dimension, auto-detected if None")
    table_name: str = Field(default="chunks", description="Table name for vector store")

    # Connection pool
    pool_min_size: int = Field(default=2, description="Minimum connection pool size")
    pool_max_size: int = Field(default=10, description="Maximum connection pool size")
    pool_timeout: float = Field(default=30.0, description="Pool connection timeout")
    operation_timeout: float = Field(default=60.0, description="Database operation timeout")
    query_timeout: float = Field(default=10.0, description="Query execution timeout")
    acquire_timeout: float = Field(default=5.0, description="Connection acquire timeout")


class PipelineConfig(BaseModel):
    """Full pipeline configuration."""
    llm: LLMConfig
    embedding: EmbeddingConfig
    storage: StorageConfig

    # Indexation pipeline workers
    enrich_workers: int = Field(default=2, description="EnrichStage worker count")
    parse_workers: int = Field(default=1, description="ParseProcessorStage worker count")
    enrich_chunks_workers: int = Field(default=2, description="EnrichChunksStage worker count")
    indexing_workers: int = Field(default=2, description="IndexingStage worker count")
    file_summary_workers: int = Field(default=2, description="FileSummaryStage worker count")

    # Pipeline queues and batching
    queue_size: int = Field(default=1000, description="Pipeline queue size")
    filter_batch_size: int = Field(default=100, description="IncrementalFilterStage batch size")
    filter_max_wait: float = Field(default=3.0, description="IncrementalFilterStage max wait seconds")
    indexing_batch_size: int = Field(default=100, description="IndexingStage batch size")
    collector_batch_size: int = Field(default=10, description="BatchCollectorStage batch size")
    collector_max_wait: float = Field(default=0.5, description="BatchCollectorStage max wait seconds")

    # Text splitting
    python_chunk_lines: int = Field(default=40, description="Code splitter chunk lines")
    python_chunk_overlap: int = Field(default=15, description="Code splitter line overlap")
    python_max_chars: int = Field(default=1500, description="Code splitter max chars per chunk")
    doc_chunk_size: int = Field(default=512, description="Document splitter chunk size")
    doc_chunk_overlap: int = Field(default=50, description="Document splitter chunk overlap")
    config_chunk_size: int = Field(default=512, description="Config file splitter chunk size")
    config_chunk_overlap: int = Field(default=50, description="Config file splitter chunk overlap")

    # Summary generation
    file_summary_max_chunks: int = Field(default=20, description="Max chunks to aggregate for file summary")

    # Search defaults
    search_default_top_k: int = Field(default=10, description="Default top_k for search queries")

    # Runtime
    workspace_path: str = Field(default="./workspace")
    monitor_interval: float = Field(default=10.0, description="Pipeline monitor loop interval")

    @classmethod
    def from_env(cls) -> "PipelineConfig":
        """Load configuration from environment variables."""
        # Load individual configs
        from ingestor.config import llm_config, emb_config, storage_config, runtime_config

        return cls(
            llm=LLMConfig(
                url=llm_config.LLM_URL,
                api_key=llm_config.LLM_API_KEY,
                model_name=llm_config.LLM_SERVED_MODEL_NAME,
                temperature=getattr(llm_config, 'LLM_TEMPERATURE', 0.1),
                max_retries=getattr(llm_config, 'LLM_MAX_RETRIES', 2),
                timeout=getattr(llm_config, 'LLM_TIMEOUT', 30.0),
                batch_size=getattr(llm_config, 'LLM_BATCH_SIZE', 10),
                max_workers=getattr(llm_config, 'LLM_MAX_WORKERS', 2),
            ),
            embedding=EmbeddingConfig(
                url=emb_config.EMB_URL,
                api_key=emb_config.EMB_API_KEY,
                model_name=emb_config.EMB_SERVED_MODEL_NAME,
                rate_limit_rpm=emb_config.EMB_RATE_LIMIT_RPM,
                max_chars=emb_config.EMB_MAX_CHARS,
                batch_size=emb_config.EMB_BATCH_SIZE,
                timeout=getattr(emb_config, 'EMB_TIMEOUT', 30.0),
                max_workers=getattr(emb_config, 'EMB_MAX_WORKERS', 2),
            ),
            storage=StorageConfig(
                type=storage_config.STORAGE_TYPE,
                postgres_host=storage_config.POSTGRES_HOST,
                postgres_port=storage_config.POSTGRES_PORT,
                postgres_db=storage_config.POSTGRES_DB,
                postgres_user=storage_config.POSTGRES_USER,
                postgres_password=storage_config.POSTGRES_PASSWORD,
                use_pgvector=storage_config.USE_PGVECTOR,
                vector_dim=storage_config.PGVECTOR_DIMENSIONS if storage_config.PGVECTOR_DIMENSIONS != 1536 else None,
                table_name=getattr(storage_config, 'VECTOR_STORE_TABLE_NAME', 'chunks'),
                pool_min_size=getattr(storage_config, 'POSTGRES_POOL_MIN_SIZE', 2),
                pool_max_size=getattr(storage_config, 'POSTGRES_POOL_MAX_SIZE', 10),
                pool_timeout=getattr(storage_config, 'POSTGRES_POOL_TIMEOUT', 30.0),
                operation_timeout=getattr(storage_config, 'POSTGRES_OPERATION_TIMEOUT', 60.0),
                query_timeout=getattr(storage_config, 'POSTGRES_QUERY_TIMEOUT', 10.0),
                acquire_timeout=getattr(storage_config, 'POSTGRES_ACQUIRE_TIMEOUT', 5.0),
            ),
            enrich_workers=getattr(runtime_config, 'ENRICH_WORKERS', 2),
            parse_workers=getattr(runtime_config, 'PARSE_WORKERS', 1),
            enrich_chunks_workers=getattr(runtime_config, 'ENRICH_CHUNKS_WORKERS', 2),
            indexing_workers=getattr(runtime_config, 'INDEXING_WORKERS', 2),
            file_summary_workers=getattr(runtime_config, 'FILE_SUMMARY_WORKERS', 2),
            queue_size=getattr(runtime_config, 'QUEUE_SIZE', 1000),
            filter_batch_size=getattr(runtime_config, 'FILTER_BATCH_SIZE', 100),
            filter_max_wait=getattr(runtime_config, 'FILTER_MAX_WAIT', 3.0),
            indexing_batch_size=getattr(runtime_config, 'INDEXING_BATCH_SIZE', 100),
            collector_batch_size=getattr(runtime_config, 'COLLECTOR_BATCH_SIZE', 10),
            collector_max_wait=getattr(runtime_config, 'COLLECTOR_MAX_WAIT', 0.5),
            python_chunk_lines=getattr(runtime_config, 'PYTHON_CHUNK_LINES', 40),
            python_chunk_overlap=getattr(runtime_config, 'PYTHON_CHUNK_OVERLAP', 15),
            python_max_chars=getattr(runtime_config, 'PYTHON_MAX_CHARS', 1500),
            doc_chunk_size=getattr(runtime_config, 'DOC_CHUNK_SIZE', 512),
            doc_chunk_overlap=getattr(runtime_config, 'DOC_CHUNK_OVERLAP', 50),
            config_chunk_size=getattr(runtime_config, 'CONFIG_CHUNK_SIZE', 512),
            config_chunk_overlap=getattr(runtime_config, 'CONFIG_CHUNK_OVERLAP', 50),
            file_summary_max_chunks=getattr(runtime_config, 'FILE_SUMMARY_MAX_CHUNKS', 20),
            search_default_top_k=getattr(runtime_config, 'SEARCH_DEFAULT_TOP_K', 10),
            workspace_path=runtime_config.WORKSPACE_PATH,
            monitor_interval=getattr(runtime_config, 'MONITOR_INTERVAL', 10.0),
        )
