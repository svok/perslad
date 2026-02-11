"""
Knowledge Port - интерфейс между ingestor и agent.

Это единственная точка интеграции между агентом и знаниями.
Agent работает только через этот порт.
Storage полностью скрыт.

MVP: прямой доступ к storage внутри ingestor.
Будущее: gRPC API, отдельный адаптер на стороне агента.
"""

import math
from typing import List, Dict, Any

from infra.logger import get_logger
from ingestor.adapters import BaseStorage
from ingestor.pipeline.impl.text_splitter_helper import TextSplitterHelper
from ingestor.pipeline.knowledge_search.pipeline import KnowledgeSearchPipeline

log = get_logger("ingestor.knowledge_port")


class KnowledgePort:
    """
    Предоставляет агенту доступ к знаниям.
    
    Гарантирует, что агент НИКОГДА не получает всю базу.
    Типичные payloads: 10-50 KB.
    
    Использует KnowledgeSearchPipeline для оптимизированного поиска.
    """

    def __init__(
        self,
        storage: BaseStorage,
        embed_model=None
    ) -> None:
        self.storage = storage
        self.embed_model = embed_model
        
        # Создаем вспомогательные компоненты
        text_splitter_helper = TextSplitterHelper()
        self.search_pipeline = KnowledgeSearchPipeline(
            storage=storage,
            text_splitter_helper=text_splitter_helper,
            embedding_model=embed_model,
            query_chunk_size=2000,
            top_k_per_query=5
        )

    async def search_by_embedding(
        self,
        query_embedding: List[float],
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Поиск по embedding (cosine similarity).
        
        Возвращает top_k наиболее релевантных чанков.
        
        NOTE: Это метод для backward compatibility.
        В production, use search() which handles query chunking automatically.
        """
        log.info("knowledge_port.search.embedding", top_k=top_k)
        
        chunks = await self.storage.get_all_chunks()
        
        # Фильтруем чанки с embeddings
        chunks_with_emb = [c for c in chunks if c.embedding is not None]
        
        if not chunks_with_emb:
            log.warning("knowledge_port.search.no_embeddings")
            return []
        
        # Вычисляем cosine similarity
        scored_chunks = []
        for chunk in chunks_with_emb:
            similarity = self._cosine_similarity(query_embedding, chunk.embedding)
            scored_chunks.append((similarity, chunk))
        
        # Сортируем по similarity
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        
        # Берём top_k
        top_chunks = scored_chunks[:top_k]
        
        # Форматируем результат
        results = []
        for similarity, chunk in top_chunks:
            results.append({
                "chunk_id": chunk.id,
                "file_path": chunk.file_path,
                "content": chunk.content,
                "summary": chunk.summary,
                "purpose": chunk.purpose,
                "similarity": similarity,
                "metadata": chunk.metadata,
            })
        
        log.info("knowledge_port.search.complete", results_count=len(results))
        return results

    async def search(self, query: str, top_k: int = 5) -> Dict[str, Any]:
        """
        Поиск по текстовому запросу (с авто-эмбеддингом и чанкованием).
        
        Args:
            query: Текстовый запрос пользователя
            top_k: Количество результатов для возврата
        
        Returns:
            Dictionary с результатами поиска и метаданными
        """
        if not query or not query.strip():
            return {"results": [], "error": "Empty query"}

        # Если есть embed_model - используем его, иначе считаем самим
        embedding = await self.embed_model.get_embedding(query)

        # Используем KnowledgeSearchPipeline
        results = await self.search_pipeline.search(top_k=top_k, query=embedding)
        
        # Форматируем результат для API
        formatted_results = [
            {
                "chunk_id": r["chunk_id"],
                "file_path": r["file_path"],
                "content": r["content"],
                "summary": r["summary"],
                "purpose": r["purpose"],
                "similarity": r["similarity"],
                "metadata": r["metadata"],
            }
            for r in results["results"]
        ]
        
        return {
            "results": formatted_results,
            "chunks_analyzed": results["chunks_analyzed"],
            "embeddings_generated": results["embeddings_generated"],
        }

    async def get_file_context(
        self,
        file_path: str,
    ) -> Dict[str, Any]:
        """
        Получить контекст файла (summary + chunks).
        """
        log.info("knowledge_port.file_context", file=file_path)
        
        # Получаем file summary
        file_summary = await self.storage.get_file_summary(file_path)
        
        # Получаем chunks
        chunks = await self.storage.get_chunks_by_file(file_path)
        
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
        
        Возвращает:
        - статистику
        - module summaries
        - структуру проекта
        """
        log.info("knowledge_port.project_overview")
        
        stats = await self.storage.get_stats()
        module_summaries = await self.storage.get_all_module_summaries()
        
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

    def _cosine_similarity(
        self,
        vec1: List[float],
        vec2: List[float],
    ) -> float:
        """
        Вычисляет cosine similarity между двумя векторами.
        """
        if len(vec1) != len(vec2):
            return 0.0
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(dot_product / (norm1 * norm2))
