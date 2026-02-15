"""API endpoints for LLM service."""

from dataclasses import dataclass


@dataclass
class LLM:
    MODELS: str = "/models"
    CHAT_COMPLETIONS: str = "/chat/completions"
    ROOT: str = "/"
