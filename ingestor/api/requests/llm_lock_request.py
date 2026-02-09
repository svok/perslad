from pydantic import BaseModel

class LLMLockRequest(BaseModel):
    """Запрос на блокировку/разблокировку LLM."""
    locked: bool
    ttl_seconds: float = 300
