from typing import List, Optional

from ingestor.app.pipeline.embed import EmbedStage as EmbedStageImpl
from ingestor.app.scanner.stages.processor_stage import ProcessorStage
from ingestor.app.storage import Chunk


class EmbedChunksStage(ProcessorStage):
    def __init__(self, embed_url: str, embed_api_key: str, max_workers: int = 2):
        super().__init__("embed", max_workers)
        self.embedder = EmbedStageImpl(embed_url, embed_api_key)

    async def process(self, chunks: List[Chunk]) -> List[Chunk]:
        return await self.embedder.run(chunks)
