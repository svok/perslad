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
from llama_index.llms.openai import OpenAI
from llama_index.llms.openai_like import OpenAILike

from infra.logger import setup_logging, get_logger
from ingestor.adapters import get_storage
from ingestor.adapters.embedding_model import EmbeddingModel
from ingestor.adapters.llama_index_embedding_adapter import EmbeddingModelAdapter
from ingestor.api.server import IngestorAPI
from ingestor.config import runtime_config, storage_config
from ingestor.config.base import PipelineConfig
from ingestor.pipeline.models.pipeline_context import PipelineContext
from ingestor.pipeline.utils.text_splitter_helper import TextSplitterHelper
from ingestor.services.indexer import IndexerOrchestrator
from ingestor.services.knowledge import KnowledgePort
from ingestor.services.lock import LLMLockManager
from ingestor.services.validator import DimensionValidator

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

    # === Load central config ===
    config = PipelineConfig.from_env()
    log.info("pipeline.config.loaded", workers=config.enrich_workers)

    # === Storage ===
    storage = get_storage()
    await storage.initialize()
    log.info("ingestor.storage.initialized")

    # === Lock Manager ===
    lock_manager = LLMLockManager()

    # === Vector Store ===
    # Get vector store from storage adapter
    if storage._vector_store is None:
        raise RuntimeError(f"Storage {type(storage).__name__} does not provide a vector store")
    vector_store = storage._vector_store
    log.info("ingestor.vector_store.reused_from_storage")

    # === Embedding Model ===
    # Create embedding model using config values
    embed_model_raw = EmbeddingModel(
        embed_url=config.embedding.url,
        api_key=config.embedding.api_key,
        served_model_name=config.embedding.model_name,
        rate_limit_rpm=config.embedding.rate_limit_rpm,
        max_chars=config.embedding.max_chars,
        batch_size=config.embedding.batch_size,
    )

    # Wrap with adapter to provide BaseEmbedding interface for llama_index
    embed_model = EmbeddingModelAdapter(embed_model_raw)

    # === Validate dimensions (must match exactly) ===
    log.info("dimension_validator.validation.started")
    dimension_validator = DimensionValidator(
        embed_model=embed_model_raw, storage=storage, lock_manager=lock_manager
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

    # === LLM (for chunk enrichment) ===
    # Use MODEL_NAME from config
    llm = OpenAILike(
        api_base=config.llm.url,
        api_key=config.llm.api_key,
        model=config.llm.model_name,
        is_chat_model=True,
        is_function_calling_model=True,
    )

    # === Pipeline Context ===
    pipeline_context = PipelineContext(
        workspace_path=Path(workspace),
        storage=storage,
        llm=llm,
        lock_manager=lock_manager,
        embed_model=embed_model,
        vector_store=vector_store,
        text_splitter_helper=TextSplitterHelper(
            python_chunk_lines=config.python_chunk_lines,
            python_chunk_overlap=config.python_chunk_overlap,
            python_max_chars=config.python_max_chars,
            doc_chunk_size=config.doc_chunk_size,
            doc_chunk_overlap=config.doc_chunk_overlap,
            config_chunk_size=config.config_chunk_size,
            config_chunk_overlap=config.config_chunk_overlap,
        ),
        config=config.model_dump(),
    )

    # === Knowledge Port ===
    knowledge_port = KnowledgePort(pipeline_context, knowledge_index=knowledge_index)
    log.info("knowledge_port.ready")

    # === Indexer Orchestrator ===
    indexer = IndexerOrchestrator(pipeline_context)

    async def start_and_scan():
        await indexer.start()
        await indexer.start_full_scan()
        await indexer.start_watching()

    indexer_task = asyncio.create_task(start_and_scan())
    log.info("ingestor.indexer.started")

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

    # Wait for API server (this is the main foreground task)
    try:
        await api_task
    except asyncio.CancelledError:
        pass
    finally:
        # === Graceful Shutdown ===
        log.info("ingestor.shutdown.start")
        _shutdown.set()

        # Stop indexer
        await indexer.stop()
        indexer_task.cancel()
        try:
            await indexer_task
        except asyncio.CancelledError:
            pass

        # Cancel API task if still running
        api_task.cancel()
        try:
            await api_task
        except asyncio.CancelledError:
            pass

        # Close embedding model
        if hasattr(embed_model_raw, 'close') and callable(getattr(embed_model_raw, 'close')):
            try:
                await embed_model_raw.close()
                log.info("embedding_model.closed")
            except Exception as e:
                log.error("embedding_model.close.failed", error=str(e))

        # Close LLM if it has close method
        if hasattr(llm, 'aclose') and callable(getattr(llm, 'aclose')):
            try:
                await llm.aclose()
                log.info("llm.closed")
            except Exception as e:
                log.error("llm.close.failed", error=str(e))

        # Close storage
        if hasattr(storage, 'close') and callable(getattr(storage, 'close')):
            try:
                await storage.close()
                log.info("storage.closed")
            except Exception as e:
                log.error("storage.close.failed", error=str(e))

        log.info("ingestor.shutdown.complete")


if __name__ == "__main__":
    asyncio.run(main())
