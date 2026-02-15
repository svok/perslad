from dataclasses import dataclass


@dataclass
class ScannedFile:
    """Результат сканирования одного файла."""
    path: str
    relative_path: str
    size_bytes: int
    extension: str
