"""
Indexer Orchestrator

Координирует запуск пайплайна и переключается между режимами.
"""

import asyncio
from dataclasses import replace

from infra.logger import get_logger
from ingestor.pipeline.indexation.pipeline import IndexationPipeline
from ingestor.pipeline.models.pipeline_context import PipelineContext
from ingestor.pipeline.stages.inotify_source import InotifySourceStage
from ingestor.pipeline.stages.scanner_source_stage import ScannerSourceStage


class IndexerOrchestrator:
    def __init__(self, pipeline_context: PipelineContext) -> None:
        self.pipeline_context = replace(
            pipeline_context,
            config={**pipeline_context.config,
                    'filter_workers': 2,
                    'enrich_workers': 4,
                    'queue_size': 2000,
                    }
        )
        self.log = get_logger("ingestor.indexer")

        self._pipeline: IndexationPipeline = IndexationPipeline(self.pipeline_context)
        self.workspace_path = self.pipeline_context.workspace_path
        self._running = False
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Запускает пайплайн (processors only)"""
        async with self._lock:
            if self._running:
                return
            self._running = True

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
