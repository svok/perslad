"""
Ingestor Main Entry Point

Запускает:
1. HTTP API (для knowledge search)
2. Indexer Pipeline (scanner + parse + enrich + indexing)
"""

import asyncio
import signal
from pathlib import Path

import uvicorn
from dotenv import load_dotenv

from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.vector_stores.postgres import PGVectorStore
from llama_index.core.vector_stores.simple import SimpleVectorStore

from ingestor.config import emb_config, llm_config, runtime_config, storage_config
from ingestor.pipeline.models.pipeline_context import PipelineContext
from ingestor.pipeline.utils.text_splitter_helper import TextSplitterHelper
from ingestor.services.indexer import IndexerOrchestrator
from ingestor.adapters import get_storage
from ingestor.api.server import IngestorAPI
from ingestor.services.validator import DimensionValidator
from ingestor.services.knowledge import KnowledgePort
from ingestor.services.lock import LLMLockManager
from infra.logger import setup_logging, get_logger

_shutdown = asyncio.Event()


def _install_signal_handlers(log):
    """Устанавливает обработчики сигналов."""

    def _handler(signame: str):
        log.info("ingestor.shutdown.signal", signal=signame)
        _shutdown.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _handler, sig.name)


async def run_api_server(api: IngestorAPI, port: int):
    """Запускает HTTP API сервер."""
    config = uvicorn.Config(
        api.app,
        host="0.0.0.0",
        port=port,
        log_level="info",
    )
    server = uvicorn.Server(config)
    await server.serve()


async def main() -> None:
    env = runtime_config.ENV
    workspace = runtime_config.WORKSPACE_PATH
    api_port = runtime_config.INGESTOR_PORT
    log_level = runtime_config.LOG_LEVEL

    setup_logging(log_level=log_level)
    log = get_logger("ingestor")

    log.info(
        "ingestor.boot",
        env=env,
        workspace=workspace,
        port=api_port,
        storage_type=storage_config.STORAGE_TYPE,
    )

    # === Storage ===
    storage = get_storage()
    await storage.initialize()
    log.info("ingestor.storage.initialized")

    # === Lock Manager ===
    lock_manager = LLMLockManager()

    # === Vector Store ===
    if hasattr(storage, '_vector_store') and storage._vector_store is not None:
        vector_store = storage._vector_store
        log.info("ingestor.vector_store.reused_from_storage")
    else:
        if storage_config.STORAGE_TYPE == "postgres":
            conn_str = f"postgresql://{storage_config.POSTGRES_USER}:{storage_config.POSTGRES_PASSWORD}@{storage_config.POSTGRES_HOST}:{storage_config.POSTGRES_PORT}/{storage_config.POSTGRES_DB}"
            vector_store = PGVectorStore(
                connection_string=conn_str,
                table_name=storage_config.VECTOR_STORE_TABLE_NAME,
                embed_dim=storage_config.PGVECTOR_DIMENSIONS,
            )
        elif storage_config.STORAGE_TYPE == "memory":
            vector_store = SimpleVectorStore()
        else:
            raise ValueError(f"Unknown storage type: {storage_config.STORAGE_TYPE}")
        log.info("ingestor.vector_store.created_separately")

    # === Embedding Model ===
    # Subclass OpenAIEmbedding to add get_embedding_dimension() method
    class OpenAIEmbeddingWithDimension(OpenAIEmbedding):
        def __init__(self, *args, dim: int = 768, **kwargs):
            super().__init__(*args, **kwargs)
            self._custom_dim = dim
        
        async def get_embedding_dimension(self) -> int:
            return self._custom_dim
    
    embed_model = OpenAIEmbeddingWithDimension(
        api_base=emb_config.EMB_URL,
        api_key=emb_config.EMB_API_KEY,
        model_name=emb_config.EMB_SERVED_MODEL_NAME,
        timeout=30.0,
        dim=storage_config.PGVECTOR_DIMENSIONS,
    )

    # === Validate dimensions (must match exactly) ===
    log.info("dimension_validator.validation.started")
    dimension_validator = DimensionValidator(
        embed_model=embed_model, storage=storage, lock_manager=lock_manager
    )
    try:
        await dimension_validator.validate_dimensions()
        log.info("dimension_validator.validation.complete")
    except Exception as e:
        log.error("dimension_validator.validation.failed", error=str(e))
        raise  # Exit immediately - dimension mismatch is fatal

    # === Knowledge Index ===
    from ingestor.search.knowledge_index import KnowledgeIndex
    knowledge_index = KnowledgeIndex(vector_store, embed_model)
    log.info("knowledge_index.created")

    # === Pipeline Context ===
    pipeline_context = PipelineContext(
        workspace_path=Path(workspace),
        storage=storage,
        llm=None,  # LLM not used (enrich disabled)
        lock_manager=lock_manager,
        embed_model=embed_model,
        vector_store=vector_store,
        text_splitter_helper=TextSplitterHelper(),
        config={},
    )
    
    # === Knowledge Port ===
    knowledge_port = KnowledgePort(pipeline_context, knowledge_index=knowledge_index)
    log.info("knowledge_port.ready")
    
    # === Indexer Orchestrator ===
    indexer = IndexerOrchestrator(pipeline_context)
    
    # === HTTP API ===
    api = IngestorAPI(
        lock_manager=lock_manager,
        storage=storage,
        knowledge_port=knowledge_port,
        embedding_model=embed_model,
    )

    # === Background Tasks ===
    api_task = asyncio.create_task(run_api_server(api, api_port))
    log.info("ingestor.api.started", port=api_port)

    # Wait for API server
    try:
        await api_task
    except asyncio.CancelledError:
        pass
    finally:
        # Shutdown
        log.info("ingestor.shutdown.start")
        await indexer.stop()
        api_task.cancel()
        try:
            await api_task
        except asyncio.CancelledError:
            pass
        if hasattr(embed_model, 'close') and callable(getattr(embed_model, 'close')):
            try:
                await embed_model.close()
            except Exception:
                pass
        await storage.close()
        log.info("ingestor.shutdown.complete")


if __name__ == "__main__":
    asyncio.run(main())
