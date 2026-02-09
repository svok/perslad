from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict
from ingestor.services.lock import LLMLockManager

@dataclass(frozen=True)
class StageContext:
    """Контекст с зависимостями, передаваемый фабрикам стадий"""
    workspace_path: Path
    storage: Any
    llm: Any
    lock_manager: LLMLockManager
    embed_url: str
    embed_api_key: str
    config: Dict[str, Any]
