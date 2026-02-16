from dataclasses import dataclass, field
from typing import Dict


@dataclass
class FileSummary:
    """Суммаризация на уровне файла."""
    file_path: str
    summary: str
    metadata: Dict = field(default_factory=dict)
