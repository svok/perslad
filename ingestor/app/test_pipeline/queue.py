from typing import Optional, TypeVar
from abc import ABC, abstractmethod
import asyncio


T = TypeVar('T')


class IQueue(ABC):
    @abstractmethod
    async def put(self, item: T) -> None:
        pass

    @abstractmethod
    async def get(self) -> T:
        pass


class QueueAdapter(IQueue):
    def __init__(self, name: Optional[str] = None, _queue=None):
        self.name = name if name is not None else str(id(self))
        self._queue = _queue if _queue is not None else asyncio.Queue()

    async def put(self, item: T) -> None:
        await self._queue.put(item)

    async def get(self) -> T:
        return await self._queue.get()
