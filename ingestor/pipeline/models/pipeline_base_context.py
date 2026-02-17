"""
Pipeline Base Context

Абстрактный базовый класс для контекстов пайплайнов (индексации и поиска).
Предоставляет общую структуру данных и логику обработки.
"""

from abc import abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Literal
import time

from ingestor.core.models.chunk import Chunk

PipelineContextStatus = Literal["none", "pending", "success", "skipped", "error"]

@dataclass(kw_only=True)
class PipelineBaseContext:
    """
    Абстрактный базовый класс для контекстов пайплайнов.

    Предоставляет общую структуру данных и логику:
    - chunks: список чанков
    - status: статус обработки
    - error: сообщение об ошибке
    - has_errors/erros: флаги ошибок
    """

    # Результаты обработки (должны быть определены в дочерних классах)
    chunks: List['Chunk'] = None

    # Статус обработки (должен быть определен в дочерних классах)
    status: PipelineContextStatus = ''

    # Сообщение об ошибке
    error: Optional[str] = None

    # Флаги ошибок
    has_errors: bool = False
    errors: List[str] = field(default_factory=list)

    # Временные метки
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    @abstractmethod
    def mark_success(self) -> None:
        """Отметить успешную обработку."""
        pass

    @abstractmethod
    def mark_skipped(self, reason: str = "") -> None:
        """Отметить пропуск обработки."""
        pass

    @abstractmethod
    def mark_error(self, error: str) -> None:
        """Отметить ошибку обработки."""
        pass

    def is_processable(self) -> bool:
        """
        Проверка готовности к обработке.

        Возвращаем true, если:
        - статус pending или success
        - нет критических ошибок
        - есть хотя бы один валидный чанк
        """
        return self.status in ("pending", "success") and not self.has_errors

    def has_valid_chunks(self) -> bool:
        """
        Есть ли валидные чанки для обработки.

        Чанк считается валидным, если он содержит непустой контент.
        """
        return len(self.chunks) > 0 and any(
            c.content and c.content.strip() for c in self.chunks
        )
