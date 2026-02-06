"""
Indexer Orchestrator - TEST VERSION

Прямой запуск SA + SB из test_pipeline без боевого MultiSourcePipeline
"""

import asyncio
from pathlib import Path
from typing import Optional

from infra.llm import LLMClient
from infra.logger import get_logger
from ingestor.adapters.base_storage import BaseStorage
from ingestor.app.knowledge_port import KnowledgePort
from ingestor.app.llm_lock import LLMLockManager
from ingestor.app.scanner.queues import ThrottledQueue
from ingestor.app.scanner.file_event import FileEvent

from ingestor.app.test_pipeline import handler
from ingestor.app.test_pipeline.main import StdoutSink
from ingestor.app.test_pipeline.sa import SourceSA
from ingestor.app.test_pipeline.sb import SourceSB


class IndexerOrchestrator:
    def __init__(
            self,
            workspace_path: str,
            llm: LLMClient,
            lock_manager: LLMLockManager,
            storage: BaseStorage,
            knowledge_port: KnowledgePort,
            embed_url: str = "http://emb:8001/v1",
            embed_api_key: str = "sk-dummy",
    ) -> None:
        self.workspace_path = Path(workspace_path).resolve()
        self.log = get_logger("ingestor.indexer")
        self.llm = llm
        self.lock_manager = lock_manager
        self.storage = storage
        self.knowledge_port = knowledge_port
        self.embed_url = embed_url
        self.embed_api_key = embed_api_key

        self._pipeline: handler.Handler | None = None
        self._running = False
        self._lock = asyncio.Lock()
        self._sa_task = None
        self._sb_task = None
        self._sa_queue: Optional[ThrottledQueue[FileEvent]] = None
        self._sb_queue: Optional[ThrottledQueue[FileEvent]] = None

    async def start(self) -> None:
        """Запускает пайплайн"""
        async with self._lock:
            if self._running:
                return
            self._running = True

        # Create queues - TEST VERSION with ThrottledQueue
        self._sa_queue = ThrottledQueue(maxsize=2000, throttle_delay=0, name="sa_queue")
        self._sb_queue = ThrottledQueue(maxsize=2000, throttle_delay=0, name="sb_queue")

        # Create Handler with StdoutSink
        self._pipeline = handler.Handler(StdoutSink())
        await self._pipeline.set_queues(self._sa_queue, self._sb_queue)

        self.log.info("indexer.pipeline_ready")

    async def start_full_scan(self) -> None:
        """Полный скан - запускаем SA и ЖДЕМ завершения"""
        if not self._sa_queue:
            raise RuntimeError("Call start() first")

        self.log.info("indexer.full_scan.starting")

        # Запускаем SA и БЛОКИРУЕМся пока он завершится
        self._sa_task = asyncio.create_task(
            SourceSA(self._sa_queue, name="SA", message_template="msg-a").start()
        )
        await self._sa_task
        self.log.info("indexer.full_scan.completed")

    async def start_watching(self) -> None:
        """Inotify - запускаем SB"""
        if not self._pipeline:
            raise RuntimeError("Call start() first")

        self.log.info("indexer.watching.starting")

        # Запускаем SB
        self._sb_task = asyncio.create_task(
            SourceSB(self._sb_queue, name="SB", message_template="msg-b").start()
        )

        self.log.info("indexer.watching.started")

    async def stop(self) -> None:
        """Останавливает индексер"""
        async with self._lock:
            if not self._running:
                return
            self._running = False

        self.log.info("indexer.stopping")

        if self._sa_task:
            self._sa_task.cancel()
            try:
                await self._sa_task
            except asyncio.CancelledError:
                pass

        if self._sb_task:
            self._sb_task.cancel()
            try:
                await self._sb_task
            except asyncio.CancelledError:
                pass

        if self._pipeline:
            await self._pipeline.stop()

        self.log.info("indexer.stopped")
