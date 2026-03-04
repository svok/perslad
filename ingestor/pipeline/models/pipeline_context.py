from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from ingestor.core.ports.storage import BaseStorage
from llama_index.core.embeddings import BaseEmbedding
from llama_index.core.llms import LLM
from ingestor.pipeline.utils.text_splitter_helper import TextSplitterHelper
from ingestor.services.lock import LLMLockManager


@dataclass
class PipelineContext:
    """Контекст с зависимостями, передаваемый фабрикам стадий"""
    
    workspace_path: Path
    storage: BaseStorage
    llm: LLM | None
    lock_manager: LLMLockManager | None
    embed_model: BaseEmbedding | None
    vector_store: Any  # Vector store (PGVectorStore, SimpleVectorStore, etc.)
    text_splitter_helper: TextSplitterHelper
    config: Dict[str, Any]
