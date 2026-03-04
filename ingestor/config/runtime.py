from pydantic_settings import BaseSettings
from pydantic import Field


class RuntimeConfig(BaseSettings):
    ENV: str = Field(default="dev")
    LOG_LEVEL: str = Field(default="INFO")
    WORKSPACE_PATH: str = Field(default="/workspace")
    INGESTOR_PORT: int = Field(default=8124)

    # Pipeline worker counts
    ENRICH_WORKERS: int = Field(default=2)
    PARSE_WORKERS: int = Field(default=1)
    ENRICH_CHUNKS_WORKERS: int = Field(default=2)
    INDEXING_WORKERS: int = Field(default=2)
    FILE_SUMMARY_WORKERS: int = Field(default=2)

    # Queue and batching
    QUEUE_SIZE: int = Field(default=1000)
    FILTER_BATCH_SIZE: int = Field(default=100)
    FILTER_MAX_WAIT: float = Field(default=3.0)
    INDEXING_BATCH_SIZE: int = Field(default=100)
    COLLECTOR_BATCH_SIZE: int = Field(default=10)
    COLLECTOR_MAX_WAIT: float = Field(default=0.5)

    # Text splitting
    PYTHON_CHUNK_LINES: int = Field(default=40)
    PYTHON_CHUNK_OVERLAP: int = Field(default=15)
    PYTHON_MAX_CHARS: int = Field(default=1500)
    DOC_CHUNK_SIZE: int = Field(default=512)
    DOC_CHUNK_OVERLAP: int = Field(default=50)
    CONFIG_CHUNK_SIZE: int = Field(default=512)
    CONFIG_CHUNK_OVERLAP: int = Field(default=50)

    # Summary generation
    FILE_SUMMARY_MAX_CHUNKS: int = Field(default=20)

    # Search defaults
    SEARCH_DEFAULT_TOP_K: int = Field(default=10)

    # Monitoring
    MONITOR_INTERVAL: float = Field(default=10.0)


runtime_config = RuntimeConfig()
