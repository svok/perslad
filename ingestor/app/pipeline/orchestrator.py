"""
Pipeline Orchestrator

Координирует выполнение всех stages.
Детерминированный, перезапускаемый, можно остановить в любой момент.
"""

import asyncio
import time

from infra.llm import LLMClient
from infra.logger import get_logger
from ingestor.adapters import BaseStorage
from ingestor.app.llm_lock import LLMLockManager
from ingestor.app.pipeline.embed import EmbedStage
from ingestor.app.pipeline.enrich import EnrichStage
from ingestor.app.pipeline.parse import ParseStage
from ingestor.app.pipeline.persist import PersistStage
from ingestor.app.pipeline.scan import ScanStage
from ingestor.app.storage import InMemoryStorage, Chunk

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
        storage: BaseStorage,
        embed_url: str = "http://emb:8001/v1",
        embed_api_key: str = "sk-dummy",
    ) -> None:
        self.workspace_path = workspace_path
        self.llm = llm
        self.lock_manager = lock_manager
        self.storage = storage

        # Инициализируем stages
        self.scan_stage = ScanStage(workspace_path)
        self.parse_stage = ParseStage()
        self.enrich_stage = EnrichStage(llm, lock_manager)

        # Embed stage
        self.embed_stage = EmbedStage(embed_url, embed_api_key)

        self.persist_stage = PersistStage(storage)

    class EnrichCollector:
        def __init__(self, storage: BaseStorage, max_buffer=100, debounce=1.0):
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
            await self.queue.put(chunk)
            async with self.lock:
                if self.timer is None:
                    self.timer = asyncio.create_task(self._flush())

        async def _flush(self):
            items_processed = 0
            while not self.queue.empty():
                try:
                    chunk = await asyncio.wait_for(self.queue.get(), timeout=self.debounce)
                    self.buffer.append(chunk)
                    self.queue.task_done()
                    items_processed += 1
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
            log.info("collector.waiting_done", total_added=self.total_added, buffer_len=len(self.buffer))
            await self.queue.join()
            log.info("collector.waiting_done.after_queue_join")
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
            embedded_queue = asyncio.Queue(maxsize=100)

            collector = self.EnrichCollector(self.storage, max_buffer=100, debounce=1.0)

            log.info("pipeline.tasks.created")

            scan_task = asyncio.create_task(self._scan_producer(files_queue))
            parse_enrich_task = asyncio.create_task(self._parse_enrich_consumer(files_queue, enriched_queue))
            embed_task = asyncio.create_task(self._embed_consumer(enriched_queue, embedded_queue))
            save_task = asyncio.create_task(self._save_consumer(embedded_queue, collector))

            log.info("pipeline.tasks.running")
            await scan_task
            log.info("pipeline.task.scan.complete")

            await parse_enrich_task
            log.info("pipeline.task.parse_enrich.complete")

            await embed_task
            log.info("pipeline.task.embed.complete")

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
                future.set_result(None)
            except Exception as e:
                future.set_exception(e)

        asyncio.create_task(put_with_callback())
        await future
        log.info("scan_producer.all_files_sent")

        log.info("scan_producer.preparing_sentinel")
        await files_queue.put(None)
        log.info("scan_producer.sentinel_sent")

    async def _parse_enrich_consumer(self, files_queue: asyncio.Queue, enriched_queue: asyncio.Queue) -> None:
        log.info("parse_enrich_consumer.starting")
        enriched_count = 0
        sentinel_received = False
        files_processed = 0

        while True:
            log.info("parse_enrich_consumer.waiting_for_file")
            file = await files_queue.get()

            files_processed += 1
            log.info("parse_enrich_consumer.received_file", file_name=file.relative_path if hasattr(file, 'relative_path') else file[:50], files_processed=files_processed)
            if file is None:
                sentinel_received = True
                log.info("parse_enrich_consumer.received_sentinel")
                break

            # Parse single file (expects a list, so wrap it)
            chunks = await self.parse_stage.run([file])

            if not chunks:
                continue

            enriched = await self.enrich_stage.run(chunks)
            enriched_count += len(enriched)

            for i, chunk in enumerate(enriched):
                await enriched_queue.put(chunk)

        # Отправляем sentinel в enriched_queue после обработки всех files
        if sentinel_received:
            log.info("parse_enrich_consumer.send_enriched_sentinel", total_enriched=enriched_count)
            await enriched_queue.put(None)
        log.info("parse_enrich_consumer.finished", total_enriched=enriched_count, sentinel_received=sentinel_received, files_processed=files_processed)

    async def _embed_consumer(self, enriched_queue: asyncio.Queue, embedded_queue: asyncio.Queue) -> None:
        log.info("embed_consumer.starting")
        if not self.embed_stage:
            log.warning("embed_stage.not_configured, skipping embeddings")
            # Pass all chunks through as None sentinel
            while True:
                chunk = await enriched_queue.get()
                await embedded_queue.put(chunk)
                if chunk is None:
                    break
            return

        embedded_count = 0
        total_enriched = 0

        while True:
            chunk = await enriched_queue.get()
            if chunk is None:
                log.info("embed_consumer.received_sentinel", total_enriched=total_enriched)
                break

            total_enriched += 1

            try:
                log.info("embed_consumer.processing", chunk_id=chunk.id[:20], file_path=chunk.file_path[:50] if chunk.file_path else None)
                # Apply embeddings (embed_stage.run doesn't actually return enriched chunks, it modifies them in-place)
                await self.embed_stage.run([chunk])
                embedded_count += 1
                log.info("embed_consumer.embedded", chunk_id=chunk.id[:20], embedded=embedded_count)
            except Exception as e:
                log.error("embed_consumer.embedding_failed", chunk_id=chunk.id[:20], error=str(e))
                # Still pass through the chunk even if embedding fails
                embedded_count += 1

            await embedded_queue.put(chunk)

        log.info("embed_consumer.finished", embedded=embedded_count, total_enriched=total_enriched)

    async def _save_consumer(self, queue: asyncio.Queue, collector: EnrichCollector) -> None:
        log.info("save_consumer.starting")
        enriched_chunks_passed = 0
        chunks_sent = 0

        while True:
            chunk = await queue.get()
            if chunk is None:
                log.info("save_consumer.received sentinel")
                break

            enriched_chunks_passed += 1
            await collector.add(chunk)
            chunks_sent += 1

        log.info("save_consumer.finished", enriched_chunks_passed=enriched_chunks_passed, chunks_sent=chunks_sent)
        await collector.wait_done()

    async def run_incremental(self, file_paths: list[str]) -> None:
        """
        Инкрементальная индексация конкретных файлов.
        Для будущего использования (file watcher, CI).
        """
        log.info("pipeline.incremental.start", files_count=len(file_paths))
        # TODO: implement incremental indexing
        log.warning("pipeline.incremental.not_implemented")
