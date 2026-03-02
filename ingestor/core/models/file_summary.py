from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class FileSummary:
    """File-level summary generated from chunk summaries using LLM."""
    file_path: str
    summary: str
    metadata: Dict[str, Optional[object]] = field(default_factory=dict)
