from typing import List
from pydantic import BaseModel

class SearchRequest(BaseModel):
    """Запрос на поиск по embedding."""
    query_embedding: List[float]
    top_k: int = 5
