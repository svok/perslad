from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional, get_args

EventTypes = Literal["create", "modify", "delete", "scan", "rename"]

@dataclass
class FileEvent:
    """Унифицированное событие файла"""
    path: Path                    # Относительный путь к файлу
    event_type: EventTypes
    abs_path: Optional[Path] = None  # Абсолютный путь (для удобства)
    EVENT_TYPES = get_args(EventTypes)


    def __post_init__(self):
        if self.abs_path is None and not self.path.is_absolute():
            # Будет установлено позже, когда знаем workspace
            pass

    @property
    def is_deletion(self) -> bool:
        return self.event_type == "delete"
