"""
Collector for enriching chunks.
"""

import asyncio
import time
from infra.logger import get_logger
from ingestor.core.models.chunk import Chunk
from ingestor.core.ports.storage import BaseStorage

log = get_logger("ingestor.pipeline.collector")

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
