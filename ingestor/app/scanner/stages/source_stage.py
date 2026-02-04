from abc import abstractmethod
from typing import Any, AsyncGenerator, Optional
import asyncio

from infra.logger import get_logger
from ingestor.app.scanner.queues import ThrottledQueue


class SourceStage:
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
        try:
            async for item in self.generate():
                self.log.info(f"[{self.name}] Got item from generate(): {item}")
                if self._stop_event.is_set():
                    self.log.info(f"[{self.name}] Stop event, breaking")
                    break
                self.log.info(f"[{self.name}] Putting to queue...")
                await self.output_queue.put(item)
                self.log.info(f"[{self.name}] Put done")
        except asyncio.CancelledError:
            self.log.info(f"[{self.name}] CancelledError")
            raise
        except Exception as e:
            self.log.error(f"[{self.name}] Exception: {e}", exc_info=True)
            raise
        finally:
            self.log.info(f"[{self.name}] SourceStage._run() FINALLY")

    @abstractmethod
    async def generate(self) -> AsyncGenerator[Any, None]:
        pass

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
        self.log.info(f"[{self.name}] Stopped")
