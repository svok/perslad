"""
Pipeline File Context

Единый контейнер для передачи информации о файле через весь pipeline.
Содержит все метаданные, статус обработки и результаты (чанки).
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Any
import time

from ingestor.core.models.chunk import Chunk
from ingestor.pipeline.models.file_event import EventTypes


@dataclass
class PipelineFileContext:
    """Контекст processing одного файла."""
    
    # Обязательные идентификаторы
    file_path: Path          # Относительный путь (в workspace)
    abs_path: Path           # Абсолютный путь
    event_type: EventTypes   # "scan", "inotify", "full_scan"
    
    # Обогащенные метаданные (заполняются EnrichStage)
    size: int = 0
    mtime: float = 0
    
    # Результаты обработки
    chunks: List['Chunk'] = field(default_factory=list)
    status: str = "pending"  # "pending", "success", "skipped", "error"
    error: Optional[str] = None
    
    # Флаги ошибок (вместо пропуска)
    has_errors: bool = False
    errors: List[str] = field(default_factory=list)
    
    # Временные метки
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    
    # Ссылка на исходное событие (опционально, для отладки)
    raw_event: Optional[Any] = None
    
    def mark_success(self):
        """Отметить успешную обработку."""
        self.status = "success"
        self.updated_at = time.time()
    
    def mark_skipped(self, reason: str = ""):
        """Отметить пропуск файла."""
        self.status = "skipped"
        self.error = reason
        self.updated_at = time.time()
    
    def mark_error(self, error: str):
        """Отметить ошибку обработки."""
        self.status = "error"
        self.error = error
        self.updated_at = time.time()
    
    def has_content(self) -> bool:
        """Есть ли валидные чанки для сохранения."""
        return len(self.chunks) > 0 and any(
            c.content and c.content.strip() for c in self.chunks
        )
