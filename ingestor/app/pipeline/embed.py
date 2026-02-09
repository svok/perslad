"""
Stage 4: Embeddings

Задача: посчитать embeddings для чанков.
Использует локальный embedding endpoint без llama-index.
"""

from typing import List

import httpx

from infra.logger import get_logger
from ingestor.app.storage import Chunk

log = get_logger("ingestor.pipeline.embed")

class EmbedStage:
    """
    Вычисляет embeddings для чанков с помощью локального или удаленного endpoint.
    """

    def __init__(self, embed_url: str, api_key: str) -> None:
        self.embed_url = embed_url.rstrip('/')
        self.api_key = api_key
        # Создаем клиент один раз для повторного использования соединений (Keep-Alive)
        self._client = httpx.AsyncClient(
            timeout=60.0,
            headers={"Authorization": f"Bearer {self.api_key}"}
        )

    async def run(self, chunks: List[Chunk]) -> List[Chunk]:
        """
        Вычисляет embeddings для списка чанков.
        """
        # Фильтруем чанки: если нет ни саммари, ни контента, эмбеддинг невозможен
        valid_chunks = [c for c in chunks if (c.summary or c.content or "").strip()]

        if not valid_chunks:
            log.warning("embed.skip", reason="No valid content in chunks")
            return chunks

        log.info("embed.start", total=len(chunks), valid=len(valid_chunks))

        # Разбиваем на батчи для эффективности API
        batch_size = 10
        for i in range(0, len(valid_chunks), batch_size):
            batch = valid_chunks[i:i + batch_size]
            try:
                await self._embed_batch(batch)
            except Exception as e:
                log.error("embed.batch.failed", batch_start=i, error=str(e), exc_info=True)
                # Мы не бросаем исключение выше, чтобы остальные батчи могли обработаться
                continue

        log.info("embed.complete", chunks_count=len(chunks))
        return chunks

    async def _embed_batch(self, chunks: List[Chunk]) -> None:
        """
        Отправляет батч текстов в API и записывает результаты обратно в объекты Chunk.
        """
        # Подготовка текстов: приоритет у summary, т.к. он лучше отражает суть для поиска
        texts = []
        for c in chunks:
            # Обрезаем слишком длинные тексты, чтобы не превысить контекст модели
            text = (c.summary or c.content or "")[:1000].strip()
            # Если после обрезки стало пусто (маловероятно из-за фильтрации выше),
            # добавляем заглушку, чтобы не упал весь батч
            texts.append(text if text else "empty")

        # Отправка запроса
        response = await self._client.post(
            f"{self.embed_url}/embeddings",
            json={
                "model": "embed-model",
                "input": texts,
            }
        )
        response.raise_for_status()
        result = response.json()

        embeddings_data = result.get("data", [])

        if len(embeddings_data) != len(chunks):
            raise ValueError(f"API returned {len(embeddings_data)} embeddings, but we sent {len(chunks)} texts")

        # Записываем эмбеддинги в объекты
        for i, chunk in enumerate(chunks):
            # В зависимости от API, структура может быть: data[i]['embedding'] или просто список
            emb_item = embeddings_data[i]
            if isinstance(emb_item, dict) and "embedding" in emb_item:
                chunk.embedding = emb_item["embedding"]
            elif isinstance(emb_item, list):
                chunk.embedding = emb_item
            else:
                log.error("embed.format_error", chunk_id=chunk.id, data=str(emb_item)[:100])
                continue

    async def close(self) -> None:
        """Закрывает HTTP клиент"""
        await self._client.aclose()
