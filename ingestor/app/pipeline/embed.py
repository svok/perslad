"""
Stage 4: Embeddings

Задача: посчитать embeddings для чанков.
NO LLM reasoning (но использует embedding endpoint).

В MVP можно делать даже при LLM lock, если это отдельный endpoint.
"""

from typing import List

from llama_index.embeddings.openai import OpenAIEmbedding

from infra.logger import get_logger
from ingestor.app.storage import Chunk

log = get_logger("ingestor.pipeline.embed")


class EmbedStage:
    """
    Вычисляет embeddings для чанков.
    """

    def __init__(self, embed_model: OpenAIEmbedding) -> None:
        self.embed_model = embed_model

    async def run(self, chunks: List[Chunk]) -> List[Chunk]:
        """
        Вычисляет embeddings для всех чанков.
        """
        log.info("embed.start", chunks_count=len(chunks))
        
        embedded = 0
        skipped = 0
        
        # Батчим для эффективности
        batch_size = 10
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            
            try:
                await self._embed_batch(batch)
                embedded += len(batch)
            except Exception as e:
                log.warning(
                    "embed.batch.failed",
                    batch_start=i,
                    batch_size=len(batch),
                    error=str(e),
                )
                skipped += len(batch)
        
        log.info(
            "embed.complete",
            embedded=embedded,
            skipped=skipped,
        )
        
        return chunks

    async def _embed_batch(self, chunks: List[Chunk]) -> None:
        """
        Вычисляет embeddings для батча чанков.
        """
        # Подготавливаем тексты
        texts = []
        for chunk in chunks:
            # Используем summary если есть, иначе content
            text = chunk.summary or chunk.content[:500]
            texts.append(text)
        
        # Вызываем embedding model
        embeddings = await self.embed_model.aget_text_embedding_batch(texts)
        
        # Сохраняем embeddings
        for chunk, embedding in zip(chunks, embeddings):
            chunk.embedding = embedding
        
        log.debug("embed.batch.complete", batch_size=len(chunks))
