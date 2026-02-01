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
    Вычисляет embeddings для чанков с помощью локального embedding endpoint.
    """

    def __init__(self, embed_url: str, api_key: str) -> None:
        self.embed_url = embed_url
        self.api_key = api_key

    async def run(self, chunks: List[Chunk]) -> List[Chunk]:
        """
        Вычисляет embeddings для всех чанков.
        """
        log.info("embed.start", chunks_count=len(chunks))

        embedded = 0
        skipped = 0

        # Batch for efficiency
        batch_size = 10
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]

            try:
                await self._embed_batch(batch)
                embedded += len(batch)
            except Exception as e:
                log.error(
                    "embed.batch.failed",
                    batch_start=i,
                    batch_size=len(batch),
                    error=str(e),
                    exc_info=True,
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
        # Prepare texts
        texts = []
        for chunk in chunks:
            text = chunk.summary or chunk.content[:500]
            texts.append(text)

        # Call embedding endpoint
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.embed_url}/embeddings",
                json={
                    "model": "embed-model",
                    "input": texts,
                },
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            response.raise_for_status()
            result = response.json()
            
        # Debug info for troubleshooting
        log.debug("embed.batch.response", result=result)
        
        # Save embeddings
        embeddings = result.get("data", [])
        log.debug("embed.batch.embeddings_extracted", count=len(embeddings), chunks_count=len(chunks))
        
        if len(embeddings) != len(chunks):
            log.warning("embed.batch.mismatch", expected=len(chunks), got=len(embeddings))
            raise ValueError(f"Embedding count mismatch: expected {len(chunks)}, got {len(embeddings)}")
            
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            if "embedding" not in embedding:
                log.error("embed.batch.embedding_missing_key", chunk_id=chunk.id[:20], embedding=embedding)
                raise ValueError(f"Missing 'embedding' key in response for chunk {chunk.id}")
            chunk.embedding = embedding["embedding"]
            log.debug("embed.batch.chunk_embedding_set", chunk_id=chunk.id[:20], embedding_len=len(embedding["embedding"]))

        log.debug("embed.batch.complete", batch_size=len(chunks))
