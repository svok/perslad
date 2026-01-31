from pydantic_settings import BaseSettings
from pydantic import Field


class IngestorConfig(BaseSettings):
    # runtime
    ENV: str = Field(default="dev")
    LOG_LEVEL: str = Field(default="INFO")

    # repo / workspace
    WORKSPACE_PATH: str = Field(default="/workspace")

    # LLM endpoints (заготовка)
    LOCAL_LLM_BASE_URL: str | None = None
    CLOUD_LLM_BASE_URL: str | None = None

    # LLM lock endpoint (agent)
    AGENT_SYSTEM_URL: str | None = None

    class Config:
        env_prefix = "INGEST_"
        case_sensitive = False


config = IngestorConfig()
