from ingestor.adapters.embedding_model import EmbeddingModel
from ingestor.pipeline.base.processor_stage import ProcessorStage
from ingestor.pipeline.models.pipeline_file_context import PipelineFileContext


class EmbedChunksStage(ProcessorStage):
    """
    Класс-обертка для интеграции в пайплайн.
    """

    def __init__(self, embed_model: EmbeddingModel, max_workers: int = 2):
        super().__init__("embed", max_workers)
        self.embed_model = embed_model

    async def process(self, context: PipelineFileContext) -> PipelineFileContext:
        # Пропускаем skipped или пустые
        if context.status != "success" or not context.chunks:
            return context
        
        # Генерация embeddings (возвращает новый список или изменяет)
        context.chunks = await self.embed_model.run(context.chunks)
        return context
