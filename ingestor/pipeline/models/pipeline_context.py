from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from pydantic import SecretStr

from infra.managers.base import BaseManager
from ingestor.core.ports.storage import BaseStorage
from ingestor.services.lock import LLMLockManager
from ingestor.pipeline.utils.text_splitter_helper import TextSplitterHelper

@dataclass(frozen=True)
class PipelineContext:
    """Контекст с зависимостями, передаваемый фабрикам стадий"""
    workspace_path: Path
    storage: BaseStorage
    llm: BaseManager | None
    lock_manager: LLMLockManager | None
    embed_url: str
    embed_api_key: str  # Changed from SecretStr to str for simplicity
    text_splitter_helper: TextSplitterHelper
    config: Dict[str, Any]
    embed_model: Any = None
