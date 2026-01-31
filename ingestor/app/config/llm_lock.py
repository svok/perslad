from pydantic_settings import BaseSettings
from pydantic import Field


class LLMLockConfig(BaseSettings):
    AGENT_SYSTEM_URL: str | None = Field(default=None)

llm_lock = LLMLockConfig()
