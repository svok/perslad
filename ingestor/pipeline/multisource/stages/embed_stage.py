from typing import List

from ingestor.pipeline.impl.embed import EmbedStage
from ingestor.pipeline.multisource.stages.processor_stage import ProcessorStage
from ingestor.core.models.chunk import Chunk


class EmbedChunksStage(ProcessorStage):
    """
    Класс-обертка для интеграции в пайплайн.
    """
    def __init__(self, embed_url: str, embed_api_key: str, max_workers: int = 2):
        super().__init__("embed", max_workers)
        self.embedder = EmbedStage(embed_url, embed_api_key)

    async def process(self, chunks: List[Chunk]) -> List[Chunk]:
        # Воркер вызывает этот метод для каждого сообщения из очереди
        return await self.embedder.run(chunks)

    async def stop(self) -> None:
        # Переопределяем stop, чтобы закрыть соединения
        await self.embedder.close()
        await super().stop()
