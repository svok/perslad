from dataclasses import dataclass, field
from typing import Dict, List, Optional

@dataclass
class Chunk:
    """Базовый чанк кода/документации."""
    id: str
    file_path: str
    content: str
    start_line: int
    end_line: int
    chunk_type: str  # "code", "doc", "config"
    
    # Enrichment (from local LLM)
    summary: Optional[str] = None
    purpose: Optional[str] = None
    
    # Embeddings
    embedding: Optional[List[float]] = None
    
    # Metadata
    metadata: Dict = field(default_factory=dict)
