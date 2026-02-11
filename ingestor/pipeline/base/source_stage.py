from abc import abstractmethod, ABC
from typing import Any, AsyncGenerator, Optional
import asyncio

from infra.logger import get_logger
from ingestor.pipeline.indexation.queues import ThrottledQueue


class SourceStage(ABC):
    """Базовая стадия-источник данных"""

    def __init__(self, name: str):
        self.name = name
        self.log = get_logger(f'ingestor.scanner.{self.__class__.__name__}')
        self._stop_event = asyncio.Event()  # ← ДОБАВИТЬ
        self._task: Optional[asyncio.Task] = None
        self.output_queue: Optional[ThrottledQueue] = None

    async def start(self, output_queue: ThrottledQueue) -> None:
        self.output_queue = output_queue
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name=f"{self.name}_source")

    async def _run(self) -> None:
        self.log.info(f"[{self.name}] SourceStage._run() ENTER")
        count = 0
        try:
            async for item in self.generate():
                count += 1
                if self._stop_event.is_set():
                    break
                print("PUT")
                await self.output_queue.put(item)
        except asyncio.CancelledError:
            self.log.info(f"[{self.name}] CancelledError")
            raise
        except Exception as e:
            self.log.error(f"[{self.name}] Exception: {e}", exc_info=True)
            raise
        finally:
            self.log.info(f"[{self.name}] SourceStage._run() FINALLY, total: {count}")

    async def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def wait(self):
        if self._task:
            try:
                await self._task
            finally:
                self._task = None # Теперь is_running вернет False

    @abstractmethod
    async def generate(self) -> AsyncGenerator[Any, None]:
        if False:  # Никогда не выполнится, но делает метод генератором
            # noinspection PyUnreachableCode
            yield
        return

    async def stop(self) -> None:
        """Останавливает генерацию"""
        self.log.info(f"[{self.name}] Stopping")
        self._stop_event.set()
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        self.log.info(f"[{self.name}] Stopped")
