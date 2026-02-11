import asyncio
import os
from pathlib import Path
from typing import AsyncGenerator, Optional, Dict

import inotify_simple
from inotify_simple import flags

from ingestor.pipeline.models.file_event import FileEvent, EventTypes
from ingestor.pipeline.indexation.gitignore_checker import GitignoreChecker
from ingestor.pipeline.base.source_stage import SourceStage


class InotifySourceStage(SourceStage):
    """Inotify с рекурсивным мониторингом и Gitignore фильтрацией"""

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
        self.inotify = inotify_simple.INotify()
        # Храним маппинг wd -> Path для восстановления полных путей
        self._wd_to_path: Dict[int, Path] = {}

        self.checker = GitignoreChecker(self.workspace_path)
        # Предварительно загружаем все .gitignore для корректной фильтрации веток
        self._refresh_gitignores()

    def _refresh_gitignores(self):
        for gi in self.workspace_path.rglob('.gitignore'):
            self.checker.load_spec_for_dir(gi.parent)

    def _add_watch_recursive(self, path: Path):
        """Рекурсивно добавляет папки в мониторинг, учитывая игнорирование"""
        for root, dirs, files in os.walk(path):
            root_path = Path(root)

            # Фильтруем директории на лету, чтобы не вешать лишние вотчеры
            dirs[:] = [d for d in dirs if not self.checker.should_ignore(root_path / d, is_dir=True)]

            wd = self.inotify.add_watch(
                root,
                mask=(flags.CREATE | flags.DELETE | flags.MODIFY |
                      flags.MOVED_FROM | flags.MOVED_TO | flags.CLOSE_WRITE | flags.ONLYDIR)
            )
            self._wd_to_path[wd] = root_path

    async def _read_loop(self) -> AsyncGenerator[FileEvent, None]:
        self.log.info("[inotify] _read_loop STARTED")

        while not self._stop_event.is_set():
            # Таймаут 0 позволяет не блокировать поток, но требует asyncio.sleep
            events = self.inotify.read(timeout=0)

            if not events:
                await asyncio.sleep(1.0)
                continue

            for event in events:
                parent_path = self._wd_to_path.get(event.wd)
                if not parent_path:
                    continue

                abs_path = parent_path / event.name
                is_dir = bool(event.mask & flags.ISDIR)

                # 1. Если это новый .gitignore — обновляем правила
                if not is_dir and event.name == '.gitignore':
                    self.checker.load_spec_for_dir(parent_path)

                # 2. Проверка игнорирования
                if self.checker.should_ignore(abs_path, is_dir=is_dir):
                    continue

                # 3. Если создана новая папка — добавляем её в мониторинг
                if is_dir and (event.mask & (flags.CREATE | flags.MOVED_TO)):
                    self._add_watch_recursive(abs_path)
                    continue

                # 4. Маппинг и yield события для файлов
                if not is_dir:
                    event_type = self._map_mask(event.mask)
                    if event_type:
                        try:
                            rel_path = abs_path.relative_to(self.workspace_path)
                            yield FileEvent(
                                path=rel_path,
                                event_type=event_type,
                                abs_path=abs_path
                            )
                        except ValueError:
                            continue

    async def generate(self) -> AsyncGenerator[FileEvent, None]:
        self.log.info(f"[{self.name}] Starting recursive inotify on: {self.workspace_path}")
        try:
            self._add_watch_recursive(self.workspace_path)
            async for event in self._read_loop():
                yield event
        finally:
            # Очистка дескрипторов при остановке
            for wd in list(self._wd_to_path.keys()):
                try:
                    self.inotify.rm_watch(wd)
                except:
                    pass
            self._wd_to_path.clear()

    def _map_mask(self, mask: int) -> Optional[EventTypes]:
        for flag, name in self.FLAG_MAP.items():
            if mask & flag:
                return name
        return None
