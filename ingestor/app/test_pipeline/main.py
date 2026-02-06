from ingestor.app.scanner.queues import ThrottledQueue
from .handler import Handler
from .sa import SourceSA
from .sb import SourceSB
from .sink import ISink
import asyncio
import logging

from ..scanner.file_event import FileEvent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class StdoutSink(ISink):
    async def process(self, file_event: FileEvent) -> None:
        print(f"[{file_event.event_type}] {file_event.path}")


async def main():
    sink = StdoutSink()
    handler = Handler(sink)

    source_queue = ThrottledQueue(name="source_queue")
    target_queue = ThrottledQueue(name="target_queue")

    logger.info("Setting up handler")
    await handler.set_queues(source_queue, target_queue)

    logger.info("Starting SA source")
    sa_task = asyncio.create_task(start_sa(source_queue, "msg-a1"))

    await asyncio.sleep(5)

    logger.info("Starting SB source")
    sb_task = asyncio.create_task(start_sb(source_queue, "msg-b1"))

    await asyncio.sleep(5)

    logger.info("Removing SB source")
    await handler.remove_source("SB")
    await sb_task
    logger.info("SB task finished")

    logger.info("Starting new SA source")
    new_sa_task = asyncio.create_task(start_sa(source_queue, "msg-a2"))

    await asyncio.sleep(5)

    logger.info("Restarting SA source")
    await new_sa_task
    logger.info("New SA task finished")

    logger.info("Removing SA source")
    await handler.remove_source("SA")
    await new_sa_task

    logger.info("Stopping handler")
    await handler.stop()

    logger.info("Test completed")


async def start_sa(queue: ThrottledQueue[FileEvent], message_template="msg-a") -> None:
    source = SourceSA(queue, name="SA", message_template=message_template)
    await source.start()


async def start_sb(queue: ThrottledQueue[FileEvent], message_template="msg-b") -> None:
    source = SourceSB(queue, name="SB", message_template=message_template)
    await source.start()


if __name__ == "__main__":
    asyncio.run(main())
