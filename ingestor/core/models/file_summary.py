from dataclasses import dataclass, field
from typing import Dict, List

@dataclass
class FileSummary:
    """Суммаризация на уровне файла."""
    file_path: str
    summary: str
    chunk_ids: List[str]
    metadata: Dict = field(default_factory=dict)
