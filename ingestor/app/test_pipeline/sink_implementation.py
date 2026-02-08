import asyncio
from typing import Optional

from .sink import ISink
import logging

from ..scanner.file_event import FileEvent
from ..scanner.queues import ThrottledQueue

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Sink(ISink):
    def __init__(self, queue: ThrottledQueue[FileEvent], name: str = "Sink"):
        self._queue = queue
        self._name = name
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        self._task = asyncio.create_task(self.process())
        logger.info(f"{self._name}: Handler started queue processing")

    async def process(self) -> None:
        while True:
            try:
                message = await self._queue.get()
                logger.info(f"{self._name}: Sink processed: {message.event_type} from {message.path}, [out-queue size: {self._queue.qsize}")
            except asyncio.CancelledError:
                logger.info(f"{self._name}: Sink Processing cancelled")
                break
            finally:
                self._queue.task_done()
