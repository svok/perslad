"""
Indexing stage - persists nodes to vector store.

Uses vector_store.async_add() with batching. No dual-write to chunks table.
"""

from typing import Any

from llama_index.core.embeddings import BaseEmbedding

from ingestor.pipeline.base.processor_stage import ProcessorStage


class IndexingStage(ProcessorStage):
    """
    Persists TextNode objects to vector store.
    
    Handles batching and error reporting.
    """
    
    def __init__(self, vector_store: Any, embed_model: BaseEmbedding, batch_size: int = 100, max_workers: int = 2):
        super().__init__("indexing", max_workers)
        self.vector_store = vector_store
        self.embed_model = embed_model
        self.batch_size = batch_size
    
    async def process(self, context):
        """Process file context and index nodes."""
        if not context.nodes:
            self.log.debug("indexing.no_nodes", file_path=context.file_path)
            return context
        
        nodes = context.nodes
        total = len(nodes)
        self.log.info("indexing.start", file_path=context.file_path, nodes_count=total)
        
        # Generate embeddings for nodes that don't have them
        nodes_without_emb = [n for n in nodes if not n.embedding]
        if nodes_without_emb:
            self.log.info("indexing.generating_embeddings", count=len(nodes_without_emb))
            try:
                # Generate embeddings one by one
                for node in nodes_without_emb:
                    emb = await self.embed_model.aget_text_embedding(node.text)
                    node.embedding = emb
                self.log.info("indexing.embeddings_generated", count=len(nodes_without_emb))
            except Exception as e:
                self.log.error("indexing.embedding_failed", error=str(e), exc_info=True)
                context.has_errors = True
                context.errors.append(f"embedding generation failed: {str(e)}")
                return context  # Cannot index without embeddings
        
         # Process in batches
        for i in range(0, total, self.batch_size):
            batch = nodes[i:i + self.batch_size]
            try:
                # Add nodes to vector store
                node_ids = await self.vector_store.async_add(batch)
                self.log.debug("indexing.batch.success", batch_start=i, batch_size=len(batch), node_ids_count=len(node_ids))
            except Exception as e:
                self.log.error("indexing.batch.failed", batch_start=i, batch_size=len(batch), error=str(e), exc_info=True)
                context.has_errors = True
                context.errors.append(f"indexing failed at batch {i}: {str(e)}")
                # Continue with next batch (best-effort)
        
        self.log.info("indexing.complete", file_path=context.file_path, total_nodes=total)
        return context
