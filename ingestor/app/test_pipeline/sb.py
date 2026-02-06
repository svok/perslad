from pathlib import Path

from .source import ISource
import asyncio
import logging

from ..scanner.queues import ThrottledQueue
from ..scanner.file_event import FileEvent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SourceSB(ISource):
    def __init__(self, queue: ThrottledQueue[FileEvent], name: str = "SB", message_template: str = "msg-b"):
        self._queue: ThrottledQueue[FileEvent] = queue
        self._name = name
        self._message_template = message_template
        self._counter = 0
        self._running = True

    async def start(self) -> None:
        logger.info(f"{self._name}: Starting with counter={self._counter}")
        count = 0
        while self._running and count < 20:
            await asyncio.sleep(1.5)
            path = Path(f"{self._message_template}-{self._counter}.txt")
            event_type: FileEvent.EventTypes = "modify"
            file_event = FileEvent(path=path, event_type=event_type)
            logger.info(f"{self._name}: Sending {file_event}, counter={self._counter}")
            await self._queue.put(file_event)
            self._counter += 1
            count += 1

    async def stop(self) -> None:
        self._running = False

    async def send(self, message: str) -> None:
        path = Path(f"{message}-{self._counter}.txt")
        event_type: FileEvent.EventTypes = "modify"
        file_event = FileEvent(path=path, event_type=event_type)
        await self._queue.put(file_event)
        logger.info(f"{self._name}: Sent {path}")

    async def put(self, item) -> None:
        await self._queue.put(item)
