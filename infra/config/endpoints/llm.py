"""API endpoints for LLM service."""

from dataclasses import dataclass


@dataclass
class LLM:
    MODELS: str = "/v1/models"
    CHAT_COMPLETIONS: str = "/v1/chat/completions"
    EMBEDDINGS: str = "/v1/embeddings"
    ROOT: str = "/"
