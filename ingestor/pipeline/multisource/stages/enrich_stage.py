from pathlib import Path
from typing import Optional
import asyncio

from ingestor.pipeline.multisource.file_event import FileEvent
from ingestor.pipeline.multisource.stages.processor_stage import ProcessorStage


class EnrichStage(ProcessorStage):
    def __init__(self, workspace_path: Path, max_workers: int = 2):
        super().__init__("enrich", max_workers)
        self.workspace_path = Path(workspace_path)

    async def process(self, event: FileEvent) -> Optional[FileEvent]:
        if not event.abs_path or not event.abs_path.exists():
            return None

        self.log.info(f"[enrich_stage] enriching file ({event.event_type}) {event.path}")

        try:
            stat = await asyncio.to_thread(event.abs_path.stat)
        except Exception as e:
            self.log.critical("stat() FAILED: %s", event.path, exc_info=True)
            return None

        event._size = stat.st_size
        event._mtime = stat.st_mtime
        return event