from pydantic_settings import BaseSettings
from pydantic import Field


class LLMLockConfig(BaseSettings):
    AGENT_SYSTEM_URL: str | None = Field(default=None)

    class Config:
        env_prefix = "INGEST_"
        case_sensitive = False


llm_lock = LLMLockConfig()
