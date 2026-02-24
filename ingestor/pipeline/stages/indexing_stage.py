"""
Indexing stage - persists nodes to vector store.

Replaces PersistChunksStage. Uses vector_store.async_add() with batching.
"""

from typing import Any

from llama_index.core.embeddings import BaseEmbedding

from ingestor.pipeline.base.processor_stage import ProcessorStage


class IndexingStage(ProcessorStage):
    """
    Persists TextNode objects to vector store.
    
    Handles batching and error reporting.
    """
    
    def __init__(self, vector_store: Any, embed_model: BaseEmbedding, storage: Any, batch_size: int = 100, max_workers: int = 2):
        super().__init__("indexing", max_workers)
        self.vector_store = vector_store
        self.embed_model = embed_model
        self.storage = storage
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
                
                # Also save to storage (dual-write) for get_chunks_by_file compatibility
                if self.storage is not None:
                    from ingestor.core.models.chunk import Chunk
                    chunks_to_save = []
                    for idx, node in enumerate(batch):
                        chunk_id = node_ids[idx] if idx < len(node_ids) else getattr(node, 'node_id', None)
                        chunk = Chunk(
                            id=chunk_id or f"tmp_{hash(node.text)}",
                            file_path=node.metadata.get("file_path", ""),
                            content=node.text,
                            start_line=node.metadata.get("start_line", 0),
                            end_line=node.metadata.get("end_line", 0),
                            chunk_type=node.metadata.get("chunk_type", ""),
                            summary=node.metadata.get("summary"),
                            purpose=node.metadata.get("purpose"),
                            embedding=node.embedding,
                            metadata=node.metadata,
                        )
                        chunks_to_save.append(chunk)
                    try:
                        await self.storage.save_chunks(chunks_to_save)
                        self.log.debug("indexing.storage.save.success", batch_start=i, chunks_count=len(chunks_to_save))
                    except Exception as e:
                        self.log.error("indexing.storage.save.failed", batch_start=i, error=str(e), exc_info=True)
                        # Non-critical - continue
            except Exception as e:
                self.log.error("indexing.batch.failed", batch_start=i, batch_size=len(batch), error=str(e), exc_info=True)
                context.has_errors = True
                context.errors.append(f"indexing failed at batch {i}: {str(e)}")
                # Continue with next batch (best-effort)
        
        self.log.info("indexing.complete", file_path=context.file_path, total_nodes=total)
        return context
