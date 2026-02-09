import asyncio
from ingestor.app.scanner.file_event import FileEvent
from ingestor.app.scanner.stages.processor_stage import ProcessorStage
from typing import List

from ingestor.app.pipeline.parse import ParseStage as ParseStageImpl
from ingestor.app.pipeline.scan import ScannedFile
from ingestor.app.storage import Chunk


class ParseProcessorStage(ProcessorStage):
    def __init__(self, max_workers: int = 4, batch_size: int = 5):
        super().__init__("parse", max_workers)
        self.parser = ParseStageImpl()

    async def process(self, event: FileEvent) -> List[Chunk]:
        all_chunks = []

        tasks = []
        if event.abs_path and event.abs_path.exists():
            tasks = self._parse_one(event)

        if not tasks:
            return []

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, list):
                all_chunks.extend(result)
            elif isinstance(result, Exception):
                self.log.error(f"Parse error: {result}")

        self.log.info(f"[parse_stage] parsing file ({event.event_type}) {event.path} into chunks: {all_chunks}")
        return all_chunks

    async def _parse_one(self, event: FileEvent) -> List[Chunk]:
        scanned = ScannedFile(
            path=str(event.abs_path),
            relative_path=str(event.path),
            size_bytes=event.abs_path.stat().st_size,
            extension=event.abs_path.suffix
        )
        chunks = await self.parser.run([scanned]) or []
        for c in chunks:
            c._abs_path = event.abs_path
        return chunks
