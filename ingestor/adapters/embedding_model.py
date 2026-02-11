"""
Embedding model adapter.

Manages communication with the embedding model service.
"""

from typing import List

import httpx
from infra.exceptions import (
    FatalValidationError,
)
from infra.logger import get_logger
from infra.httpx_handler import map_httpx_error_to_exception
from ingestor.core.models.chunk import Chunk

log = get_logger("ingestor.embedding_model")


class EmbeddingModel:
    """
    Manages communication with the embedding model service.
    """

    def __init__(self, embed_url: str, api_key: str) -> None:
        self.embed_url = embed_url.rstrip("/")
        self.api_key = api_key

    @staticmethod
    def _parse_embedding_response(result: dict) -> dict:
        """Parse and validate embedding response (DRY)."""
        embeddings = result.get("data", [])
        if not embeddings:
            raise FatalValidationError("No embeddings in response")
        
        embedding_obj = embeddings[0]
        if "embedding" not in embedding_obj:
            raise FatalValidationError("Missing embedding key")
        
        vector = embedding_obj["embedding"]
        if not isinstance(vector, list) or len(vector) == 0:
            raise FatalValidationError("Invalid embedding format")
        
        return embedding_obj

    async def get_embedding_dimension(self) -> int:
        """
        Get the dimension of embeddings produced by the model.
        """
        try:
            log.info("embedding_model.get_dimension.request_start")
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.embed_url}/embeddings",
                    json={
                        "model": "embed-model",
                        "input": ["test"]
                    },
                    headers={"Authorization": f"Bearer {self.api_key}"}
                )
                response.raise_for_status()
                
                result = response.json()
                
                embedding_obj = self._parse_embedding_response(result)
                embedding_vector = embedding_obj["embedding"]
                
                dimension = len(embedding_vector)
                log.info("embedding_model.get_dimension.success", dimension=dimension)
                return dimension

        except httpx.HTTPError as e:
            log.error("embedding_model.get_dimension.http_error", error=str(e))
            raise map_httpx_error_to_exception(e, "Embedding model")

        except Exception as e:
            log.error("embedding_model.get_dimension.error", error=str(e))
            raise FatalValidationError(f"Failed to get embedding dimension: {str(e)}") from e

    async def get_embedding(self, text: str) -> List[float]:
        """
        Get embedding for a single text.
        """
        if not text or not text.strip():
             raise FatalValidationError("Empty text for embedding")

        # Truncate to avoid context limit errors (safe limit)
        MAX_CHARS = 8000
        if len(text) > MAX_CHARS:
            log.warning("embedding_model.truncate", original_len=len(text), new_len=MAX_CHARS)
            text = text[:MAX_CHARS]

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.embed_url}/embeddings",
                    json={
                        "model": "embed-model",
                        "input": [text]
                    },
                    headers={"Authorization": f"Bearer {self.api_key}"}
                )
                response.raise_for_status()
                result = response.json()
                return self._parse_embedding_response(result)["embedding"]
                
        except httpx.HTTPError as e:
            log.error("embedding_model.get_embedding.http_error", error=str(e), url=str(e.request.url) if e.request else None)
            raise map_httpx_error_to_exception(e, "Embedding model")
        except Exception as e:
            log.error("embedding_model.get_embedding.error", error=str(e))
            raise

    async def embed_text(self, texts: List[str]) -> List[float]:
        """
        Legacy method. Returns single vector of first text.
        """
        # Re-implement using get_embedding for first item
        if not texts:
            raise ValueError("Empty input")
        return await self.get_embedding(texts[0])

    async def run(self, chunks: List[Chunk]) -> List[Chunk]:
        """
        Compute embeddings for a list of chunks.
        Compatible with EmbedStage interface.
        """
        # Filter chunks with valid content
        valid_chunks = [c for c in chunks if (c.summary or c.content or "").strip()]
        
        if not valid_chunks:
            log.warning("embed.skip", reason="No valid content in chunks")
            return chunks
        
        log.info("embed.start", total=len(chunks), valid=len(valid_chunks))
        
        # Process in batches of 10 for efficiency
        batch_size = 10
        for i in range(0, len(valid_chunks), batch_size):
            batch = valid_chunks[i:i + batch_size]
            try:
                # Prepare texts for the batch
                texts = []
                for c in batch:
                    text = (c.summary or c.content or "")[:1000].strip()
                    texts.append(text if text else "empty")
                
                # Get embeddings for the entire batch at once
                batch_embeddings = await self.get_embeddings(texts)
                
                # Assign embeddings to chunks
                for j, chunk in enumerate(batch):
                    chunk.embedding = batch_embeddings[j]
                    
            except Exception as e:
                log.error(f"embed.batch.failed", batch_start=i, error=str(e), exc_info=True)
                continue
        
        log.info("embed.complete", chunks_count=len(chunks))
        return chunks

    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Get embeddings for multiple texts in a single request.
        """
        if not texts:
            raise ValueError("Empty input list")
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.embed_url}/embeddings",
                    json={
                        "model": "embed-model",
                        "input": texts
                    },
                    headers={"Authorization": f"Bearer {self.api_key}"}
                )
                response.raise_for_status()
                result = response.json()
                
                # Parse embeddings from response
                embeddings_data = result.get("data", [])
                if len(embeddings_data) != len(texts):
                    raise ValueError(f"API returned {len(embeddings_data)} embeddings, but we sent {len(texts)} texts")
                
                embeddings = []
                for emb_item in embeddings_data:
                    if isinstance(emb_item, dict) and "embedding" in emb_item:
                        embeddings.append(emb_item["embedding"])
                    elif isinstance(emb_item, list):
                        embeddings.append(emb_item)
                    else:
                        raise ValueError(f"Invalid embedding format: {emb_item}")
                
                return embeddings
                
        except httpx.HTTPError as e:
            log.error("embedding_model.get_embeddings.http_error", error=str(e))
            raise map_httpx_error_to_exception(e, "Embedding model")
