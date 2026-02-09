from dataclasses import dataclass, field
from typing import Dict, List

@dataclass
class ModuleSummary:
    """Суммаризация на уровне модуля/пакета."""
    module_path: str
    summary: str
    file_paths: List[str]
    metadata: Dict = field(default_factory=dict)
