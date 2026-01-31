from pydantic_settings import BaseSettings
from pydantic import Field


class StorageConfig(BaseSettings):
    STORAGE_TYPE: str = Field(default="memory")

    # PostgreSQL connection
    POSTGRES_HOST: str = Field(default="postgres")
    POSTGRES_PORT: int = Field(default=5432)
    POSTGRES_DB: str = Field(default="rag")
    POSTGRES_USER: str = Field(default="rag")
    POSTGRES_PASSWORD: str = Field(default="rag")

    # Vector storage
    USE_PGVECTOR: bool = Field(default=True)
    PGVECTOR_DIMENSIONS: int = Field(default=1536)

    class Config:
        env_prefix = "INGEST_"
        case_sensitive = False


storage = StorageConfig()
