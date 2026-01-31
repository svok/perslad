from pydantic_settings import BaseSettings
from pydantic import Field


class RuntimeConfig(BaseSettings):
    ENV: str = Field(default="dev")
    LOG_LEVEL: str = Field(default="INFO")
    WORKSPACE_PATH: str = Field(default="/workspace")
    INGESTOR_PORT: int = Field(default=8001)

    class Config:
        env_prefix = "INGEST_"
        case_sensitive = False


runtime = RuntimeConfig()
