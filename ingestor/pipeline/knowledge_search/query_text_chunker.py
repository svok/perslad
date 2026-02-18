"""
Query Text Chunker - Specialized for chunking search queries.

Provides specialized logic for chunking user queries for knowledge search,
including sentence-based splitting and metadata handling.
"""

from typing import List, Dict, Any

from ingestor.pipeline.utils.text_splitter_helper import TextSplitterHelper


class QueryTextChunker:
    """
    Specialized chunker for search queries.
    
    Uses sentence-based splitting for better semantic coverage
    while respecting character limits for embedding models.
    """

    def __init__(
        self,
        text_splitter_helper: TextSplitterHelper,
        chunk_size: int = 2000
    ):
        """
        Initialize query chunker.
        
        Args:
            text_splitter_helper: Shared text splitter helper instance
            chunk_size: Maximum characters per chunk (for embeddings)
        """
        self.helper = text_splitter_helper
        self.chunk_size = chunk_size

    async def chunk(
        self,
        query: str,
        metadata: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Split a query into chunks optimized for embedding search.
        
        Args:
            query: User query text
            metadata: Additional metadata for each chunk
        
        Returns:
            List of query chunk dicts with content, metadata, and chunk_type
        """
        if not query or not query.strip():
            return []

        chunks, error = self.helper.split_query_by_sentences(
            query,
            max_chars=self.chunk_size
        )

        if error:
            return [{"content": query, "metadata": metadata or {}, "chunk_type": "query"}]

        if not chunks:
            chunks = [query]

        return [
            {
                "content": chunk,
                "metadata": metadata or {},
                "chunk_type": "query",
            }
            for chunk in chunks
        ]

    async def chunk_with_splitters(
        self,
        query: str,
        metadata: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Split query using LlamaIndex splitters (alternative approach).
        
        Useful if you want semantic splitting instead of sentence splitting.
        
        Args:
            query: User query text
            metadata: Additional metadata for each chunk
        
        Returns:
            List of query chunk dicts
        """
        if not query or not query.strip():
            return []

        splitter = self.helper.create_splitter(".txt")[1]

        chunks, error = await self.helper.chunk_text(
            text=query,
            splitter=splitter,
            chunk_type="query",
            metadata=metadata,
        )

        if error:
            return [{"content": query, "metadata": metadata or {}, "chunk_type": "query"}]

        return chunks
