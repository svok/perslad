import asyncio
from pathlib import Path
from typing import AsyncGenerator, Optional

import inotify_simple
from inotify_simple import flags

from ingestor.pipeline.multisource.file_event import FileEvent, EventTypes
from ingestor.pipeline.multisource.gitignore_checker import GitignoreChecker
from ingestor.pipeline.multisource.stages.source_stage import SourceStage


class InotifySourceStage(SourceStage):
    """Inotify с inline фильтрацией"""

    # Маппинг флагов
    FLAG_MAP: dict[int, EventTypes] = {
        flags.CREATE: "create",
        flags.DELETE: "delete",
        flags.MODIFY: "modify",
        flags.CLOSE_WRITE: "modify",
        flags.MOVED_FROM: "delete",
        flags.MOVED_TO: "create",
    }

    def __init__(self, workspace_path: Path):
        super().__init__("inotify")
        self.workspace_path = Path(workspace_path).resolve()

        self.IS = inotify_simple.INotify()
        self._watch_descriptor: int = 0

        # Checker
        self.checker = GitignoreChecker(self.workspace_path)
        self.checker.load()

    async def start(self, output_queue) -> None:
        self.log.info("[inotify] start() called")
        await super().start(output_queue)
        self.log.info("[inotify] super().start() completed")

    async def _read_loop(self) -> AsyncGenerator[FileEvent, None]:
        self.log.info(f"[inotify] _read_loop STARTED")

        while not self._stop_event.is_set():
            # Используем небольшой таймаут в самом inotify или sleep
            # inotify_simple.read блокирует поток, если timeout не 0.
            # Поэтому используем 0 и asyncio.sleep
            events = self.IS.read(timeout=0)

            if not events:
                await asyncio.sleep(1.0) # Важно! Освобождает Event Loop
                continue

            for event in events:
                if event.mask & flags.ISDIR:
                    continue

                abs_path = self.workspace_path / event.name
                rel_path = abs_path.relative_to(self.workspace_path)

                if self.checker.should_ignore(abs_path):
                    continue

                event_type = self._map_mask(event.mask)
                if event_type:
                    self.log.info(f"[inotify] yielding event: {rel_path}")
                    yield FileEvent(
                        path=rel_path,
                        event_type=event_type,
                        abs_path=abs_path
                    )

    async def generate(self) -> AsyncGenerator[FileEvent, None]:
        self.log.info(f"[{self.name}] Starting inotify on: {self.workspace_path}")

        try:
            self._watch_descriptor = self.IS.add_watch(
                self.workspace_path,
                mask=(flags.CREATE | flags.DELETE | flags.MODIFY |
                      flags.MOVED_FROM | flags.MOVED_TO | flags.CLOSE_WRITE)
            )

            async for event in self._read_loop():
                yield event

        finally:
            if self._watch_descriptor is not None:
                try:
                    self.IS.rm_watch(self._watch_descriptor)
                except Exception as e:
                    self.log.debug(f"Error removing watch: {e}")

    def _map_mask(self, mask: int) -> Optional[EventTypes]:
        for flag, name in self.FLAG_MAP.items():
            if mask & flag:
                return name
        return None
