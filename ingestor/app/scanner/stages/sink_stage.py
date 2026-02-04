import asyncio
from abc import abstractmethod
from typing import Optional, Any

from ingestor.app.scanner.queues import ThrottledQueue
from ingestor.app.scanner.stages.base_stage import BaseStage


class SinkStage(BaseStage):
    def __init__(self, name: str, max_workers: int = 1):
        super().__init__(name)
        self.max_workers = max(max_workers, 1)
        self._workers: list[asyncio.Task] = []
        self.input_queue: Optional[ThrottledQueue] = None

    async def start(self, input_queue: ThrottledQueue) -> None:
        self.input_queue = input_queue
        self._stop_event.clear()
        self._workers = [
            asyncio.create_task(self._worker_loop(i), name=f"{self.name}_w{i}")
            for i in range(self.max_workers)
        ]

    async def _worker_loop(self, wid: int) -> None:
        while not self._stop_event.is_set():
            try:
                item = await self.input_queue.get()
                if item is None:
                    self.input_queue.task_done()
                    break
                await self.consume(item)
                self.input_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception:
                self.log.error(f"Sink worker {wid} error", exc_info=True)
                raise

    @abstractmethod
    async def consume(self, item: Any) -> None:
        pass

    async def stop(self) -> None:
        await super().stop()
        await asyncio.gather(*self._workers, return_exceptions=True)
