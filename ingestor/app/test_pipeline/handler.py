from abc import ABC, abstractmethod
from typing import Optional

from .sink import ISink
import asyncio
import logging

from ..scanner.queues import ThrottledQueue
from ..scanner.file_event import FileEvent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IQueueProcessor(ABC):
    @abstractmethod
    async def start(self) -> None:
        pass

    @abstractmethod
    async def stop(self) -> None:
        pass


class Handler(IQueueProcessor):
    def __init__(self, sink: ISink, name: str = "Handler"):
        self._sink = sink
        self._name = name
        self._source_queue: Optional[ThrottledQueue[FileEvent]] = None
        self._sink_queue: Optional[ThrottledQueue[FileEvent]] = None
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        logger.info(f"{self._name}: Handler started")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info(f"{self._name}: Handler stopped")

    async def set_queues(self, source_queue: ThrottledQueue[FileEvent], sink_queue: ThrottledQueue[FileEvent]) -> None:
        logger.info(f"{self._name}: Setting up queues")
        self._source_queue = source_queue
        self._sink_queue = sink_queue
        self._task = asyncio.create_task(self._process_queue())
        logger.info(f"{self._name}: Queue processing started")

    async def remove_source(self, name: str) -> None:
        logger.info(f"{self._name}: Source {name} removed")

    async def _process_queue(self) -> None:
        logger.info(f"{self._name}: Processing loop started")
        while True:
            try:
                file_event = await self._source_queue.get()
                logger.info(f"{self._name}: Got file event from source: {file_event.path} ({file_event.event_type})")
                await self._sink.process(file_event)
                logger.info(f"{self._name}: File event processed and sent to sink")
            except asyncio.CancelledError:
                logger.info(f"{self._name}: Processing cancelled")
                break
        logger.info(f"{self._name}: Processing loop finished")
