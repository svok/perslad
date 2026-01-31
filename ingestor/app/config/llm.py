from pydantic_settings import BaseSettings
from pydantic import Field


class LLMConfig(BaseSettings):
    LOCAL_LLM_BASE_URL: str | None = Field(default=None)
    CLOUD_LLM_BASE_URL: str | None = Field(default=None)
    OPENAI_API_KEY: str = Field(default="sk-dummy")

    # Embedding settings
    OPENAI_EMBEDDING_MODEL: str = Field(default="text-embedding-3-small")

    class Config:
        env_prefix = "INGEST_"
        case_sensitive = False


llm = LLMConfig()
