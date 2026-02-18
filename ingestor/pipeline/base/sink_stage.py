import asyncio
from abc import abstractmethod
from typing import Optional, Any

from ingestor.pipeline.base.queues import ThrottledQueue
from ingestor.pipeline.base.base_stage import BaseStage


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
        count = 0
        while not self._stop_event.is_set():
            try:
                count += 1
                self.log.debug(f"[{self.name}] Worker {wid}: calling get()...")
                item = await self.input_queue.get()
                self.log.info(f"[{self.name}] Worker {wid}: received item #{count}: {type(item).__name__}")

                if item is None:
                    self.log.info(f"[{self.name}] Worker {wid}: received poison pill, will break")
                    continue

                self.log.debug(f"[{self.name}] Worker {wid}: calling consume()...")
                await self.consume(item)
                self.log.debug(f"[{self.name}] Worker {wid}: consume() completed")

            except asyncio.CancelledError:
                self.log.debug(f"[{self.name}] Worker {wid}: received CancelledError")
                break
            except Exception:
                self.log.error(f"Sink worker {wid} error", exc_info=True)
                raise
            finally:
                self.input_queue.task_done()
                self.log.debug(f"[{self.name}] Worker {wid}: task_done() called")


    @abstractmethod
    async def consume(self, item: Any) -> None:
        pass

    async def stop(self) -> None:
        await super().stop()
        await asyncio.gather(*self._workers, return_exceptions=True)
