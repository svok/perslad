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


class PipelineConfig(BaseModel):
    """Full pipeline configuration."""
    llm: LLMConfig
    embedding: EmbeddingConfig
    storage: StorageConfig
    
    # Indexation pipeline
    enrich_workers: int = Field(default=2)
    parse_workers: int = Field(default=1)
    indexing_workers: int = Field(default=2)
    
    # Runtime
    workspace_path: str = Field(default="./workspace")
    queue_size: int = Field(default=1000)
    
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
            ),
            enrich_workers=getattr(runtime_config, 'ENRICH_WORKERS', 2),
            parse_workers=getattr(runtime_config, 'PARSE_WORKERS', 1),
            indexing_workers=getattr(runtime_config, 'INDEXING_WORKERS', 2),
            workspace_path=runtime_config.WORKSPACE_PATH,
            queue_size=getattr(runtime_config, 'QUEUE_SIZE', 1000),
        )
