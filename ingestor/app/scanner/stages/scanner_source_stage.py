import asyncio
import os
from pathlib import Path
from typing import AsyncGenerator

from infra.logger import get_logger
from ingestor.app.scanner.file_event import FileEvent
from ingestor.app.scanner.gitignore_checker import GitignoreChecker
from ingestor.app.scanner.stages.source_stage import SourceStage


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

    async def _run(self) -> None:
        self.log.info("[scanner] _run() ENTER")
        try:
            count = 0
            async for item in self.generate():
                count += 1
                self.log.info(f"[scanner] Generated item #{count}: {item.path}")

                if self._stop_event.is_set():
                    self.log.info("[scanner] Stop event detected, breaking")
                    break

                self.log.info(f"[scanner] Putting to queue: {item.path}")
                await self.output_queue.put(item)
                self.log.info(f"[scanner] Put successful: {item.path}")

        except asyncio.CancelledError:
            self.log.info("[scanner] CancelledError in _run()")
            raise
        except Exception as e:
            self.log.error(f"[scanner] Exception in _run(): {e}", exc_info=True)
            raise
        finally:
            self.log.info(f"[scanner] _run() FINALLY, total items: {count}")

    async def generate(self) -> AsyncGenerator[FileEvent, None]:
        self.log.info(f"[scanner] generate() ENTER")

        if not self.workspace_path.exists():
            self.log.error(f"[scanner] Path does not exist: {self.workspace_path}")
            return

        self.log.info("[scanner] Starting os.walk...")

        for root, dirs, files in os.walk(self.workspace_path):
            self.log.info(f"[scanner] Walking: {root}, dirs={len(dirs)}, files={len(files)}")

            # Фильтруем директории
            filtered_dirs = []
            for d in dirs:
                dir_path = Path(root) / d
                if dir_path.name.startswith('.') or dir_path.name in ('__pycache__', 'node_modules'):
                    self.log.debug(f"[scanner] Skipping dir by name: {d}")
                    continue
                if self.checker.should_ignore(dir_path):
                    self.log.debug(f"[scanner] Skipping dir by gitignore: {d}")
                    continue
                filtered_dirs.append(d)

            removed = len(dirs) - len(filtered_dirs)
            if removed:
                self.log.info(f"[scanner] Filtered {removed} dirs in {root}")
            dirs[:] = filtered_dirs

            # Обрабатываем файлы
            for filename in files:
                file_path = Path(root) / filename

                if self.checker.should_ignore(file_path):
                    self.log.debug(f"[scanner] Ignoring file: {file_path}")
                    continue

                try:
                    rel_path = file_path.relative_to(self.workspace_path)
                except ValueError as e:
                    self.log.error(f"[scanner] relative_to failed: {e}")
                    continue

                self.log.info(f"[scanner] Yielding: {rel_path}")

                yield FileEvent(
                    path=rel_path,
                    event_type="scan",
                    abs_path=file_path
                )

                self.log.info(f"[scanner] Yielded: {rel_path}")

                # Проверяем остановку
                if self._stop_event.is_set():
                    self.log.info("[scanner] Stop event in generate(), breaking")
                    return

        self.log.info("[scanner] generate() COMPLETED naturally")

    async def stop(self) -> None:
        self.log.info("[scanner] stop() called")
        await super().stop()
        self.log.info("[scanner] stop() completed")
