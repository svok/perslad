import asyncio
from pathlib import Path

from ingestor.pipeline.base.processor_stage import ProcessorStage
from ingestor.pipeline.models.context import PipelineFileContext


class EnrichStage(ProcessorStage):
    def __init__(self, workspace_path: Path, max_workers: int = 2):
        super().__init__("enrich", max_workers)
        self.workspace_path = Path(workspace_path).resolve()

    async def process(self, context: PipelineFileContext) -> PipelineFileContext:
        if not context.abs_path or not context.abs_path.exists():
            context.mark_skipped("file not found")
            return context

        self.log.info(f"[enrich_stage] enriching file ({context.event_type}) {context.file_path}")

        try:
            stat = await asyncio.to_thread(context.abs_path.stat)
            context.size = stat.st_size
            context.mtime = stat.st_mtime
            return context
        except Exception as e:
            self.log.critical("stat() FAILED: %s", context.file_path, exc_info=True)
            context.mark_error(f"stat failed: {e}")
            return context