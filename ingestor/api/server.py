"""
Ingestor HTTP API

Предоставляет:
- /system/llm_lock - endpoint для управления блокировкой от агента
- /health - health check
- /stats - статистика storage
- /knowledge/* - Knowledge Port endpoints для агента
- /ingest - запуск индексации файла
- /status/{job_id} - статус задачи индексации
"""

from typing import Dict, Any

from fastapi import FastAPI, APIRouter

from infra.config.endpoints.ingestor import Ingestor
from infra.logger import get_logger
from ingestor.adapters.embedding_model import EmbeddingModel
from ingestor.api.requests.llm_lock_request import LLMLockRequest
from ingestor.api.requests.search_request import SearchRequest
from ingestor.core.ports.storage import BaseStorage
from ingestor.services.knowledge import KnowledgePort
from ingestor.services.lock import LLMLockManager

log = get_logger("ingestor.api")


class IngestorAPI:
    """
    HTTP API для ingestor.
    """

    def __init__(
        self,
        lock_manager: LLMLockManager,
        storage: BaseStorage,
        knowledge_port: KnowledgePort,
        embedding_model: EmbeddingModel,
    ) -> None:
        self.lock_manager = lock_manager
        self.storage = storage
        self.knowledge_port = knowledge_port
        self.embedding_model = embedding_model
        self.app = FastAPI(title="Ingestor API")
        self.router = APIRouter(prefix="/v1")
        
        self._setup_routes()

    def _setup_routes(self) -> None:
        """Настраивает маршруты."""
        
        @self.router.get(Ingestor.ROOT)
        async def root() -> Dict[str, Any]:
            return {
                "service": "Ingestor",
                "status": "running",
            }
        
        @self.router.get(Ingestor.HEALTH)
        async def health() -> Dict[str, Any]:
            stats = await self.storage.get_stats()
            return {
                "status": "ready",
                "storage": stats,
            }
        
        @self.router.post(Ingestor.LLM_LOCK)
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
        
        @self.router.get(Ingestor.LLM_LOCK)
        async def get_llm_lock() -> Dict[str, Any]:
            """
            Получить текущее состояние блокировки.
            """
            return self.lock_manager.get_status()
        
        @self.router.get(Ingestor.STATS)
        async def get_stats() -> Dict[str, Any]:
            """
            Статистика storage.
            """
            return await self.storage.get_stats()
        
        @self.router.get(Ingestor.CHUNKS)
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
        
        @self.router.post(Ingestor.SEARCH)
        async def search_knowledge(request: SearchRequest) -> Dict[str, Any]:
            """
            Поиск по текстовому запросу или embedding.
            Использует KnowledgeSearchPipeline для полного цикла обработки:
            query -> chunking -> embedding -> DB search -> ranking.
            """
            if request.query:
                # Обрезаем очень длинные запросы до разумного лимита для embedding модели (512 токенов ~ 500 символов)
                query_text = request.query
                if len(query_text) > 500:
                    query_text = query_text[:500] + "..."
                    log.info(f"Truncated query to 500 chars for embedding")
                
                # Пайплайн сам разобьет запрос на чанки и вычислит embeddings
                results = await self.knowledge_port.search(
                    query=query_text,
                    top_k=request.top_k
                )
                return results
            elif request.query_embedding:
                # Если готовый embedding — используем прямой поиск (для совместимости)
                results = await self.knowledge_port.search_by_embedding(
                    query_embedding=request.query_embedding,
                    top_k=request.top_k,
                )
                return {"results": results}
            else:
                return {"results": [], "error": "query or query_embedding required"}
        
        @self.router.get(Ingestor.FILE)
        async def get_file_context(file_path: str) -> Dict[str, Any]:
            """
            Получить контекст файла.
            """
            return await self.knowledge_port.get_file_context(file_path)
        
        @self.router.get(Ingestor.OVERVIEW)
        async def get_project_overview() -> Dict[str, Any]:
            """
            Получить обзор проекта.
            """
            return await self.knowledge_port.get_project_overview()

        self.app.include_router(self.router)
