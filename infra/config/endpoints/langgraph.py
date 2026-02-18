"""API endpoints for LangGraph service."""

from dataclasses import dataclass


@dataclass
class LangGraph:
    HEALTH: str = "/health"
    MODELS: str = "/models"
    CHAT_COMPLETIONS: str = "/chat/completions"
    DEBUG_TOOLS: str = "/debug/tools"
    ROOT: str = "/"
