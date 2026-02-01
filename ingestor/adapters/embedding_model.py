"""
Embedding model adapter.

Manages communication with the embedding model service.
"""

from typing import List

import httpx
from infra.exceptions import (
    FatalValidationError,
    ServiceUnavailableError,
)

from infra.logger import get_logger

log = get_logger("ingestor.embedding_model")


class EmbeddingModel:
    """
    Manages communication with the embedding model service.
    """

    def __init__(self, embed_url: str, api_key: str) -> None:
        self.embed_url = embed_url
        self.api_key = api_key

    async def get_embedding_dimension(self) -> int:
        """
        Get the dimension of embeddings produced by the model.
        
        Makes a minimal request to the model to determine the dimension.
        
        Returns:
            int: Dimension of the embedding vectors
            
        Raises:
            RuntimeError: If the model returns invalid data or connection fails
        """
        try:
            log.info("embedding_model.get_dimension.request_start")
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.embed_url}/embeddings",
                    json={
                        "model": "embed-model",
                        "input": ["test"]  # Minimal input to get dimension info
                    },
                    headers={"Authorization": f"Bearer {self.api_key}"}
                )
                response.raise_for_status()
                
                result = response.json()
                
                # Validate response structure
                embeddings = result.get("data", [])
                if not embeddings or len(embeddings) == 0:
                    raise RuntimeError(
                        f"Embedding model returned no data. Response: {result}"
                    )
                
                embedding_obj = embeddings[0]
                if "embedding" not in embedding_obj:
                    raise RuntimeError(
                        f"Embedding model response missing 'embedding' key. Response: {embedding_obj}"
                    )
                
                embedding_vector = embedding_obj["embedding"]
                if not isinstance(embedding_vector, list) or len(embedding_vector) == 0:
                    raise RuntimeError(
                        f"Invalid embedding format from model. Expected list with at least one element, got {type(embedding_vector)}"
                    )
                
                dimension = len(embedding_vector)
                log.info("embedding_model.get_dimension.success", dimension=dimension)
                return dimension

        except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout) as e:
            log.error("embedding_model.get_dimension.connection_error", error=str(e))
            raise ConnectionError(f"Failed to connect to embedding model: {str(e)}") from e
        except httpx.HTTPStatusError as e:
            log.error("embedding_model.get_dimension.http_error", error=str(e))
            if e.response.status_code >= 500:
                raise ServiceUnavailableError(f"Embedding model service unavailable: {e.response.status_code}") from e
            raise FatalValidationError(f"Embedding model failed: {e.response.status_code}") from e
        except httpx.HTTPError as e:
            log.error("embedding_model.get_dimension.http_error", error=str(e))
            raise ConnectionError(f"Failed to connect to embedding model: {str(e)}") from e
        except Exception as e:
            log.error("embedding_model.get_dimension.error", error=str(e))
            raise FatalValidationError(f"Failed to get embedding dimension: {str(e)}") from e

    async def embed_text(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            List of embedding vectors (lists of floats)
            
        Raises:
            RuntimeError: If the model returns invalid data or connection fails
        """
        try:
            log.debug("embedding_model.embed.batch_start", count=len(texts))
            
            async with httpx.AsyncClient(timeout=60.0) as client:
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
                
                embeddings = result.get("data", [])
                if len(embeddings) != len(texts):
                    raise RuntimeError(
                        f"Embedding count mismatch: requested {len(texts)}, got {len(embeddings)}"
                    )
                
                log.debug("embedding_model.embed.batch_complete", count=len(embeddings))
                return embeddings

        except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout) as e:
            log.error("embedding_model.embed.connection_error", error=str(e))
            raise ConnectionError(f"Failed to connect to embedding model: {str(e)}") from e
        except httpx.HTTPStatusError as e:
            log.error("embedding_model.embed.http_error", error=str(e))
            if e.response.status_code >= 500:
                raise ServiceUnavailableError(f"Embedding model service unavailable: {e.response.status_code}") from e
            raise FatalValidationError(f"Embedding model failed: {e.response.status_code}") from e
        except httpx.HTTPError as e:
            log.error("embedding_model.embed.http_error", error=str(e))
            raise ConnectionError(f"Failed to connect to embedding model: {str(e)}") from e
        except Exception as e:
            log.error("embedding_model.embed.error", error=str(e))
            raise FatalValidationError(f"Failed to generate embeddings: {str(e)}") from e
