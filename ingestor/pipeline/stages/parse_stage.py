from typing import List
from ingestor.core.models.chunk import Chunk
from ingestor.pipeline.utils.text_splitter_helper import TextSplitterHelper
from ingestor.pipeline.models.file_event import FileEvent
from ingestor.pipeline.base.processor_stage import ProcessorStage

class ParseProcessorStage(ProcessorStage):
    """
    Прямая конвертация из raw_chunks в объекты Chunk.
    """
    def __init__(self, max_workers: int = 4, text_splitter_helper: TextSplitterHelper = None):
        super().__init__("parse", max_workers)
        self.helper = text_splitter_helper or TextSplitterHelper()

    async def process(self, event: FileEvent) -> List[Chunk]:
        if not event.abs_path or not event.abs_path.exists():
            self.log.warning(f"File not found: {event.path}")
            return []

        try:
            # Прямой вызов хелпера без промежуточных ScannedFile (если хелпер позволяет)
            raw_chunks = self.helper.chunk_file(
                file_path=str(event.abs_path),
                relative_path=str(event.path),
                extension=event.abs_path.suffix,
                text_splitter_helper=self.helper
            )

            if not raw_chunks:
                self.log.warning(f"No chunks generated for {event.path}")
                return []

            # Быстрый маппинг через list comprehension
            chunks = [
                Chunk(
                    id=rc["id"],
                    file_path=rc.get("file_path", str(event.path)),
                    content=rc["content"],
                    start_line=rc.get("start_line", 0),
                    end_line=rc.get("end_line", 0),
                    chunk_type=rc["chunk_type"],
                    metadata=rc["metadata"],
                )
                for rc in raw_chunks if rc.get("content", "").strip()
            ]

            if len(chunks) < len(raw_chunks):
                self.log.error(f"Some chunks had EMPTY CONTENT for {event.path}")

            return chunks

        except Exception as e:
            self.log.error(f"Critical parse error for {event.path}: {e}", exc_info=True)
            return []
