import asyncio
from pathlib import Path
from typing import List, Optional, Set, Dict, Any

from infra.logger import get_logger
from .queues import ThrottledQueue
from .pipeline_context import StageContext
from .pipeline_builder import PipelineBuilder, StageDef
from .stages.indexer_sink import IndexerSinkStage
from .stages.source_stage import SourceStage

class MultiSourcePipeline:
    DEFAULT_CONFIG = {
        'enrich_workers': 2, 'parse_workers': 1, 'chunk_enrich_workers': 2,
        'embed_workers': 2, 'persist_workers': 2, 'file_summary_workers': 2,
        'queue_size': 1000,
    }

    def __init__(self, workspace_path: Path, storage, llm, lock_manager,
                 embed_url: str, embed_api_key: str, config: Optional[dict] = None):
        self.log = get_logger('ingestor.pipeline')
        self.config = {**self.DEFAULT_CONFIG, **(config or {})}

        # Создаем контекст один раз
        self._ctx = StageContext(
            workspace_path=Path(workspace_path),
            storage=storage,
            llm=llm,
            lock_manager=lock_manager,
            embed_url=embed_url,
            embed_api_key=embed_api_key,
            config=self.config
        )

        self._stage_defs = PipelineBuilder.get_default_definitions()
        self._queues: List[ThrottledQueue] = []
        self._processors: List[Any] = []
        self._sources: Set[SourceStage] = set()
        self._sink: Optional[IndexerSinkStage] = None
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        if self._running: return
        self._running = True

        # 1. Создаем очереди
        num_queues = len(self._stage_defs) + 1
        self._queues = [ThrottledQueue(self.config['queue_size'], name=f"q_{i}") for i in range(num_queues)]

        # 2. Строим стадии через фабрики
        for i, defn in enumerate(self._stage_defs):
            stage = defn.factory(self._ctx) # Передаем только контекст
            await stage.start(self._queues[i], self._queues[i+1])
            self._processors.append(stage)

        # 3. Sink
        self._sink = IndexerSinkStage()
        await self._sink.start(self._queues[-1])

        # 4. ЗАПУСКАЕМ МОНИТОРИНГ
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        self.log.info("Pipeline and monitor started")

    async def add_source(self, source: SourceStage, wait: bool = False) -> None:
        if not self._running: raise RuntimeError("Start pipeline first")
        self._sources.add(source)
        await source.start(self._queues[0])
        if wait:
            await source.wait()
            self._sources.discard(source)

    async def stop(self) -> None:
        if not self._running: return
        self._running = False

        for src in list(self._sources): await src.stop()

        # Poison pill для первой стадии
        if self._processors:
            for _ in range(self._processors[0].max_workers):
                await self._queues[0].put(None)

        for proc in self._processors: await proc.stop()
        if self._sink: await self._sink.stop()
        self.log.info("Pipeline stopped")

    async def _monitor_loop(self) -> None:
        """Фоновая задача для вывода статистики каждые 10 секунд"""
        self.log.debug("Queue monitor loop started")
        try:
            while self._running:
                # Формируем строку статистики
                stats = []
                for q in self._queues:
                    # q.qsize() в asyncio не всегда точен, но для мониторинга подходит
                    size = q.qsize
                    stats.append(f"{q.name}: {size}")

                self.log.info(f"[STATS] Queues: {' | '.join(stats)}")

                # Ждем 10 секунд, но просыпаемся, если пайплайн остановлен
                await asyncio.sleep(10)
        except asyncio.CancelledError:
            self.log.debug("Queue monitor loop cancelled")
        except Exception as e:
            self.log.error(f"Monitor error: {e}")

