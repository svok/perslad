from abc import ABC, abstractmethod


class ISource(ABC):
    @abstractmethod
    async def start(self) -> None:
        pass

    @abstractmethod
    async def stop(self) -> None:
        pass

    @abstractmethod
    async def send(self, message: str) -> None:
        pass

    @abstractmethod
    async def put(self, item) -> None:
        pass
