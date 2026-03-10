from typing import List, Dict, Any, Optional
from pydantic import BaseModel

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[Dict[str, Any]]
    model: str = "langgraph-agent"
    stream: bool = False
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    thinking: bool = False
    tools: Optional[List[Dict[str, Any]]] = None

class HealthStatus(BaseModel):
    status: str
    components: Dict[str, Any]
    ready: bool
    timestamp: int
