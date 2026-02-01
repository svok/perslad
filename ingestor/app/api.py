"""
Ingestor HTTP API

Предоставляет:
- /system/llm_lock - endpoint для управления блокировкой от агента
- /health - health check
- /stats - статистика storage
- /knowledge/* - Knowledge Port endpoints для агента
"""

from typing import Dict, Any, List

from fastapi import FastAPI
from pydantic import BaseModel

from infra.logger import get_logger
from ingestor.adapters import BaseStorage
from ingestor.app.knowledge_port import KnowledgePort
from ingestor.app.llm_lock import LLMLockManager

log = get_logger("ingestor.api")


class LLMLockRequest(BaseModel):
    """Запрос на блокировку/разблокировку LLM."""
    locked: bool
    ttl_seconds: float = 300


class SearchRequest(BaseModel):
    """Запрос на поиск по embedding."""
    query_embedding: List[float]
    top_k: int = 5


class IngestorAPI:
    """
    HTTP API для ingestor.
    """

    def __init__(
        self,
        lock_manager: LLMLockManager,
        storage: BaseStorage,
        knowledge_port: KnowledgePort,
    ) -> None:
        self.lock_manager = lock_manager
        self.storage = storage
        self.knowledge_port = knowledge_port
        self.app = FastAPI(title="Ingestor API")
        
        self._setup_routes()

    def _setup_routes(self) -> None:
        """Настраивает маршруты."""
        
        @self.app.get("/")
        async def root() -> Dict[str, Any]:
            return {
                "service": "Ingestor",
                "status": "running",
            }
        
        @self.app.get("/health")
        async def health() -> Dict[str, Any]:
            stats = await self.storage.get_stats()
            return {
                "status": "healthy",
                "storage": stats,
            }
        
        @self.app.post("/system/llm_lock")
        async def set_llm_lock(request: LLMLockRequest) -> Dict[str, Any]:
            """
            Endpoint для управления блокировкой LLM от агента.
            """
            await self.lock_manager.set_lock(
                locked=request.locked,
                ttl_seconds=request.ttl_seconds,
            )
            
            log.info(
                "api.llm_lock.updated",
                locked=request.locked,
                ttl=request.ttl_seconds,
            )
            
            return {
                "status": "ok",
                "lock_state": self.lock_manager.get_status(),
            }
        
        @self.app.get("/system/llm_lock")
        async def get_llm_lock() -> Dict[str, Any]:
            """
            Получить текущее состояние блокировки.
            """
            return self.lock_manager.get_status()
        
        @self.app.get("/stats")
        async def get_stats() -> Dict[str, Any]:
            """
            Статистика storage.
            """
            return await self.storage.get_stats()
        
        @self.app.get("/chunks")
        async def list_chunks(limit: int = 10) -> Dict[str, Any]:
            """
            Список чанков (для отладки).
            """
            chunks = await self.storage.get_all_chunks()
            
            return {
                "total": len(chunks),
                "chunks": [
                    {
                        "id": c.id,
                        "file_path": c.file_path,
                        "chunk_type": c.chunk_type,
                        "has_summary": c.summary is not None,
                        "has_embedding": c.embedding is not None,
                    }
                    for c in chunks[:limit]
                ],
            }
        
        # === Knowledge Port Endpoints ===
        
        @self.app.post("/knowledge/search")
        async def search_knowledge(request: SearchRequest) -> Dict[str, Any]:
            """
            Поиск по embedding (для агента).
            """
            results = await self.knowledge_port.search_by_embedding(
                query_embedding=request.query_embedding,
                top_k=request.top_k,
            )
            return {"results": results}
        
        @self.app.get("/knowledge/file/{file_path:path}")
        async def get_file_context(file_path: str) -> Dict[str, Any]:
            """
            Получить контекст файла.
            """
            return await self.knowledge_port.get_file_context(file_path)
        
        @self.app.get("/knowledge/overview")
        async def get_project_overview() -> Dict[str, Any]:
            """
            Получить обзор проекта.
            """
            return await self.knowledge_port.get_project_overview()
