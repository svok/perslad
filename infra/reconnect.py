import asyncio
import random
from collections.abc import Awaitable, Callable

from .logger import get_logger

log = get_logger("infra.reconnect")


async def retry_forever(
        fn: Callable[[], Awaitable[None]],
        base_delay: float = 1.0,
        max_delay: float = 30.0,
) -> None:
    delay = base_delay

    while True:
        try:
            await fn()
            return
        except Exception as e:
            log.warning(
                "reconnect.failed",
                error=str(e),
                next_delay=delay,
            )
            await asyncio.sleep(delay)
            delay = min(delay * 2, max_delay)
            delay = delay * (0.8 + random.random() * 0.4)  # jitter
