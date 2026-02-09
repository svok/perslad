"""
Ingestor Main Entry Point

Запускает:
1. HTTP API (для LLM lock и статистики)
2. Indexer Pipeline (scanner + enrich)
3. LLM reconnect (background)
"""

import asyncio
import signal
import sys

import uvicorn
from dotenv import load_dotenv

from ingestor.app.indexer import IndexerOrchestrator

# Load env vars BEFORE config imports
load_dotenv(dotenv_path="../.env", override=False)

from infra.llm import get_llm
from infra.logger import setup_logging, get_logger
from ingestor.adapters import get_storage
from ingestor.adapters.embedding_model import EmbeddingModel
from ingestor.api.server import IngestorAPI
from ingestor.config import runtime, storage as storage_config
from ingestor.app.dimension_validator import DimensionValidator
from ingestor.app.knowledge_port import KnowledgePort
from ingestor.app.llm_lock import LLMLockManager
# from ingestor.app.indexer_test import IndexerOrchestrator

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
    env = runtime.ENV
    workspace = runtime.WORKSPACE_PATH
    api_port = runtime.INGESTOR_PORT
    log_level = runtime.LOG_LEVEL

    setup_logging(log_level=log_level)
    log = get_logger("ingestor")

    log.info(
        "ingestor.boot",
        env=env,
        workspace=workspace,
        port=api_port,
        storage_type=storage_config.STORAGE_TYPE,
    )

    _install_signal_handlers(log)

    # === Инициализация компонентов ===

    llm = get_llm()
    lock_manager = LLMLockManager()
    storage = get_storage()

    # Initialize storage tables immediately (explicitly)
    await storage.initialize()
    log.info("ingestor.storage.initialized")

    knowledge_port = KnowledgePort(storage)

    # VALIDATE — will retry indefinitely
    log.info("dimension_validator.validation.started")
    dimension_validator = DimensionValidator(
        embed_model=EmbeddingModel(runtime.EMBED_URL, runtime.EMBED_API_KEY),
        storage=storage,
        lock_manager=lock_manager
    )
    await dimension_validator.validate_dimensions()
    log.info("dimension_validator.validation.complete")

    # Indexer orchestrator
    indexer = IndexerOrchestrator(
        workspace_path=workspace,
        llm=llm,
        lock_manager=lock_manager,
        storage=storage,
        knowledge_port=knowledge_port,
        embed_url=runtime.EMBED_URL,
        embed_api_key=runtime.EMBED_API_KEY,
    )

    # HTTP API
    api = IngestorAPI(lock_manager, storage, knowledge_port)

    # === Запуск фоновых задач ===

    # 1. LLM reconnect (бесконечный)
    asyncio.create_task(llm.ensure_ready())
    log.info("ingestor.llm.reconnect.started")

    # 2. HTTP API server
    api_task = asyncio.create_task(run_api_server(api, api_port))
    log.info("ingestor.api.started", port=api_port)

    # 3. Ждём готовности LLM перед запуском indexer
    log.info("ingestor.waiting_llm")
    await llm.wait_ready()
    log.info("ingestor.llm.ready")

    # 4. Запускаем indexer (full scan при старте)
    log.info("ingestor.indexer.starting")
    try:
        await indexer.start()
        await indexer.start_full_scan()  # Полный скан
        await indexer.start_watching()  # Добавляем inotify watch
        log.info("ingestor.indexer.started")
    except Exception as e:
        log.error("ingestor.indexer.error", error=str(e), exc_info=True)
        raise

    # === Основной цикл ===

    log.info("ingestor.running")

    # Ждём сигнала остановки
    await _shutdown.wait()

    # Останавливаем indexer
    if 'indexer' in locals():
        log.info("ingestor.indexer.stopping")
        try:
            await indexer.stop()
        except Exception as e:
            log.error("ingestor.indexer.stop.error", error=str(e), exc_info=True)

    # Останавливаем API
    api_task.cancel()
    try:
        await api_task
    except asyncio.CancelledError:
        pass

    log.info("ingestor.shutdown.complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception:
        raise