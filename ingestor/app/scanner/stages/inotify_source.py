import asyncio
from pathlib import Path
from typing import AsyncGenerator, Optional

import inotify_simple
from inotify_simple import flags

from infra.logger import get_logger
from ingestor.app.scanner.file_event import FileEvent
from ingestor.app.scanner.gitignore_checker import GitignoreChecker
from ingestor.app.scanner.stages.source_stage import SourceStage


class InotifySourceStage(SourceStage):
    """Inotify с inline фильтрацией"""

    # Маппинг флагов
    FLAG_MAP = {
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
        self._event_queue: asyncio.Queue[FileEvent] = asyncio.Queue(maxsize=1000)

        # Checker
        self.checker = GitignoreChecker(self.workspace_path)
        self.checker.load()

    async def generate(self) -> AsyncGenerator[FileEvent, None]:
        """Читает события, фильтрует на лету"""
        self.log.info(f"[{self.name}] Starting inotify: {self.workspace_path}")

        # Устанавливаем watch
        try:
            self._watch_descriptor = self.IS.add_watch(
                self.workspace_path,
                mask=(
                        flags.CREATE | flags.DELETE | flags.MODIFY |
                        flags.MOVED_FROM | flags.MOVED_TO | flags.CLOSE_WRITE
                )
            )
        except Exception as e:
            self.log.error(f"Failed to add watch: {e}")
            raise

        # Запускаем чтение в фоне
        read_task = asyncio.create_task(self._read_loop())

        try:
            while not self._stop_event.is_set():
                try:
                    event = await asyncio.wait_for(
                        self._event_queue.get(),
                        timeout=0.5
                    )
                    yield event
                except asyncio.TimeoutError:
                    continue
        finally:
            read_task.cancel()
            try:
                await read_task
            except asyncio.CancelledError:
                pass
            if self._watch_descriptor:
                try:
                    self.IS.rm_watch(self._watch_descriptor)
                except Exception:
                    pass

    async def _read_loop(self) -> None:
        """Читает из inotify и фильтрует"""
        ignored = 0
        passed = 0

        while not self._stop_event.is_set():
            try:
                events = self.IS.read(timeout=100)  # 100ms timeout

                for event in events:
                    if event.mask & flags.IN_ISDIR:
                        continue

                    abs_path = Path(event.pathname)
                    rel_path = abs_path.relative_to(self.workspace_path)

                    # # Фильтрация (та же логика что в сканере)
                    # if self.checker.is_quick_ignore(abs_path):
                    #     ignored += 1
                    #     continue

                    if self.checker.should_ignore(abs_path):
                        ignored += 1
                        continue

                    # Прошёл
                    passed += 1
                    event_type: str = self._map_mask(event.mask)

                    # Не блокируемся на очереди
                    try:
                        if event_type in FileEvent.EVENT_TYPES:
                            self._event_queue.put_nowait(FileEvent(
                                path=rel_path,
                                event_type=event_type,
                                abs_path=abs_path
                            ))
                    except asyncio.QueueFull:
                        self.log.warning("Event queue full, dropping event")

            except inotify_simple.TIMEOUT:
                continue
            except Exception as e:
                self.log.error(f"Read error: {e}")
                break

        self.log.info(f"Inotify stats: passed={passed}, ignored={ignored}")

    def _map_mask(self, mask: int) -> str:
        for flag, name in self.FLAG_MAP.items():
            if mask & flag:
                return name
        return "unknown"
