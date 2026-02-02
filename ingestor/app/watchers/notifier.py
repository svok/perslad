"""
File Notifier - Runtime File Watching with fsnotify

Мониторит изменения в реальном времени через fsnotify
"""

import asyncio
from pathlib import Path
from typing import Callable, List

import fsnotify

from ingestor.adapters.base_storage import BaseStorage
from ingestor.app.storage import FileSummary
from ingestor.app.watchers.base import BaseFileSource


class FileNotifierSource(BaseFileSource):
    """
    Мониторит изменения файлов через fsnotify
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
        self._observer: fsnotify.Observer = None
        self._running = False
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Запускает fsnotify наблюдатель"""
        super()._load_gitignore_matchers()

        log.info("file_notifier.starting", workspace=str(self.workspace_path))

        async with self._lock:
            if self._running:
                log.warning("file_notifier already running")
                return

            self._running = True

        # Создаем наблюдатель
        self._observer = fsnotify.Observer()
        self._observer.schedule(self._on_change, str(self.workspace_path), recursive=True)
        self._observer.start()

        log.info("file_notifier.started")

    async def stop(self) -> None:
        """Останавливает fsnotify наблюдатель"""
        async with self._lock:
            if not self._running:
                return

            self._running = False
            log.info("file_notifier.stopping")

        if self._observer:
            self._observer.stop()
            self._observer.join()

        log.info("file_notifier.stopped")

    def _on_change(self, event: fsnotify.Event) -> None:
        """
        Обработчик событий fsnotify
        """
        # Игнорируем директории
        if event.is_directory:
            return

        # Получаем относительный путь
        try:
            relative_path = Path(event.src_path).relative_to(self.workspace_path)
        except ValueError:
            return

        # Проверяем .gitignore
        if self._should_ignore_path(Path(event.src_path)):
            return

        # Определяем тип события
        event_type = self._map_event_type(event)

        log.debug("file_notifier.event", event=event_type, file=str(relative_path))

        # Вызываем callback (event_type может быть "delete", "create", "modified")
        asyncio.create_task(self._trigger_event(relative_path, event_type))

    async def _trigger_event(self, file_path: str, event_type: str) -> None:
        """Вызывает callback с событием"""
        try:
            self.on_file_event(file_path, event_type)
        except Exception as e:
            log.error("file_notifier.event_failed", file=file_path, error=str(e), exc_info=True)

    def _map_event_type(self, event: fsnotify.Event) -> str:
        """Маппинг fsnotify событий в типы событий"""
        if event.is_create:
            return "create"
        elif event.is_delete:
            return "delete"
        elif event.is_modify:
            return "modified"
        elif event.is_rename:
            return "rename"
        else:
            return "unknown"

    @property
    def is_running(self) -> bool:
        return self._running
