"""
Embedding model adapter.

Manages communication with the embedding model service.
"""

from typing import List, Type

import httpx
from infra.exceptions import (
    AuthorizationError,
    InfraConnectionError,
    FatalValidationError,
    ServiceUnavailableError,
    ValidationError,
)

from infra.logger import get_logger

__all__ = ["EmbeddingModel"]

log = get_logger("ingestor.embedding_model")


class EmbeddingModel:
    """
    Manages communication with the embedding model service.
    """

    def __init__(self, embed_url: str, api_key: str) -> None:
        self.embed_url = embed_url
        self.api_key = api_key

    @staticmethod
    def _parse_embedding_response(result: dict, context: str) -> dict:
        """Parse and validate embedding response (DRY)."""
        embeddings = result.get("data", [])
        if not embeddings:
            raise FatalValidationError(f"{context}: no embeddings in response")
        
        embedding_obj = embeddings[0]
        if "embedding" not in embedding_obj:
            raise FatalValidationError(f"{context}: missing 'embedding' key")
        
        vector = embedding_obj["embedding"]
        if not isinstance(vector, list) or len(vector) == 0:
            raise FatalValidationError(f"{context}: invalid embedding format")
        
        return embedding_obj

    @staticmethod
    def _map_httpx_error_to_exception(exc: httpx.HTTPError, context: str) -> InfraConnectionError | FatalValidationError:
        """Map httpx errors to exceptions."""
        if isinstance(exc, httpx.ConnectError):
            raise InfraConnectionError(f"{context}: connection failed") from exc
        if isinstance(exc, (httpx.ReadTimeout, httpx.ConnectTimeout)):
            raise InfraConnectionError(f"{context}: timeout") from exc
        if isinstance(exc, httpx.NetworkError):
            raise InfraConnectionError(f"{context}: network error") from exc
        if isinstance(exc, httpx.RemoteProtocolError):
            raise FatalValidationError(f"{context}: remote protocol error") from exc
        if isinstance(exc, httpx.LocalProtocolError):
            raise FatalValidationError(f"{context}: local protocol error") from exc
        raise FatalValidationError(f"{context}: {exc}")

    @staticmethod
    def _map_httpx_status_to_exception(status: int, context: str, cause: BaseException = None) -> Type[BaseException]:
        """Map HTTP status codes to exceptions with template."""
        status_map = {
            401: (AuthorizationError, "authentication"),
            403: (AuthorizationError, "authentication"),
            400: (ValidationError, "bad request"),
            404: (FatalValidationError, "not found"),
            405: (FatalValidationError, "method not allowed"),
            429: (ServiceUnavailableError, "rate limit exceeded"),
            500: (ServiceUnavailableError, "service unavailable"),
            502: (ServiceUnavailableError, "bad gateway"),
            503: (ServiceUnavailableError, "service unavailable"),
            504: (ServiceUnavailableError, "gateway timeout"),
        }
        
        exc_type, prefix = status_map.get(status, (FatalValidationError, "failed"))
        raise exc_type(f"{context}: {prefix} failed: {status}") from cause

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
                
                # Validate and parse response
                embedding_obj = self._parse_embedding_response(result, "Embedding model")
                embedding_vector = embedding_obj["embedding"]
                
                dimension = len(embedding_vector)
                log.info("embedding_model.get_dimension.success", dimension=dimension)
                return dimension

        except httpx.HTTPError as e:
            log.error("embedding_model.get_dimension.http_error", error=str(e))
            self._map_httpx_error_to_exception(e, "Embedding model")
            return -1  # Type safety, unreachable

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
                
                # Validate response structure
                embedding_obj = self._parse_embedding_response(result, "Embedding model")
                embedding = embedding_obj["embedding"]
                
                log.debug("embedding_model.embed.batch_complete", count=len(embedding))
                return embedding

        except httpx.HTTPError as e:
            log.error("embedding_model.embed.http_error", error=str(e))
            self._map_httpx_error_to_exception(e, "Embedding model")
            return []  # Type safety, unreachable

        except Exception as e:
            log.error("embedding_model.embed.error", error=str(e))
            raise FatalValidationError(f"Failed to generate embeddings: {str(e)}") from e
