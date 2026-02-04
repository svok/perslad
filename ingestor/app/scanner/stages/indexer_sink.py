from typing import List

from ingestor.app.scanner.stages.sink_stage import SinkStage
from ingestor.app.storage import Chunk


class IndexerSinkStage(SinkStage):
    def __init__(self, max_workers: int = 1):
        super().__init__("indexer_sink", max_workers)

    async def consume(self, chunks: List[Chunk]) -> None:
        if chunks:
            self.log.info(f"Completed: {chunks[0].file_path} ({len(chunks)} chunks)")
