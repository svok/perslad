from dataclasses import dataclass
from pathlib import Path


@dataclass
class FileInfo:
    """Информация о файле для обработки в конвейере"""
    path: Path
    relative_path: str
    size: int = 0
    mtime: float = 0.0
    checksum: str = ""
