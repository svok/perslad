import asyncio
from abc import ABC
from typing import Optional

from infra.logger import get_logger


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
