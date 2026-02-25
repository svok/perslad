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

    # Connection pool
    POSTGRES_POOL_MIN_SIZE: int = Field(default=2)
    POSTGRES_POOL_MAX_SIZE: int = Field(default=10)
    POSTGRES_POOL_TIMEOUT: float = Field(default=30.0)
    POSTGRES_OPERATION_TIMEOUT: float = Field(default=60.0)
    POSTGRES_QUERY_TIMEOUT: float = Field(default=10.0)
    POSTGRES_ACQUIRE_TIMEOUT: float = Field(default=5.0)

    # Vector storage
    USE_PGVECTOR: bool = Field(default=True)
    PGVECTOR_DIMENSIONS: int = Field(default=1536)
    VECTOR_STORE_TABLE_NAME: str = Field(default="chunks_vectors")

    def to_dict(self) -> dict:
        """Возвращает полный конфиг как словарь."""
        return self.model_dump()

    def to_dict_public(self) -> dict:
        """Возвращает конфиг без секретных полей."""
        return self.model_dump(exclude={"POSTGRES_PASSWORD"})


storage_config = StorageConfig()
