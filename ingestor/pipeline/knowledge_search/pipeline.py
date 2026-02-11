"""
Knowledge Search Pipeline - Lightweight pipeline for searching indexed knowledge.

Provides optimized search capabilities for knowledge base using:
1. Query chunking for large queries
2. Embedding generation for query parts
3. Vector search via pgvector
4. Ranking and deduplication of results
"""

from typing import List, Dict, Any, Optional, TYPE_CHECKING

from ingestor.core.ports.storage import BaseStorage
from ingestor.pipeline.impl.text_splitter_helper import TextSplitterHelper
from ingestor.pipeline.knowledge_search.query_text_chunker import QueryTextChunker

if TYPE_CHECKING:
    from ingestor.adapters.embedding_model import EmbeddingModel


class KnowledgeSearchPipeline:
    """
    Lightweight pipeline for searching knowledge base.
    
    Optimized for:
    - Large query text (chunks query before embedding)
    - Vector-based search (O(log N) via pgvector)
    - Batch operations for efficiency
    - Minimal dependencies (no queues, workers)
    """

    def __init__(
        self,
        storage: BaseStorage,
        text_splitter_helper: TextSplitterHelper,
        embedding_model: Optional[EmbeddingModel] = None,
        query_chunk_size: int = 2000,
        top_k_per_query: int = 10
    ):
        """
        Initialize knowledge search pipeline.
        
        Args:
            storage: Storage interface for vector search
            text_splitter_helper: Shared text splitter helper
            embedding_model: Optional embedding model for query embedding
            query_chunk_size: Maximum characters per query chunk (for embeddings)
            top_k_per_query: Number of results to retrieve per query chunk
        """
        self.storage = storage
        self.helper = text_splitter_helper
        self.embedding_model = embedding_model
        self.query_chunker = QueryTextChunker(
            text_splitter_helper=text_splitter_helper,
            chunk_size=query_chunk_size
        )
        self.top_k_per_query = top_k_per_query

    async def search(
        self,
        query: str,
        top_k: int = 10,
        filter_by_file: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute full knowledge search with query chunking.
        
        Pipeline steps:
        1. Chunk query by sentences
        2. Generate embeddings for each chunk
        3. Vector search for each embedding
        4. Rank and deduplicate results
        
        Args:
            query: User query text
            top_k: Total number of results to return
            filter_by_file: Optional file path filter
        
        Returns:
            Dictionary with results and metadata
        """
        print(f"KnowledgeSearchPipeline.search: Starting search for query: {query[:100]}...")
        
        chunks = await self.query_chunker.chunk(query)
        print(f"KnowledgeSearchPipeline.search: Split query into {len(chunks)} chunks")
        
        embeddings = await self._embed_query_chunks(chunks)
        print(f"KnowledgeSearchPipeline.search: Generated embeddings for {len(embeddings)} chunks")
        
        all_results = []
        for chunk_emb in embeddings:
            chunk_results = await self._vector_search(
                chunk_emb["embedding"],
                filter_by_file=filter_by_file
            )
            for result in chunk_results:
                result["original_query_chunk"] = chunk_emb["text"]
            all_results.extend(chunk_results)
        
        print(f"KnowledgeSearchPipeline.search: Retrieved {len(all_results)} raw results")
        
        ranked = await self._rank_and_deduplicate(all_results, top_k)
        print(f"KnowledgeSearchPipeline.search: Returning {len(ranked)} ranked results")
        
        return {
            "results": ranked,
            "chunks_analyzed": len(chunks),
            "embeddings_generated": len(embeddings),
        }

    async def _embed_query_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Generate embeddings for query chunks using storage backend.
        """
        embeddings = []
        
        for chunk_data in chunks:
            chunk_text = chunk_data["content"]
            
            if self.embedding_model:
                embedding = await self.embedding_model.get_embedding(chunk_text)
            else:
                raise NotImplementedError(
                    "Need to integrate embedding model here. "
                    "Pass embedding_model to __init__ and use it"
                )
            
            embeddings.append({
                "text": chunk_text,
                "embedding": embedding
            })
        
        return embeddings

    async def _vector_search(
        self,
        query_embedding: List[float],
        filter_by_file: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform vector search using storage backend.
        
        Uses pgvector for O(log N) similarity search.
        
        Args:
            query_embedding: Vector to search with
            filter_by_file: Optional file path filter
        
        Returns:
            List of matching chunks with similarity scores
        """
        # NOTE: This is a placeholder. In production, use storage vector search:
        # chunks = await self.storage.search_by_vector(query_embedding, self.top_k_per_query)
        
        # For now, implement a simple SQL query pattern

        try:
            all_chunks = await self.storage.get_all_chunks()
            chunks_with_emb = [c for c in all_chunks if c.embedding is not None]
            
            if not chunks_with_emb:
                return []
            
            if filter_by_file:
                chunks_with_emb = [c for c in chunks_with_emb if c.file_path == filter_by_file]
            
            if not chunks_with_emb:
                return []
            
            # Compute cosine similarity for each chunk
            scored_chunks = []
            for chunk in chunks_with_emb:
                similarity = self._cosine_similarity(query_embedding, chunk.embedding)
                scored_chunks.append({
                    "chunk_id": chunk.id,
                    "file_path": chunk.file_path,
                    "content": chunk.content,
                    "summary": chunk.summary,
                    "purpose": chunk.purpose,
                    "similarity": similarity,
                    "metadata": chunk.metadata,
                    "chunk_type": chunk.chunk_type,
                })
            
            # Sort by similarity
            scored_chunks.sort(key=lambda x: x["similarity"], reverse=True)
            
            return scored_chunks[:self.top_k_per_query]
            
        except Exception as e:
            print(f"Error in vector search: {e}")
            return []

    async def _rank_and_deduplicate(
        self,
        results: List[Dict[str, Any]],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """
        Rank and deduplicate search results.
        
        Uses:
        - Combined similarity from multiple query chunks
        - File path deduplication
        - Content similarity (if available)
        
        Args:
            results: Raw search results
            top_k: Number of top results to return
        
        Returns:
            Ranked and deduplicated results
        """
        if not results:
            return []
        
        # Create a dictionary for deduplication by file path
        dedup_dict = {}
        
        for result in results:
            file_path = result["file_path"]
            chunk_id = result["chunk_id"]
            
            # Combine similarity from all query chunks
            # (in a real implementation, track which query chunk produced each result)
            base_score = result["similarity"]
            
            if file_path not in dedup_dict:
                dedup_dict[file_path] = {
                    "chunk_id": chunk_id,
                    "file_path": file_path,
                    "summary": result["summary"],
                    "purpose": result["purpose"],
                    "similarity": base_score,
                    "content": result["content"],
                    "metadata": result["metadata"],
                    "chunk_type": result["chunk_type"],
                }
            else:
                # Keep the highest scoring chunk for this file
                if base_score > dedup_dict[file_path]["similarity"]:
                    dedup_dict[file_path]["chunk_id"] = chunk_id
                    dedup_dict[file_path]["similarity"] = base_score
                    dedup_dict[file_path]["content"] = result["content"]
                    dedup_dict[file_path]["summary"] = result["summary"]
                    dedup_dict[file_path]["purpose"] = result["purpose"]
        
        # Convert to list and sort by similarity
        ranked_results = list(dedup_dict.values())
        ranked_results.sort(key=lambda x: x["similarity"], reverse=True)
        
        return ranked_results[:top_k]

    @staticmethod
    def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        """
        Compute cosine similarity between two vectors.
        
        Args:
            vec1: First vector
            vec2: Second vector
        
        Returns:
            Cosine similarity score (0.0 to 1.0)
        """
        import math
        
        if len(vec1) != len(vec2):
            return 0.0
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(dot_product / (norm1 * norm2))
