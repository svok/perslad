from ingestor.core.models.chunk import Chunk
from ingestor.pipeline.base.processor_stage import ProcessorStage
from ingestor.pipeline.models.pipeline_file_context import PipelineFileContext
from ingestor.pipeline.utils.text_splitter_helper import TextSplitterHelper


class ParseProcessorStage(ProcessorStage):
    """
    Конвертация PipelineFileContext в объекты Chunk.
    Выполняет чтение файла и разбивку на чанки.
    """

    def __init__(self, max_workers: int = 4, text_splitter_helper: TextSplitterHelper = None):
        super().__init__("parse", max_workers)
        self.helper = text_splitter_helper or TextSplitterHelper()

    async def process(self, context: PipelineFileContext) -> PipelineFileContext:
        if not context.abs_path or not context.abs_path.exists():
            context.mark_skipped("file not found")
            return context

        try:
            raw_chunks = self.helper.chunk_file(
                file_path=str(context.abs_path),
                relative_path=str(context.file_path),
                extension=context.abs_path.suffix,
                text_splitter_helper=self.helper
            )

            if not raw_chunks:
                self.log.warning(f"No chunks generated for {context.file_path} (binary or empty)")
                context.has_errors = True
                context.errors.append("no chunks generated (binary or empty)")
                context.chunks = []
                return context

            # Маппинг в Chunk objects, фильтруем пустые
            chunks = [
                Chunk(
                    id=rc["id"],
                    file_path=str(context.file_path),
                    content=rc["content"],
                    start_line=rc.get("start_line", 0),
                    end_line=rc.get("end_line", 0),
                    chunk_type=rc["chunk_type"],
                    metadata=rc["metadata"],
                )
                for rc in raw_chunks
                if rc.get("content", "").strip()
            ]

            if len(chunks) < len(raw_chunks):
                self.log.warning(f"Some chunks had EMPTY CONTENT for {context.file_path}")

            if not chunks:
                context.has_errors = True
                context.errors.append("all chunks empty")
                context.chunks = []
                return context

            context.chunks = chunks
            context.mark_success()
            return context

        except Exception as e:
            self.log.error(f"Critical parse error for {context.file_path}: {e}", exc_info=True)
            context.has_errors = True
            context.errors.append(f"parse error: {str(e)}")
            context.chunks = []
            return context
