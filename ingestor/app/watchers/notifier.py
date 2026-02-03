"""
File Notifier - Runtime File Watching with inotify-simple 2.0.1

Мониторит изменения в реальном времени через native inotify (C)
"""

import asyncio
from pathlib import Path
from typing import Callable

import inotify_simple
from inotify_simple import flags

from infra.logger import get_logger
from ingestor.adapters.base_storage import BaseStorage
from ingestor.app.watchers.base import BaseFileSource

log = get_logger("ingestor.notifier")


class FileNotifierSource(BaseFileSource):
    """
    Мониторит изменения файлов через native inotify (C)
    """

    def __init__(
        self,
        workspace_path: str,
        storage: BaseStorage,
        on_file_event: Callable[[str, str], None]  # (file_path, event_type)
    ):
        super().__init__(workspace_path)
        self.storage = storage
        self.on_file_event = on_file_event

        self.IS = inotify_simple.INotify()
        self._running = False
        self._watch_descriptor: int = 0
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Запускает inotify observer"""
        super()._load_gitignore_matchers()

        log.info("file_notifier.starting", workspace=str(self.workspace_path))

        async with self._lock:
            if self._running:
                log.warning("file_notifier already running")
                return

            self._running = True

        # Add watch
        try:
            self._watch_descriptor = self.IS.add_watch(
                self.workspace_path,
                mask=(
                    flags.CREATE
                    | flags.DELETE
                    | flags.MODIFY
                    | flags.MOVED_FROM
                    | flags.MOVED_TO
                    | flags.CLOSE_WRITE
                )
            )
            log.info("file_notifier.watch_added", descriptor=self._watch_descriptor)
        except Exception as e:
            log.error("file_notifier.watch_failed", error=str(e), exc_info=True)
            self._running = False
            raise

        # Start event loop in background
        asyncio.create_task(self._read_loop())

        log.info("file_notifier.started")

    async def stop(self) -> None:
        """Останавливает inotify observer"""
        async with self._lock:
            if not self._running:
                return

            self._running = False
            log.info("file_notifier.stopping")

        # Remove watch
        if self._watch_descriptor:
            self.IS.rm_watch(self._watch_descriptor)

        log.info("file_notifier.stopped")

    async def _read_loop(self) -> None:
        """
        Non-blocking event loop.
        Checks inotify queue every 0ms (non-blocking), raises TIMEOUT if empty.
        """
        try:
            log.info("file_notifier.read_loop.starting")

            while self._running:
                try:
                    # Non-blocking read (timeout=0)
                    events = self.IS.read(timeout=0)

                    for event in events:
                        # Игнорируем события для директорий
                        if event.mask & flags.IN_ISDIR:
                            continue

                        # Получаем относительный путь
                        try:
                            relative_path = Path(event.pathname).relative_to(self.workspace_path)
                        except ValueError:
                            continue

                        # Проверяем .gitignore
                        abs_path = self.workspace_path / relative_path
                        if self._should_ignore_path(abs_path):
                            continue

                        # Маппинг событий
                        event_type = self._map_mask_to_type(event.mask)

                        log.debug("file_notifier.event", file=str(relative_path), event=event_type)

                        # Вызываем callback
                        asyncio.create_task(self._trigger_event(str(relative_path), event_type))

                except inotify_simple.TIMEOUT:
                    # Ничего не произошло, проверяем флаг running и продолжаем
                    continue

                except Exception as e:
                    if not self._running:
                        break
                    log.error("file_notifier.read_loop.error", error=str(e), exc_info=True)
                    break

            log.info("file_notifier.read_loop.stopped")

        except asyncio.CancelledError:
            log.info("file_notifier.read_loop.cancelled")
            raise

    async def _trigger_event(self, file_path: str, event_type: str) -> None:
        """Вызывает callback с событием"""
        try:
            self.on_file_event(file_path, event_type)
        except Exception as e:
            log.error("file_notifier.event_failed", file=file_path, error=str(e), exc_info=True)

    def _map_mask_to_type(self, mask: int) -> str:
        """
        Маппинг inotify масок в типы событий
        """
        if mask & flags.CREATE: return "create"
        if mask & flags.DELETE: return "delete"
        if mask & flags.MODIFY | mask & flags.CLOSE_WRITE: return "modified"
        if mask & flags.MOVED_FROM | mask & flags.MOVED_TO: return "rename"
        return "unknown"
