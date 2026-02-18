"""
Pipeline Search Context

Контекст для поискового пайплайна.
Наследуется от BasePipelineContext.
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional
import time

from ingestor.core.models.chunk import Chunk

# Import from pipeline base
from .pipeline_base_context import PipelineBaseContext


@dataclass(kw_only=True)
class PipelineSearchContext(PipelineBaseContext):
    """
    Контекст для поискового пайплайна.

    Наследует поля:
    - chunks: список чанков
    - status: статус обработки
    - error: сообщение об ошибке
    - has_errors/erros: флаги ошибок
    - created_at/updated_at: временные метки

    Добавляет специфичные поля:
    - query_data: данные поискового запроса
    - result: результаты поиска
    """

    # Специфичные поля для search pipeline
    query_data: Dict[str, Any]
    result: Optional[list] = None

    def mark_success(self) -> None:
        """Отметить успешную обработку."""
        self.status = "success"
        self.updated_at = time.time()

    def mark_skipped(self, reason: str = "") -> None:
        """Отметить пропуск обработки."""
        self.status = "skipped"
        self.error = reason
        self.updated_at = time.time()

    def mark_error(self, error: str) -> None:
        """Отметить ошибку обработки."""
        self.status = "error"
        self.error = error
        self.has_errors = True
        self.errors.append(error)
        self.updated_at = time.time()
