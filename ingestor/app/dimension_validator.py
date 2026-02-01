"""
Dimension Validator

Validates that embedding dimensions match between model and database.
"""

import asyncio
from typing import Any, Callable, Awaitable

from ingestor.app.config import runtime
from ingestor.adapters.embedding_model import EmbeddingModel
from ingestor.app.llm_lock import LLMLockManager
from infra.exceptions import FatalValidationError, InfraConnectionError
from infra.logger import get_logger
from infra.reconnect import retry_forever

log = get_logger("ingestor.dimension_validator")


class FatalValidationError(RuntimeError):
    """Fatal validation error that prevents application from starting."""
    pass


class DimensionValidator:
    """
    Validates that embedding dimensions match between model and database.
    """
    
    def __init__(self, embed_model: EmbeddingModel, storage: Any, lock_manager: LLMLockManager) -> None:
        """
        Initialize dimension validator.
        
        Args:
            embed_model: EmbeddingModel instance for querying dimension
            storage: Storage instance (for database access)
            lock_manager: LLM lock manager for waiting
        """
        self.embed_model = embed_model
        self.storage = storage
        self.lock_manager = lock_manager
    
    async def _connect_once(self) -> None:
        """Пробует установить соединение и проверить размерность."""
        try:
            log.info("dimension_validator.connect.attempt")

            # Ждём, пока LLM не разблокирован
            await self.lock_manager.wait_unlocked()

            # Get dimension from embedding model
            model_dim = await self.embed_model.get_embedding_dimension()
            log.info("dimension_validator.model_dimension", dimension=model_dim)

            # Get dimension from database schema
            if not hasattr(self.storage, 'get_embedding_dimension'):
                raise RuntimeError("Storage does not have get_embedding_dimension method")

            db_dim = await self.storage.get_embedding_dimension()
            log.info("dimension_validator.db_dimension", dimension=db_dim)

            # Compare and fail if mismatch
            if model_dim != db_dim:
                raise FatalValidationError(
                    f"Embedding dimension mismatch: model produces vectors of size {model_dim}, "
                    f"but database column expects {db_dim}. This will cause data loss or errors. "
                    "Please ensure your embedding model and database schema are configured correctly."
                )

            log.info("dimension_validator.validated", model_dim=model_dim, db_dim=db_dim)
        except Exception as e:
            log.warning("dimension_validator.connect.failed", error=str(e))
            raise e
    
    async def validate_dimensions(self) -> None:
        """
        Validates that embedding dimensions match between model and database.
        
        At startup, makes a request to the embedding model and queries the database
        to get their dimensions. If they don't match, raises FatalValidationError.
        Uses retry_forever to ensure connectivity.
        """
        await retry_forever(
            self._connect_once,
            retryable_exceptions=[InfraConnectionError],
        )
