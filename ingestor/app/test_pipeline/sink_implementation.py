from .sink import ISink
import logging

from ..scanner.file_event import FileEvent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Sink(ISink):
    def __init__(self, name: str = "Sink"):
        self._name = name

    async def process(self, message: FileEvent) -> None:
        logger.info(f"{self._name}: Processed {message.event_type} from {message.path}")
