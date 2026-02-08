from abc import ABC, abstractmethod
from ..scanner.file_event import FileEvent


class ISink(ABC):
    @abstractmethod
    async def process(self) -> None:
        pass
