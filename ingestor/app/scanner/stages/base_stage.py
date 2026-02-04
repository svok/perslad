from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Optional
import asyncio

from infra.logger import get_logger
from ingestor.app.scanner.queues import ThrottledQueue


class BaseStage(ABC):
    def __init__(self, name: str):
        self.name = name
        self.log = get_logger(f'ingestor.scanner.{name}')
        self._stop_event = asyncio.Event()
        self._task: Optional[asyncio.Task] = None

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
