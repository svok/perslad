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
    PGVECTOR_DIMENSIONS: int = Field(default=1536) # The number MUST differ from real to track possible errors

    def to_dict(self) -> dict:
        """Возвращает полный конфиг как словарь."""
        return self.model_dump()

    def to_dict_public(self) -> dict:
        """Возвращает конфиг без секретных полей."""
        return self.model_dump(exclude={"POSTGRES_PASSWORD"})


storage_config = StorageConfig()
