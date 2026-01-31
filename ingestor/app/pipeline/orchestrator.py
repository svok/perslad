"""
Pipeline Orchestrator

Координирует выполнение всех stages.
Детерминированный, перезапускаемый, можно остановить в любой момент.
"""

from typing import Optional
import asyncio
import time

from llama_index.embeddings.openai import OpenAIEmbedding

from infra.logger import get_logger
from infra.llm import LLMClient
from ingestor.app.storage import InMemoryStorage, Chunk
from ingestor.app.llm_lock import LLMLockManager
from ingestor.app.pipeline.scan import ScanStage
from ingestor.app.pipeline.parse import ParseStage
from ingestor.app.pipeline.enrich import EnrichStage
from ingestor.app.pipeline.embed import EmbedStage
from ingestor.app.pipeline.persist import PersistStage

log = get_logger("ingestor.pipeline.orchestrator")


class PipelineOrchestrator:
    """
    Управляет выполнением ingest pipeline.
    """

    def __init__(
        self,
        workspace_path: str,
        llm: LLMClient,
        lock_manager: LLMLockManager,
        storage: InMemoryStorage,
        embed_model: Optional[OpenAIEmbedding] = None,
    ) -> None:
        self.workspace_path = workspace_path
        self.llm = llm
        self.lock_manager = lock_manager
        self.storage = storage
        
        # Инициализируем stages
        self.scan_stage = ScanStage(workspace_path)
        self.parse_stage = ParseStage()
        self.enrich_stage = EnrichStage(llm, lock_manager)
        
        # Embed model (опционально для MVP)
        if embed_model:
            self.embed_stage = EmbedStage(embed_model)
        else:
            self.embed_stage = None
        
        self.persist_stage = PersistStage(storage)

    class EnrichCollector:
        def __init__(self, storage: InMemoryStorage, max_buffer=100, debounce=1.0):
            self.queue = asyncio.Queue(max_buffer)
            self.buffer = []
            self.last_time = time.time()
            self.timer = None
            self.lock = asyncio.Lock()
            self.done = False
            self.storage = storage
            self.debounce = debounce

        async def add(self, chunk: Chunk):
            await self.queue.put(chunk)
            async with self.lock:
                if self.timer is None:
                    self.timer = asyncio.create_task(self._flush())

        async def _flush(self):
            while not self.queue.empty():
                try:
                    chunk = await asyncio.wait_for(self.queue.get(), timeout=self.debounce)
                    self.buffer.append(chunk)
                except asyncio.TimeoutError:
                    break

            if len(self.buffer) >= 100:
                return

            if self.buffer and (time.time() - self.last_time >= self.debounce):
                log.info("collector.flush", chunk_count=len(self.buffer))
                await self.storage.save_chunks(self.buffer.copy())
                self.buffer.clear()

            self.last_time = time.time()
            async with self.lock:
                self.timer = None

        async def wait_done(self):
            log.info("collector.waiting_done")
            await self.queue.join()
            await self._flush()
            if self.buffer:
                log.info("collector.flush.final", chunk_count=len(self.buffer))
                await self.storage.save_chunks(self.buffer.copy())

    async def run_full_pipeline(self) -> None:
        """
        Запускает полный pipeline от начала до конца.
        """
        log.info("pipeline.start", workspace=self.workspace_path)

        try:
            files_queue = asyncio.Queue(maxsize=100)
            enriched_queue = asyncio.Queue(maxsize=100)

            collector = self.EnrichCollector(self.storage, max_buffer=100, debounce=1.0)

            scan_task = asyncio.create_task(self._scan_producer(files_queue))
            parse_enrich_task = asyncio.create_task(self._parse_enrich_consumer(files_queue, enriched_queue))
            save_task = asyncio.create_task(self._save_consumer(enriched_queue, collector))

            log.info("pipeline.tasks.created")
            await scan_task
            log.info("pipeline.task.scan.complete")

            await parse_enrich_task
            log.info("pipeline.task.parse_enrich.complete")

            await save_task
            log.info("pipeline.task.save.complete")

            log.info("pipeline.complete")

        except Exception as e:
            log.error("pipeline.failed", error=str(e), exc_info=True)
            raise

    async def _scan_producer(self, queue: asyncio.Queue) -> None:
        log.info("scan_producer.starting")
        files = await self.scan_stage.run()
        log.info("scan_producer.finished", files_count=len(files))
        for file in files:
            await queue.put(file)
        # Отправляем два sentinel для разных consumer
        await queue.put(None)  # sentinel для parse_enrich_consumer
        await queue.put(None)  # sentinel для save_consumer
        log.info("scan_producer.sentinel_sent")

    async def _parse_enrich_consumer(self, files_queue: asyncio.Queue, enriched_queue: asyncio.Queue) -> None:
        log.info("parse_enrich_consumer.starting")
        enriched_count = 0
        sentinel_count = 0

        while True:
            files = await files_queue.get()
            if files is None:
                sentinel_count += 1
                log.info("parse_enrich_consumer.received sentinel", count=sentinel_count)
                # Дождаться двух sentinel-ов: один для parse, один для save
                if sentinel_count >= 2:
                    break
                continue

            chunks = await self.parse_stage.run(files)
            enriched = await self.enrich_stage.run(chunks)
            enriched_count += len(enriched)
            log.info("parse_enrich_consumer.enriched", chunks_count=len(chunks), enriched_count=enriched_count)

            for chunk in enriched:
                await enriched_queue.put(chunk)

        log.info("parse_enrich_consumer.finished", total_enriched=enriched_count)

    async def _save_consumer(self, queue: asyncio.Queue, collector: EnrichCollector) -> None:
        log.info("save_consumer.starting")
        sentinel_count = 0
        enriched_chunks_passed = 0

        while True:
            chunk = await queue.get()
            if chunk is None:
                sentinel_count += 1
                log.info("save_consumer.received sentinel", count=sentinel_count)
                if sentinel_count >= 2:
                    break
                continue

            enriched_chunks_passed += 1
            log.debug("save_consumer.received enriched chunk", count=enriched_chunks_passed)
            await collector.add(chunk)

        log.info("save_consumer.finished", enriched_chunks_passed=enriched_chunks_passed)
        await collector.wait_done()

    async def run_incremental(self, file_paths: list[str]) -> None:
        """
        Инкрементальная индексация конкретных файлов.
        Для будущего использования (file watcher, CI).
        """
        log.info("pipeline.incremental.start", files_count=len(file_paths))
        # TODO: implement incremental indexing
        log.warning("pipeline.incremental.not_implemented")
