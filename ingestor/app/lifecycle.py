import asyncio
import structlog

logger = structlog.get_logger("ingestor.lifecycle")


class IngestorService:
    def __init__(self):
        self._running = False

    async def start(self):
        logger.info("ingestor.starting")
        self._running = True

    async def stop(self):
        logger.info("ingestor.stopping")
        self._running = False

    async def run_forever(self):
        await self.start()

        try:
            while self._running:
                await asyncio.sleep(5)
        except asyncio.CancelledError:
            pass
        finally:
            await self.stop()
