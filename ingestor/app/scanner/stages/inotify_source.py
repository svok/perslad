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
        self._task: Optional[asyncio.Task] = None

        # Checker
        self.checker = GitignoreChecker(self.workspace_path)
        self.checker.load()

    async def _read_loop(self) -> AsyncGenerator[FileEvent, None]:
        """Читает события и сразу их генерирует"""
        try:
            self.log.info(f"[inotify] _read_loop STARTED")

            while not self._stop_event.is_set():
                try:
                    # Non-blocking read - read() returns generator, not coroutine
                    events = self.IS.read(timeout=0)

                    for event in events:
                        # Игнорируем события для директорий
                        if event.mask & flags.ISDIR:
                            continue

                        # event.name содержит только имя файла
                        # Аbsolute path = workspace_path + event.name
                        abs_path = self.workspace_path / event.name

                        # Получаем относительный путь
                        rel_path = abs_path.relative_to(self.workspace_path)

                        # Проверяем .gitignore
                        if self.checker.should_ignore(abs_path):
                            continue

                        # Маппинг событий
                        event_type: str = self._map_mask(event.mask)

                        self.log.info(f"[inotify] event: {rel_path} -> {event_type}")

                        # Генерируем событие сразу
                        yield FileEvent(
                            path=rel_path,
                            event_type=event_type,
                            abs_path=abs_path
                        )

                except Exception as e:
                    if not self._stop_event.is_set():
                        self.log.error(f"Read error: {e}")
                    break

            self.log.info(f"[inotify] _read_loop stopped")

        except asyncio.CancelledError:
            self.log.info(f"[inotify] _read_loop cancelled")
            raise
        except Exception as e:
            self.log.error(f"Read loop error: {e}")
            raise

    async def generate(self) -> AsyncGenerator[FileEvent, None]:
        """Обертка для асинхронного генератора"""
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

        try:
            async for event in self._read_loop():
                yield event
        finally:
            print("INOTIFY EXCEPTION")

            if self._watch_descriptor:
                try:
                    self.IS.rm_watch(self._watch_descriptor)
                except Exception:
                    print("INOTIFY EXCEPTION")
                    pass

    def _map_mask(self, mask: int) -> str:
        for flag, name in self.FLAG_MAP.items():
            if mask & flag:
                return name
        return "unknown"
