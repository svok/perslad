import os
from pathlib import Path
from typing import AsyncGenerator

from infra.logger import get_logger
from ingestor.pipeline.multisource.file_event import FileEvent
from ingestor.pipeline.multisource.gitignore_checker import GitignoreChecker
from ingestor.pipeline.multisource.stages.source_stage import SourceStage


class ScannerSourceStage(SourceStage):
    def __init__(self, workspace_path: Path, max_workers: int = 2):
        super().__init__("scanner")
        self.workspace_path = Path(workspace_path).resolve()
        self.checker = GitignoreChecker(self.workspace_path)
        self.checker.load()
        self.log = get_logger('ingestor.scanner.ScannerSourceStage')
        self.log.info(f"[scanner] Initialized, workspace={workspace_path}")

    async def start(self, output_queue) -> None:
        self.log.info("[scanner] start() called")
        await super().start(output_queue)
        self.log.info("[scanner] super().start() completed")

    async def generate(self) -> AsyncGenerator[FileEvent, None]:
        try:
            if not self.workspace_path.exists():
                self.log.error("Path does not exist: %s", self.workspace_path)
                return

            self.log.info("Starting os.walk...")

            for root, dirs, files in os.walk(self.workspace_path):
                # Filter ignored directories
                filtered_dirs = [d for d in dirs
                    if not d.startswith('.') and d not in ('__pycache__', 'node_modules')
                    and not self.checker.should_ignore(Path(root) / d)]

                if filtered_dirs:
                    dirs[:] = filtered_dirs

                for filename in files:
                    file_path = Path(root) / filename

                    if self.checker.should_ignore(file_path):
                        continue

                    try:
                        rel_path = file_path.relative_to(self.workspace_path)
                    except ValueError:
                        continue

                    self.log.info(f"[scanner] File detected {rel_path}")
                    yield FileEvent(
                        path=rel_path,
                        event_type="scan",
                        abs_path=file_path
                    )

            self.log.info("Scan completed")
            return
        except Exception as e:
            self.log.error("Scan generation error: %s", e, exc_info=True)
            raise

    async def stop(self) -> None:
        self.log.info("[scanner] stop() called")
        await super().stop()
        self.log.info("[scanner] stop() completed")
