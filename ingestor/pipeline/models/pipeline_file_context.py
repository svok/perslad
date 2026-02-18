"""
Pipeline File Context

Контекст для индексационного пайплайна.
Наследуется от BasePipelineContext.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import time

from ingestor.core.models.chunk import Chunk

# Import from pipeline base
from .pipeline_base_context import PipelineBaseContext


@dataclass(kw_only=True)
class PipelineFileContext(PipelineBaseContext):
    """
    Контекст для индексационного пайплайна.

    Наследует поля:
    - chunks: список чанков
    - status: статус обработки
    - error: сообщение об ошибке
    - has_errors/erros: флаги ошибок
    - created_at/updated_at: временные метки

    Добавляет специфичные поля:
    - file_path: относительный путь к файлу
    - abs_path: абсолютный путь к файлу
    - event_type: тип события (scan, inotify, full_scan)
    - size: размер файла
    - mtime: время модификации
    - raw_event: исходное событие (опционально)
    """

    # Специфичные поля для file pipeline
    file_path: Path
    abs_path: Path
    event_type: str
    size: int = 0
    mtime: float = 0
    raw_event: Optional[dict] = None

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
