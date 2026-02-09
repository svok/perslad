from ingestor.app.scanner.file_event import FileEvent
from ingestor.app.scanner.stages.processor_stage import ProcessorStage
from typing import List

from ingestor.app.pipeline.parse import ParseStage as ParseStageImpl
from ingestor.app.pipeline.scan import ScannedFile
from ingestor.core.models.chunk import Chunk


class ParseProcessorStage(ProcessorStage):
    def __init__(self, max_workers: int = 4):
        super().__init__("parse", max_workers)
        self.parser = ParseStageImpl()

    async def process(self, event: FileEvent) -> List[Chunk]:
        # 1. Защита от пустых путей
        if not event.abs_path or not event.abs_path.exists():
            self.log.warning(f"[{self.name}] File not found: {event.path}")
            return []

        # 2. Вызываем парсинг
        try:
            # parser.run ожидает List[ScannedFile], возвращает List[Chunk]
            chunks = await self._parse_one(event)

            # ПРОВЕРКА: Если чанки пустые или контент пустой - логируем
            if not chunks:
                self.log.warning(f"[{self.name}] No chunks generated for {event.path}")
            elif any(not c.content.strip() for c in chunks):
                self.log.error(f"[{self.name}] EMPTY CONTENT in chunks for {event.path}")

            return chunks
        except Exception as e:
            self.log.error(f"[{self.name}] Critical parse error: {e}", exc_info=True)
            return []

    async def _parse_one(self, event: FileEvent) -> List[Chunk]:
        scanned = ScannedFile(
            path=str(event.abs_path),
            relative_path=str(event.path),
            size_bytes=event.abs_path.stat().st_size,
            extension=event.abs_path.suffix
        )
        # ВНИМАНИЕ: Проверь, что ParseStageImpl.run реально читает файл!
        chunks = await self.parser.run([scanned]) or []

        for c in chunks:
            # Убеждаемся, что путь проброшен
            c._abs_path = event.abs_path
            if not c.file_path:
                c.file_path = str(event.path)
        return chunks
