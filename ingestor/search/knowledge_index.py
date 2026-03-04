"""
Knowledge Index using llama_index VectorStoreIndex.

Implements direct vector search without multi-stage pipelines.
"""

from typing import List, Dict, Optional, Any

from llama_index.core import VectorStoreIndex, StorageContext
from llama_index.core.retrievers import VectorIndexRetriever
from llama_index.core.vector_stores.types import MetadataFilter, MetadataFilters, FilterOperator
from llama_index.core.embeddings import BaseEmbedding
from llama_index.core.schema import TextNode

from infra.logger import get_logger

log = get_logger("ingestor.knowledge_index")


class KnowledgeIndex:
    """
    Provides knowledge search using vector similarity.
    
    Implements direct vector search without multi-stage pipelines.
    """
    
    def __init__(self, vector_store: Any, embed_model: BaseEmbedding):
        """
        Initialize knowledge index.
        
        Args:
            vector_store: Vector store for storage and retrieval
            embed_model: Embedding model for query embedding
        """
        self.vector_store = vector_store
        self.embed_model = embed_model
        
        # Create storage context
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        
        # Create index (empty initially, will be populated as nodes are added)
        self._index = VectorStoreIndex(
            nodes=[],
            storage_context=storage_context,
            embed_model=embed_model,
        )
    
    async def search(
        self, 
        query: str, 
        top_k: int = 10, 
        filter_by_file: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Search for relevant knowledge chunks.
        
        Args:
            query: Text query
            top_k: Maximum number of results
            filter_by_file: Optional file path to filter results
            
        Returns:
            Dictionary with results and metadata
        """
        log.info("knowledge_index.search", query=query[:100], top_k=top_k, filter_by_file=filter_by_file)
        
        try:
            # Create retriever
            retriever = VectorIndexRetriever(
                index=self._index,
                similarity_top_k=top_k * 2,  # Retrieve more for deduplication
            )
            
            # Apply filters if needed
            if filter_by_file:
                from llama_index.core.vector_stores import MetadataFilter, MetadataFilters
                metadata_filter = MetadataFilter(
                    key="file_path",
                    operator=FilterOperator.EQ,
                    value=filter_by_file,
                )
                filters = MetadataFilters(filters=[metadata_filter])
                retriever._filters = filters
            
            # Retrieve nodes
            nodes = await retriever.aretrieve(query)
            
            # Deduplicate by file (keep first occurrence per file)
            seen_files = set()
            results = []
            for node in nodes:
                file_path = node.metadata.get("file_path", "")
                if file_path and file_path not in seen_files:
                    seen_files.add(file_path)
                    results.append({
                        "file_path": file_path,
                        "content": node.text,
                        "score": getattr(node, 'score', None),
                        "metadata": node.metadata,
                        "start_line": node.metadata.get("start_line", 0),
                        "end_line": node.metadata.get("end_line", 0),
                    })
                    if len(results) >= top_k:
                        break
            
            log.info("knowledge_index.search.complete", results_count=len(results))
            return {"results": results, "total": len(results)}
            
        except Exception as e:
            log.error("knowledge_index.search.failed", error=str(e), exc_info=True)
            return {"results": [], "error": str(e), "total": 0}
