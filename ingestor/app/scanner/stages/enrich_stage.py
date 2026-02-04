from pathlib import Path
from typing import Optional

from ingestor.app.scanner.file_event import FileEvent
from ingestor.app.scanner.stages.processor_stage import ProcessorStage


class EnrichStage(ProcessorStage):
    def __init__(self, workspace_path: Path, max_workers: int = 2):
        super().__init__("enrich", max_workers, batch_size=1, output_is_batch=False)
        self.workspace_path = Path(workspace_path)

    async def process(self, event: FileEvent) -> Optional[FileEvent]:
        if not event.abs_path or not event.abs_path.exists():
            return None

        stat = event.abs_path.stat()
        event._size = stat.st_size
        event._mtime = stat.st_mtime

        return event