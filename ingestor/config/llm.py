from pydantic_settings import BaseSettings
from pydantic import Field


class LLMConfig(BaseSettings):
    LLM_URL: str | None = Field(default=None)
    LLM_API_KEY: str = Field(default="sk-dummy", alias="OPENAI_API_KEY")
    LLM_SERVED_MODEL_NAME: str = Field(default="default-model")

llm_config = LLMConfig()
