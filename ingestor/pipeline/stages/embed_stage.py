from typing import List

from ingestor.adapters.embedding_model import EmbeddingModel
from ingestor.core.models.chunk import Chunk
from ingestor.pipeline.base.processor_stage import ProcessorStage


class EmbedChunksStage(ProcessorStage):
    """
    Класс-обертка для интеграции в пайплайн.
    """
    def __init__(self, embed_model: EmbeddingModel, max_workers: int = 2):
        super().__init__("embed", max_workers)
        self.embed_model = embed_model
        # Создаем клиент только если нет готовой модели

    async def process(self, chunks: List[Chunk]) -> List[Chunk]:
        # Если передана модель (например, Mock или EmbeddingModel адаптер), используем её
        return await self.embed_model.run(chunks)
