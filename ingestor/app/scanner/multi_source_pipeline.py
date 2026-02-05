import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar, Callable, Any, List, Optional, Type, Set

from infra.logger import get_logger
from ingestor.app.llm_lock import LLMLockManager
from ingestor.app.scanner.file_event import FileEvent
from ingestor.app.scanner.queues import ThrottledQueue
from ingestor.app.scanner.stages.enrich_stage import EnrichStage
from ingestor.app.scanner.stages.indexer_sink import IndexerSinkStage
from ingestor.app.scanner.stages.processor_stage import ProcessorStage
from ingestor.app.scanner.stages.sink_stage import SinkStage
from ingestor.app.scanner.stages.source_stage import SourceStage

T = TypeVar('T')
U = TypeVar('U')


@dataclass
class StageDef:
    """Определение стадии в пайплайне"""
    name: str
    stage_class: Type[ProcessorStage]
    config_key: str  # ключ в self.config для max_workers
    input_type: Type[Any]
    output_type: Type[Any]
    # Фабрика для создания инстанса (получает pipeline как аргумент)
    factory: Callable[[Any], ProcessorStage]


class MultiSourcePipeline:
    """Декларативный пайплайн — описываем структуру, система собирает"""

    DEFAULT_CONFIG = {
        'enrich_workers': 2,
        'parse_workers': 1,
        'chunk_enrich_workers': 2,
        'embed_workers': 2,
        'persist_workers': 2,
        'file_summary_workers': 2,
        'queue_size': 1000,
    }

    def __init__(
            self,
            workspace_path: Path,
            storage,
            llm,
            lock_manager: LLMLockManager,
            embed_url: str,
            embed_api_key: str,
            config: Optional[dict] = None
    ):
        self.log = get_logger('ingestor.pipeline')
        self.workspace_path = Path(workspace_path)
        self.storage = storage
        self.config = {**self.DEFAULT_CONFIG, **(config or {})}

        self._llm = llm
        self._lock_manager = lock_manager
        self._embed_url = embed_url
        self._embed_api_key = embed_api_key

        # Описание пайплайна (тапл — последовательность)
        self._stage_defs: List[StageDef] = [
            StageDef(
                name="enrich",
                stage_class=EnrichStage,
                config_key="enrich_workers",
                input_type=FileEvent,
                output_type=FileEvent,
                factory=lambda p: EnrichStage(p.workspace_path, p.config["enrich_workers"])
            ),
            # StageDef(
            #     name="parse",
            #     stage_class=ParseProcessorStage,
            #     config_key="parse_workers",
            #     input_type=FileEvent,
            #     output_type=List[Chunk],
            #     factory=lambda p: ParseProcessorStage(p.config["parse_workers"])
            # ),
            # StageDef(
            #     name="chunk_enrich",
            #     stage_class=EnrichChunksStage,
            #     config_key="chunk_enrich_workers",
            #     input_type=List[Chunk],
            #     output_type=List[Chunk],
            #     factory=lambda p: EnrichChunksStage(p._llm, p._lock_manager, p.config["chunk_enrich_workers"])
            # ),
            # StageDef(
            #     name="embed",
            #     stage_class=EmbedChunksStage,
            #     config_key="embed_workers",
            #     input_type=List[Chunk],
            #     output_type=List[Chunk],
            #     factory=lambda p: EmbedChunksStage(p._embed_url, p._embed_api_key, p.config["embed_workers"])
            # ),
            # StageDef(
            #     name="persist",
            #     stage_class=PersistChunksStage,
            #     config_key="persist_workers",
            #     input_type=List[Chunk],
            #     output_type=List[Chunk],
            #     factory=lambda p: PersistChunksStage(p.storage, p.config["persist_workers"])
            # ),
            # StageDef(
            #     name="file_summary",
            #     stage_class=FileSummaryStage,
            #     config_key="file_summary_workers",
            #     input_type=List[Chunk],
            #     output_type=List[Chunk],
            #     factory=lambda p: FileSummaryStage(p.storage, p.config["file_summary_workers"])
            # ),
        ]

        # Runtime
        self._queues: List[ThrottledQueue] = []
        self._processors: List[ProcessorStage] = []
        self._sink: Optional[SinkStage] = None
        self._sources: Set[SourceStage] = set()
        self._running = False

    async def start(self) -> None:
        """Автоматически собирает пайплайн из _stage_defs"""
        if self._running:
            return

        self._running = True
        self.log.info(f"Building pipeline with {len(self._stage_defs)} stages")

        # Создаём очереди: N стадий = N+1 очередей (включая вход для sink)
        num_queues = len(self._stage_defs) + 1
        self._queues = [
            ThrottledQueue(self.config['queue_size'], name=f"q_{i}")
            for i in range(num_queues)
        ]

        # Создаём и подключаем стадии
        self._processors = []
        for i, defn in enumerate(self._stage_defs):
            stage = defn.factory(self)
            input_q = self._queues[i]
            output_q = self._queues[i + 1]

            self.log.debug(f"Connecting {defn.name}: q_{i} → q_{i+1}")
            await stage.start(input_q, output_q)
            self._processors.append(stage)

        # Sink забирает из последней очереди
        self._sink = IndexerSinkStage()
        await self._sink.start(self._queues[-1])

        self.log.info(f"Pipeline ready: {len(self._processors)} stages, {len(self._queues)} queues")

    async def add_source(self, source: SourceStage, wait: bool = False) -> None:
        """Добавляет источник в первую очередь"""
        if not self._running:
            raise RuntimeError("Call start() first")

        self.log.info(f"Adding source: {source.name}")
        await source.start(self._queues[0])  # Всегда в первую очередь
        self._sources.add(source)

        if wait and source._task:
            await source._task
            self._sources.discard(source)
            self.log.info(f"Source {source.name} completed")

    async def stop(self) -> None:
        """Graceful shutdown"""
        if not self._running:
            return

        self.log.info("Stopping...")
        self._running = False

        # Sources
        for src in list(self._sources):
            await src.stop()

        # Poison pill — по одному на каждого воркера первой стадии
        first_stage_workers = self._processors[0].max_workers if self._processors else 1
        for _ in range(first_stage_workers):
            try:
                await asyncio.wait_for(self._queues[0].put(None), timeout=1.0)
            except asyncio.TimeoutError:
                break

        # Processors
        for proc in self._processors:
            await proc.stop()

        # Sink
        await self._sink.stop()

        # Drain
        for q in self._queues:
            while True:
                try:
                    q.get_nowait()
                    q.task_done()
                except asyncio.QueueEmpty:
                    break

        self.log.info("Stopped")
