import os
from pathlib import Path
from typing import AsyncGenerator

from infra.logger import get_logger
from ingestor.pipeline.models.pipeline_file_context import PipelineFileContext
from ingestor.pipeline.utils.gitignore_checker import GitignoreChecker
from ingestor.pipeline.base.source_stage import SourceStage

class ScannerSourceStage(SourceStage):
    def __init__(self, workspace_path: Path, max_workers: int = 2):
        super().__init__("scanner")
        self.workspace_path = Path(workspace_path).resolve()
        self.checker = GitignoreChecker(self.workspace_path)
        self.log = get_logger('ingestor.scanner.ScannerSourceStage')
        self.log.info(f"[scanner] Initialized, workspace={self.workspace_path}")

    async def generate(self) -> AsyncGenerator[PipelineFileContext, None]:
        try:
            if not self.workspace_path.exists():
                self.log.error("Path does not exist: %s", self.workspace_path)
                return

            self.log.info("Starting scan...")

            for root, dirs, files in os.walk(self.workspace_path):
                current_root = Path(root)

                # 1. Динамически подгружаем .gitignore, если встретили ее в новой папке
                if (current_root / '.gitignore').exists():
                    self.checker.load_spec_for_dir(current_root)

                # 2. Фильтруем директории (модификация dirs In-place отсекает ветки)
                # Оставляем только те, что не заигнорены
                dirs[:] = [
                    d for d in dirs
                    if not self.checker.should_ignore(current_root / d, is_dir=True)
                ]

                # 3. Обрабатываем файлы
                for filename in files:
                    file_path = current_root / filename

                    if self.checker.should_ignore(file_path, is_dir=False):
                        continue

                    try:
                        rel_path = file_path.relative_to(self.workspace_path)
                    except ValueError:
                        continue

                    self.log.info(f"[scanner] File detected {rel_path}")
                    yield PipelineFileContext(
                        file_path=rel_path,
                        abs_path=file_path,
                        event_type="scan",
                        status="pending"
                    )

            self.log.info("Scan completed")
        except Exception as e:
            self.log.error("Scan generation error: %s", e, exc_info=True)
            raise

    async def start(self, output_queue) -> None:
        self.log.info("[scanner] start() called")
        await super().start(output_queue)
        self.log.info("[scanner] super().start() completed")

    async def stop(self) -> None:
        self.log.info("[scanner] stop() called")
        await super().stop()
        self.log.info("[scanner] stop() completed")
