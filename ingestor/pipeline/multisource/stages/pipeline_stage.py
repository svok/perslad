from abc import ABC, abstractmethod
from typing import Optional, Any, List
import asyncio

from infra.logger import get_logger
from ingestor.pipeline.multisource.queues import ThrottledQueue


class PipelineStage(ABC):
    """Базовая стадия конвейера"""

    def __init__(self, name: str, max_workers: int = 1):
        self.log = get_logger(f'ingestor.scanner.{self.__class__.__name__}')
        if max_workers < 1:
            raise ValueError("max_workers must be at least 1")
        self.name = name
        self.max_workers = max_workers
        self._workers: List[asyncio.Task] = []
        self._stop_event = asyncio.Event()

    @abstractmethod
    async def process(self, item: Any) -> Optional[Any]:
        """Обрабатывает один элемент"""
        pass

    async def start(self,
                    input_queue: Optional[ThrottledQueue] = None,
                    output_queue: Optional[ThrottledQueue] = None) -> None:
        """Запускает воркеры стадии"""
        self.input_queue = input_queue
        self.output_queue = output_queue

        self._stop_event.clear()
        self._workers = [
            asyncio.create_task(
                self._worker_loop(i),
                name=f"{self.name}_worker_{i}"
            )
            for i in range(self.max_workers)
        ]

    async def _worker_loop(self, worker_id: int) -> None:
        """Цикл обработки для одного воркера"""
        while not self._stop_event.is_set():
            try:
                item = await self.input_queue.get()

                if item is None:
                    # Сигнал завершения
                    if self.output_queue:
                        await self.output_queue.put(None)
                    self.input_queue.task_done()
                    break

                result = await self.process(item)

                if result is not None and self.output_queue:
                    await self.output_queue.put(result)

                self.input_queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.log.error(f"Error in {self.name} worker {worker_id}", exc_info=True)
                raise

    async def stop(self) -> None:
        """Останавливает стадию"""
        self._stop_event.set()

        for worker in self._workers:
            if not worker.done():
                worker.cancel()

        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
