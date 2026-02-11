"""
Indexer Orchestrator

Координирует запуск пайплайна и переключается между режимами.
"""

import asyncio
from pathlib import Path

from infra.managers.llm import LLMManager
from infra.logger import get_logger
from ingestor.core.ports.storage import BaseStorage
from ingestor.pipeline.indexation.indexer_pipeline import IndexationPipeline
from ingestor.pipeline.stages.inotify_source import InotifySourceStage
from ingestor.pipeline.stages.scanner_source_stage import ScannerSourceStage
from ingestor.services.knowledge import KnowledgePort
from ingestor.services.lock import LLMLockManager


class IndexerOrchestrator:
    def __init__(
            self,
            workspace_path: str,
            llm: LLMManager,
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

        # self.gitignore_matchers: Dict[Path, Callable] = {}
        self._pipeline: IndexationPipeline | None = None
        self._running = False
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Запускает пайплайн (processors only)"""
        async with self._lock:
            if self._running:
                return
            self._running = True

        # self._load_gitignores()

        # Ленивый импорт чтобы избежать circular dependency

        self._pipeline = IndexationPipeline(
            workspace_path=self.workspace_path,
            storage=self.storage,
            llm = self.llm,
            lock_manager = self.lock_manager,
            embed_url = self.embed_url,
            embed_api_key = self.embed_api_key,
            config={
                'filter_workers': 2,
                'enrich_workers': 4,
                'queue_size': 2000,
            }
        )

        await self._pipeline.start()
        self.log.info("indexer.pipeline_ready")

    async def start_full_scan(self) -> None:
        """Полный скан — blocking"""
        if not self._pipeline:
            raise RuntimeError("Call start() first")

        self.log.info("indexer.full_scan.starting")
        scanner = ScannerSourceStage(self.workspace_path)
        await self._pipeline.add_source(scanner, wait=True)
        self.log.info("indexer.full_scan.completed")

    async def start_watching(self) -> None:
        """Inotify — background"""
        if not self._pipeline:
            raise RuntimeError("Call start() first")

        self.log.info("indexer.watching.starting")
        inotify = InotifySourceStage(
            self.workspace_path,
            # gitignore_checker=self._should_ignore
        )
        await self._pipeline.add_source(inotify, wait=False)
        self.log.info("indexer.watching.started")

    async def stop(self) -> None:
        """Останавливает индексер"""
        async with self._lock:
            if not self._running:
                return
            self._running = False

        self.log.info("indexer.stopping")
        if self._pipeline:
            await self._pipeline.stop()
        self.log.info("indexer.stopped")
