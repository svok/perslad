"""API endpoints for Ingestor service."""

from dataclasses import dataclass


@dataclass
class Ingestor:
    ROOT: str = "/"
    HEALTH: str = "/health"
    SEARCH: str = "/knowledge/search"
    STATS: str = "/stats"
    CHUNKS: str = "/chunks"
    FILE: str = "/knowledge/file/{file_path:path}"
    OVERVIEW: str = "/knowledge/overview"
    LLM_LOCK: str = "/system/llm_lock"
