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
