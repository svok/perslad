import asyncio
from typing import List

from ingestor.app.scanner.queues import ThrottledQueue
from ingestor.app.scanner.stages.processor_stage import ProcessorStage
from ingestor.app.storage import Chunk


class BatchCollectorStage(ProcessorStage):
    """Собирает чанки от нескольких файлов в батч"""

    def __init__(self, batch_size: int = 10, max_wait: float = 0.5):
        super().__init__("batch_collector", max_workers=1)
        self.batch_size = batch_size
        self.max_wait = max_wait
        self._buffer: List[List[Chunk]] = []
        self._lock = asyncio.Lock()
        self._flush_event = asyncio.Event()

    async def start(self, input_queue: ThrottledQueue, output_queue: ThrottledQueue) -> None:
        self.input_queue = input_queue
        self.output_queue = output_queue
        self._stop_event.clear()
        # Два таска: collector и flusher
        self._workers = [
            asyncio.create_task(self._collect_loop(), name="collector"),
            asyncio.create_task(self._flush_loop(), name="flusher"),
        ]

    async def _collect_loop(self):
        """Собирает чанки в буфер"""
        while not self._stop_event.is_set():
            try:
                item = await self.input_queue.get()

                if item is None:
                    async with self._lock:
                        if self._buffer:
                            await self._flush()
                    await self.output_queue.put(None)
                    break

                async with self._lock:
                    self._buffer.append(item)  # item = List[Chunk]
                    if len(self._buffer) >= self.batch_size:
                        self._flush_event.set()

                self.input_queue.task_done()

            except asyncio.CancelledError:
                break

    async def _flush_loop(self):
        """Периодически сливает буфер по таймауту"""
        while not self._stop_event.is_set():
            try:
                await asyncio.wait_for(self._flush_event.wait(), timeout=self.max_wait)
            except asyncio.TimeoutError:
                pass

            async with self._lock:
                if self._buffer:
                    await self._flush()
                self._flush_event.clear()

    async def _flush(self):
        """Сливает буфер в выходную очередь"""
        batch = self._buffer[:self.batch_size]
        self._buffer = self._buffer[self.batch_size:]
        # Отправляем батч как один элемент
        await self.output_queue.put(batch)  # List[List[Chunk]]

    async def stop(self):
        await super().stop()
