from ingestor.adapters import BaseStorage
from ingestor.pipeline.base.processor_stage import ProcessorStage
from ingestor.pipeline.models.context import PipelineFileContext


class PersistChunksStage(ProcessorStage):
    def __init__(self, storage: BaseStorage, max_workers: int = 2):
        super().__init__("persist", max_workers)
        self.storage = storage

    async def process(self, context: PipelineFileContext) -> PipelineFileContext:
        # Если есть ошибки или чанки пустые - удаляем старые
        if context.has_errors or not context.chunks:
            # Удаляем старые чанки, так как файл битый или пустой
            # Используем file_path как ключ (внешний ключ удалит связь, но здесь мы чистим чанки)
            # Важно: если мы удаляем summary, чанки удалятся каскадно. 
            # Но PersistStage отвечает за чанки. Безопаснее удалить чанки явно или положиться на FileSummaryStage?
            # Лучше удалить явно для идемпотентности, но если мы полагаемся на FK, то достаточно удалить summary.
            # ОДНАКО, PersistStage идет ДО FileSummaryStage.
            # Если мы тут не удалим, а FileSummaryStage удалит summary (или обновит его), что будет с чанками?
            # Если FileSummaryStage удалит summary -> FK удалит чанки.
            # Если FileSummaryStage ОБНОВИТ summary (с ошибкой), то старый summary останется?
            # Нет, summary обновляется по PK.
            # Поэтому чанки останутся, если их явно не удалить.
            # Значит, нужно удалить чанки здесь.
            
            await self.storage.delete_chunks_by_file_paths([str(context.file_path)])
            return context
        
        # Сохраняем новые чанки
        # Сначала удалим старые (чтобы не было дублей при изменении разбивки)
        # Хотя save_chunks делает upsert, но если изменились ID чанков (сдвиг строк), старые могут остаться.
        # Поэтому clean insert лучше.
        await self.storage.delete_chunks_by_file_paths([str(context.file_path)])
        await self.storage.save_chunks(context.chunks)
        
        return context
