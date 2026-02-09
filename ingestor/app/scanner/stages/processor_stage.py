import asyncio
from abc import abstractmethod
from typing import Optional, Any

from ingestor.app.scanner.queues import ThrottledQueue
from ingestor.app.scanner.stages.base_stage import BaseStage


class ProcessorStage(BaseStage):
    """Обработчик: один элемент → один результат, структура сохраняется"""

    def __init__(self, name: str, max_workers: int = 1):
        super().__init__(name)
        self.max_workers = max(max_workers, 1)
        self._workers: list[asyncio.Task] = []
        self.input_queue: Optional[ThrottledQueue] = None
        self.output_queue: Optional[ThrottledQueue] = None

    async def start(self, input_queue: ThrottledQueue, output_queue: Optional[ThrottledQueue] = None) -> None:
        self.input_queue = input_queue
        self.output_queue = output_queue
        self._stop_event.clear()
        self._workers = [
            asyncio.create_task(self._worker_loop(i), name=f"{self.name}_w{i}")
            for i in range(self.max_workers)
        ]

    async def _worker_loop(self, wid: int) -> None:
        """Просто: взял → обработал → положил. Без батчинга."""
        self.log.info(f"[{self.name}] Worker {wid} started")
        count = 0
        while not self._stop_event.is_set():
            try:
                count += 1
                item = await self.input_queue.get()
                print("GOT ITEM")

                try:
                    result = await self.process(item)
                    if result is not None and self.output_queue:
                        await self.output_queue.put(result)
                except Exception:
                    self.log.critical(f"[{self.name}] Worker {wid} exception")
                    raise
                finally:
                    self.input_queue.task_done()
                    self.log.debug(f"[{self.name}] Worker {wid} finished handling")


                await asyncio.sleep(0)  # ← ВАЖНО

            except asyncio.CancelledError:
                self.log.info(f"[{self.name}] Worker {wid}: cancelled")
                break
            except BaseException as e:
                self.log.critical(f"[{self.name}] Worker {wid} crashed")
                raise

    async def process(self, item: Any) -> Any:
        """
        Обработка одного элемента.
        Должна быть реализована в подклассе.
        """
        raise NotImplementedError(f"{self.__class__.__name__}.process() not implemented")

    async def stop(self) -> None:
        await super().stop()
        for w in self._workers:
            if not w.done():
                w.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
