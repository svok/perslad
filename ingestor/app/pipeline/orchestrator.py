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
            self.total_added = 0
            self.total_flushed = 0

        async def add(self, chunk: Chunk):
            self.total_added += 1
            log.debug("collector.add.call", total_added=self.total_added)
            await self.queue.put(chunk)
            async with self.lock:
                if self.timer is None:
                    self.timer = asyncio.create_task(self._flush())

        async def _flush(self):
            log.debug("collector.flush.start", buffer_len=len(self.buffer), queue_empty=self.queue.empty())
            
            while not self.queue.empty():
                try:
                    chunk = await asyncio.wait_for(self.queue.get(), timeout=self.debounce)
                    self.buffer.append(chunk)
                except asyncio.TimeoutError:
                    break

            if len(self.buffer) >= 100:
                log.info("collector.flush.buffer_full", buffer_len=len(self.buffer), flushing=True)
                await self.storage.save_chunks(self.buffer.copy())
                self.total_flushed += len(self.buffer)
                log.info("collector.flush.saved", saved_count=len(self.buffer), total_flushed=self.total_flushed)
                self.buffer.clear()
                return

            if self.buffer and (time.time() - self.last_time >= self.debounce):
                log.info("collector.flush.timeout", buffer_len=len(self.buffer))
                await self.storage.save_chunks(self.buffer.copy())
                self.total_flushed += len(self.buffer)
                log.info("collector.flush.saved", saved_count=len(self.buffer), total_flushed=self.total_flushed)
                self.buffer.clear()

            self.last_time = time.time()
            async with self.lock:
                self.timer = None

        async def wait_done(self):
            log.info("collector.waiting_done", total_added=self.total_added, buffer_len=len(self.buffer), queue_empty=self.queue.empty())
            await self.queue.join()
            await self._flush()
            if self.buffer:
                log.info("collector.flush.final", buffer_len=len(self.buffer))
                await self.storage.save_chunks(self.buffer.copy())
                self.total_flushed += len(self.buffer)
                log.info("collector.flush.saved", saved_count=len(self.buffer), total_flushed=self.total_flushed)
                self.buffer.clear()
            
            log.info("collector.done", total_added=self.total_added, total_flushed=self.total_flushed)

    async def run_full_pipeline(self) -> None:
        """
        Запускает полный pipeline от начала до конца.
        """
        log.info("pipeline.start", workspace=self.workspace_path)

        try:
            files_queue = asyncio.Queue(maxsize=100)
            enriched_queue = asyncio.Queue(maxsize=100)

            collector = self.EnrichCollector(self.storage, max_buffer=100, debounce=1.0)

            log.info("pipeline.tasks.created")
            
            scan_task = asyncio.create_task(self._scan_producer(files_queue))
            parse_enrich_task = asyncio.create_task(self._parse_enrich_consumer(files_queue, enriched_queue))
            save_task = asyncio.create_task(self._save_consumer(enriched_queue, collector))

            log.info("pipeline.tasks.running")
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

    async def _scan_producer(self, files_queue: asyncio.Queue) -> None:
        log.info("scan_producer.starting")
        files = await self.scan_stage.run()
        log.info("scan_producer.finished", files_count=len(files))
        
        future = asyncio.Future()
        
        async def put_with_callback():
            try:
                for i, file in enumerate(files):
                    await files_queue.put(file)
                    log.debug("scan_producer.put_file", index=i, total=len(files), filename=file)
                future.set_result(None)
            except Exception as e:
                future.set_exception(e)
        
        asyncio.create_task(put_with_callback())
        await future
        log.info("scan_producer.all_files_sent")
        
        # Отправляем только 1 sentinel после того, как все файлы отправлены
        await files_queue.put(None)
        log.info("scan_producer.sentinel_sent")

    async def _parse_enrich_consumer(self, files_queue: asyncio.Queue, enriched_queue: asyncio.Queue) -> None:
        log.info("parse_enrich_consumer.starting")
        enriched_count = 0
        sentinel_received = False

        while True:
            files = await files_queue.get()
            if files is None:
                sentinel_received = True
                log.info("parse_enrich_consumer.received sentinel")
                break

            log.info("parse_enrich_consumer.get_files", files_count=len(files), files=files[:3] if len(files) > 3 else files)
            
            chunks = await self.parse_stage.run(files)
            enriched = await self.enrich_stage.run(chunks)
            enriched_count += len(enriched)
            log.info("parse_enrich_consumer.enriched", chunks_count=len(chunks), enriched_count=enriched_count)

            for i, chunk in enumerate(enriched):
                await enriched_queue.put(chunk)
                log.debug("parse_enrich_consumer.put_chunk", chunk_index=i, total=len(enriched), chunk_id=chunk.id)

        # Отправляем sentinel в enriched_queue после обработки всех files
        if sentinel_received:
            log.info("parse_enrich_consumer.send_enriched_sentinel", total_enriched=enriched_count)
            await enriched_queue.put(None)
        log.info("parse_enrich_consumer.finished", total_enriched=enriched_count, sentinel_received=sentinel_received)

    async def _save_consumer(self, queue: asyncio.Queue, collector: EnrichCollector) -> None:
        log.info("save_consumer.starting")
        enriched_chunks_passed = 0

        while True:
            chunk = await queue.get()
            if chunk is None:
                log.info("save_consumer.received sentinel")
                break

            enriched_chunks_passed += 1
            log.debug("save_consumer.get_chunk", count=enriched_chunks_passed, chunk_id=chunk.id, file_path=chunk.file_path)
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
