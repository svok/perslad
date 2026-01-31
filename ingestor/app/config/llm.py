from pydantic_settings import BaseSettings
from pydantic import Field


class LLMConfig(BaseSettings):
    LOCAL_LLM_BASE_URL: str | None = Field(default=None)
    CLOUD_LLM_BASE_URL: str | None = Field(default=None)
    OPENAI_API_KEY: str = Field(default="sk-dummy")

    # Embedding settings
    OPENAI_API_BASE: str | None = Field(default=None)
    OPENAI_EMBEDDING_MODEL: str = Field(default="embed-model")

llm = LLMConfig()
