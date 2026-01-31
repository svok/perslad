import asyncio
from typing import Callable


class HealthFlag:
    def __init__(self) -> None:
        self._ready = asyncio.Event()

    def set_ready(self) -> None:
        self._ready.set()

    def set_not_ready(self) -> None:
        self._ready.clear()

    async def wait_ready(self, timeout: float | None = None) -> bool:
        try:
            await asyncio.wait_for(self._ready.wait(), timeout)
            return True
        except asyncio.TimeoutError:
            return False
