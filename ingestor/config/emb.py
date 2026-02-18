from pydantic_settings import BaseSettings
from pydantic import Field


class EMBConfig(BaseSettings):
    EMB_URL: str | None = Field(default=None)
    EMB_API_KEY: str = Field(default="sk-dummy", alias="OPENAI_API_KEY")
    EMB_SERVED_MODEL_NAME: str = Field(default="embed-model")

emb_config = EMBConfig()
