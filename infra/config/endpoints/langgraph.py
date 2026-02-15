"""API endpoints for LangGraph service."""

from dataclasses import dataclass


@dataclass
class LangGraph:
    HEALTH: str = "/health"
    CHAT_COMPLETIONS: str = "/v1/chat/completions"
    ROOT: str = "/"
