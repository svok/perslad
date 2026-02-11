import asyncio
from dataclasses import replace
from pathlib import Path
from typing import Optional, Set

from .builder import IndexationPipelineBuilder
from .queues import ThrottledQueue
from ingestor.pipeline.stages.indexer_sink import IndexerSinkStage
from ingestor.pipeline.base.source_stage import SourceStage

from ..base.base_pipeline import BasePipeline
from ..models.pipeline_context import PipelineContext


class IndexationPipeline(BasePipeline):
    DEFAULT_CONFIG = {
        **BasePipeline.DEFAULT_CONFIG,
        'enrich_workers': 2, 'parse_workers': 1, 'chunk_enrich_workers': 2,
        'embed_workers': 2, 'persist_workers': 2, 'file_summary_workers': 2,
    }

    def __init__(self, pipeline_context: PipelineContext):
        super().__init__(
            replace(pipeline_context, config={**pipeline_context.config, **IndexationPipeline.DEFAULT_CONFIG})
        )

        self._stage_defs = IndexationPipelineBuilder.get_default_definitions()
        self._sources: Set[SourceStage] = set()
        self._sink: Optional[IndexerSinkStage] = None

    async def start(self) -> None:
        if self._running: return
        self._running = True

        # 1. Создаем очереди
        num_queues = len(self._stage_defs) + 1
        self._queues = [ThrottledQueue(self.config['queue_size'], name=f"q_{i}") for i in range(num_queues)]

        # 2. Строим стадии через фабрики
        for i, defn in enumerate(self._stage_defs):
            stage = defn.factory(self._ctx)  # Передаем только контекст
            await stage.start(self._queues[i], self._queues[i + 1])
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

        for src in list(self._sources): await src.stop()

        # Poison pill для первой стадии
        if self._processors:
            for _ in range(self._processors[0].max_workers):
                await self._queues[0].put(None)

        if self._sink: await self._sink.stop()
        await super().stop()
