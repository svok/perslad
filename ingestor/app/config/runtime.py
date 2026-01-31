from pydantic_settings import BaseSettings
from pydantic import Field


class RuntimeConfig(BaseSettings):
    ENV: str = Field(default="dev")
    LOG_LEVEL: str = Field(default="INFO")
    WORKSPACE_PATH: str = Field(default="/workspace")
    INGESTOR_PORT: int = Field(default=8001)
    EMBED_URL: str = Field(default="http://emb:8001/v1")
    EMBED_API_KEY: str = Field(default="sk-dummy")

runtime = RuntimeConfig()
