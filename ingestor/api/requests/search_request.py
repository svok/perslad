from typing import List, Optional
from pydantic import BaseModel

class SearchRequest(BaseModel):
    """Запрос на поиск по embedding или тексту."""
    query: Optional[str] = None
    query_embedding: Optional[List[float]] = None
    top_k: int = 5
