"""
Adapter for EmbeddingModel to be used with llama_index as BaseEmbedding.

This wrapper allows EmbeddingModel to be passed where llama_index expects
BaseEmbedding interface.
"""

from typing import List, Optional, Any

from llama_index.core.embeddings import BaseEmbedding
from infra.logger import get_logger

from ingestor.adapters.embedding_model import EmbeddingModel

log = get_logger("ingestor.embedding_adapter")


class EmbeddingModelAdapter(BaseEmbedding):
    """
    Adapter that makes EmbeddingModel compatible with llama_index's BaseEmbedding interface.
    """
    
    def __init__(self, embed_model: EmbeddingModel, **kwargs):
        """
        Initialize adapter.
        
        Args:
            embed_model: EmbeddingModel instance
        """
        super().__init__(**kwargs)
        self._embed_model = embed_model
    
    # Async methods
    
    async def aget_text_embedding(self, text: str) -> List[float]:
        """
        Get embedding for a single text.
        
        Args:
            text: Text to embed
            
        Returns:
            List of floats representing the embedding vector
        """
        return await self._embed_model.get_embedding(text)
    
    async def aget_query_embedding(self, query: str) -> List[float]:
        """
        Get embedding for a query string.
        
        Args:
            query: Query text to embed
            
        Returns:
            List of floats representing the embedding vector
        """
        return await self._embed_model.get_embedding(query)
    
    async def aget_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Get embeddings for multiple texts.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        return await self._embed_model.get_embeddings(texts)
    
    async def get_embedding_dimension(self) -> int:
        """
        Get the dimension of embeddings produced by this model.
        
        Returns:
            Embedding dimension (size of output vectors)
        """
        return await self._embed_model.get_embedding_dimension()
    
    # Synchronous methods - not supported, raise if called
    
    def get_text_embedding(self, text: str) -> List[float]:
        raise NotImplementedError(
            "EmbeddingModelAdapter is async-only. Use aget_text_embedding() instead."
        )
    
    def get_query_embedding(self, query: str) -> List[float]:
        raise NotImplementedError(
            "EmbeddingModelAdapter is async-only. Use aget_query_embedding() instead."
        )
    
    def get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        raise NotImplementedError(
            "EmbeddingModelAdapter is async-only. Use aget_text_embeddings() instead."
        )
    
    # Note: BaseEmbedding also requires _aget_text_embedding, _get_text_embedding, etc.
    # Those are internal methods used by BaseEmbedding's default implementations.
    # We can provide them as aliases to our async methods to satisfy ABC.
    
    async def _aget_text_embedding(self, text: str) -> List[float]:
        return await self.aget_text_embedding(text)
    
    async def _aget_query_embedding(self, query: str) -> List[float]:
        return await self.aget_query_embedding(query)
    
    def _get_text_embedding(self, text: str) -> List[float]:
        raise NotImplementedError("Async-only adapter")
    
    def _get_query_embedding(self, query: str) -> List[float]:
        raise NotImplementedError("Async-only adapter")
