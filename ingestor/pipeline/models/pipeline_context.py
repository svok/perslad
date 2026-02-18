from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from infra.managers.base import BaseManager
from ingestor.adapters.embedding_model import EmbeddingModel
from ingestor.core.ports.storage import BaseStorage
from ingestor.pipeline.utils.text_splitter_helper import TextSplitterHelper
from ingestor.services.lock import LLMLockManager


@dataclass(frozen=True)
class PipelineContext:
    """Контекст с зависимостями, передаваемый фабрикам стадий"""
    workspace_path: Path
    storage: BaseStorage
    llm: BaseManager | None
    lock_manager: LLMLockManager | None
    embed_model: EmbeddingModel | None
    text_splitter_helper: TextSplitterHelper
    config: Dict[str, Any]
