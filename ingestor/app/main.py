"""
Ingestor Main Entry Point

Запускает:
1. HTTP API (для LLM lock и статистики)
2. Ingest pipeline (batch)
3. LLM reconnect (background)
"""

import asyncio
import os
import signal
import sys

from dotenv import load_dotenv
import uvicorn

from infra.logger import setup_logging, get_logger
from infra.llm import get_llm
from ingestor.app.llm_lock import LLMLockManager
from ingestor.app.pipeline.orchestrator import PipelineOrchestrator
from ingestor.app.knowledge_port import KnowledgePort
from ingestor.app.api import IngestorAPI
from ingestor.app.config import runtime, storage as storage_config, llm as llm_config
from ingestor.adapters import get_storage

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
    load_dotenv(dotenv_path="../.env", override=False)

    env = runtime.ENV
    workspace = runtime.WORKSPACE_PATH
    api_port = runtime.INGESTOR_PORT
    log_level = runtime.LOG_LEVEL

    setup_logging(env=env, log_level=log_level)
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
    knowledge_port = KnowledgePort(storage)

    # Pipeline orchestrator
    pipeline = PipelineOrchestrator(
        workspace_path=workspace,
        llm=llm,
        lock_manager=lock_manager,
        storage=storage,
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

    # 3. Ждём готовности LLM перед запуском pipeline
    log.info("ingestor.waiting_llm")
    await llm.wait_ready()
    log.info("ingestor.llm.ready")

    # 4. Запускаем pipeline
    log.info("ingestor.pipeline.starting")
    try:
        await pipeline.run_full_pipeline()
        log.info("ingestor.pipeline.finished")
    except Exception as e:
        log.error("ingestor.pipeline.error", error=str(e), exc_info=True)

    # === Основной цикл ===

    log.info("ingestor.running")

    # Ждём сигнала остановки
    await _shutdown.wait()

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
