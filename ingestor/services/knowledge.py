"""
Knowledge Port - интерфейс между ingestor и agent.

Это единственная точка интеграции между агентом и знаниями.
Agent работает только через этот порт.
Storage полностью скрыт.

Использует KnowledgeSearchPipeline для поиска и прямые запросы к storage
для чтения метаданных (get_file_context, get_project_overview).
"""

from typing import List, Dict, Any

from infra.logger import get_logger
from ingestor.pipeline.models.pipeline_context import PipelineContext
from ingestor.pipeline.knowledge_search.pipeline import KnowledgeSearchPipeline

log = get_logger("ingestor.knowledge_port")


class KnowledgePort:
    """
    Предоставляет агенту доступ к знаниям.
    
    Гарантирует, что агент НИКОГДА не получает всю базу.
    Типичные payloads: 10-50 KB.
    """

    def __init__(
        self,
        pipeline_context: PipelineContext,
        search_pipeline: KnowledgeSearchPipeline = None
    ) -> None:
        self.context = pipeline_context
        
        # Используем переданный пайплайн или создаем свой
        if search_pipeline:
            self.search_pipeline = search_pipeline
        else:
            # Используем упрощенную версию KnowledgeSearchPipeline (которая работает через стадии)
            # ВАЖНО: Если инстанцируем здесь, нужно убедиться, что пайплайн НЕ запущен повторно
            # Лучшая практика: создавать KnowledgeSearchPipeline отдельно и передавать его сюда.
            self.search_pipeline = KnowledgeSearchPipeline(self.context)

    async def search_by_embedding(
        self,
        query_embedding: List[float],
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Поиск по embedding (cosine similarity).
        
        NOTE: Это legacy метод. Новый код должен использовать search().
        """
        log.info("knowledge_port.search.embedding", top_k=top_k)
        
        # Прямой вызов storage для обратной совместимости
        chunks = await self.context.storage.search_vector(query_embedding, top_k)
        
        results = []
        for chunk in chunks:
            # Вычисляем similarity явно для ответа (так как search_vector вернул уже отсортированные)
            # В идеале DB возвращает similarity, но у нас пока просто чанки
            results.append({
                "chunk_id": chunk.id,
                "file_path": chunk.file_path,
                "content": chunk.content,
                "summary": chunk.summary,
                "purpose": chunk.purpose,
                "similarity": 0.0,  # TODO: DB должен возвращать score
                "metadata": chunk.metadata,
            })
        
        log.info("knowledge_port.search.complete", results_count=len(results))
        return results

    async def search(self, query: str, top_k: int = 5) -> Dict[str, Any]:
        """
        Поиск по текстовому запросу через пайплайн.
        
        Args:
            query: Текстовый запрос пользователя
            top_k: Количество результатов для возврата
        
        Returns:
            Dictionary с результатами поиска и метаданными
        """
        if not query or not query.strip():
            return {"results": [], "error": "Empty query"}

        # Пайплайн сам разберется с эмбеддингом и поиском
        # Запуск пайплайна для одного запроса
        results = await self.search_pipeline.search(query, top_k=top_k)
        
        return results

    async def get_file_context(
        self,
        file_path: str,
    ) -> Dict[str, Any]:
        """
        Получить контекст файла (summary + chunks).
        Использует прямой доступ к storage, так как это просто чтение.
        """
        log.info("knowledge_port.file_context", file=file_path)
        
        storage = self.context.storage
        
        # Получаем file summary
        file_summary = await storage.get_file_summary(file_path)
        
        # Получаем chunks
        chunks = await storage.get_chunks_by_file(file_path)
        
        return {
            "file_path": file_path,
            "summary": file_summary.summary if file_summary else None,
            "chunks": [
                {
                    "chunk_id": c.id,
                    "content": c.content,
                    "summary": c.summary,
                    "chunk_type": c.chunk_type,
                }
                for c in chunks
            ],
        }

    async def get_project_overview(self) -> Dict[str, Any]:
        """
        Получить обзор проекта (high-level).
        Использует прямой доступ к storage.
        """
        log.info("knowledge_port.project_overview")
        
        storage = self.context.storage
        
        stats = await storage.get_stats()
        module_summaries = await storage.get_all_module_summaries()
        
        return {
            "stats": stats,
            "modules": [
                {
                    "module_path": m.module_path,
                    "summary": m.summary,
                    "files_count": len(m.file_paths),
                }
                for m in module_summaries
            ],
        }
