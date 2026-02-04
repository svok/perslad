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
        while not self._stop_event.is_set():
            try:
                item = await self.input_queue.get()

                if item is None:
                    self.input_queue.task_done()
                    if wid == 0 and self.output_queue:
                        await self.output_queue.put(None)
                    break

                # Обрабатываем один элемент
                result = await self.process(item)

                if result is not None and self.output_queue:
                    await self.output_queue.put(result)

                self.input_queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception:
                self.log.error(f"Worker {wid} error", exc_info=True)
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
