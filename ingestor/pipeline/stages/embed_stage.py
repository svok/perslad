from typing import List

import httpx
from pydantic import SecretStr

from ingestor.pipeline.base.processor_stage import ProcessorStage
from ingestor.core.models.chunk import Chunk
from infra.config.endpoints.embedding import Embedding


class EmbedChunksStage(ProcessorStage):
    """
    Класс-обертка для интеграции в пайплайн.
    """
    def __init__(self, embed_url: str, embed_api_key: SecretStr, max_workers: int = 2, embed_model = None):
        super().__init__("embed", max_workers)
        self.embed_model = embed_model
        self.embed_url = embed_url.rstrip('/')
        self.api_key = embed_api_key
        # Создаем клиент только если нет готовой модели
        self._client = None
        if not self.embed_model:
            self._client = httpx.AsyncClient(
                timeout=60.0,
                headers={"Authorization": f"Bearer {self.api_key}"}
            )

    async def process(self, chunks: List[Chunk]) -> List[Chunk]:
        # Если передана модель (например, Mock или EmbeddingModel адаптер), используем её
        if self.embed_model:
            return await self.embed_model.run(chunks)
        
        # Воркер вызывает этот метод для каждого сообщения из очереди
        return await self.run(chunks)

    async def stop(self) -> None:
        # Переопределяем stop, чтобы закрыть соединения
        if self._client:
            await self._client.aclose()
        await super().stop()

    async def run(self, chunks: List[Chunk]) -> List[Chunk]:
        """
        Вычисляет embeddings для списка чанков.
        """
        # Фильтруем чанки: если нет ни саммари, ни контента, эмбеддинг невозможен
        valid_chunks = [c for c in chunks if (c.summary or c.content or "").strip()]
        
        if not valid_chunks:
            return chunks  # Нечего эмбеддить
            
        # Подготавливаем тексты для эмбеддинга
        texts = []
        for c in valid_chunks:
            # Обрезаем слишком длинные тексты, чтобы не превысить контекст модели
            text = (c.summary or c.content or "")[:1000].strip()
            # Если после обрезки стало пусто (маловероятно из-за фильтрации выше),
            # добавляем заглушку, чтобы не упал весь батч
            texts.append(text if text else "empty")

        # Отправка запроса
        response = await self._client.post(
            Embedding.EMBEDDINGS,
            json={
                "model": "embed-model",
                "input": texts,
            }
        )
        response.raise_for_status()
        result = response.json()

        embeddings_data = result.get("data", [])

        if len(embeddings_data) != len(valid_chunks):
            raise ValueError(f"API returned {len(embeddings_data)} embeddings, but we sent {len(valid_chunks)} texts")

        # Записываем эмбеддинги в объекты
        for i, chunk in enumerate(valid_chunks):
            # В зависимости от API, структура может быть: data[i]['embedding'] или просто список
            emb_item = embeddings_data[i]
            if isinstance(emb_item, dict) and "embedding" in emb_item:
                chunk.embedding = emb_item["embedding"]
            elif isinstance(emb_item, list):
                chunk.embedding = emb_item
            else:
                self.log.error("embed.format_error", chunk_id=chunk.id, data=str(emb_item)[:100])
                continue

        return chunks
