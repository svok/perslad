"""
File Scanner - Full Workspace Scan with Diff

Стриминг сканер workspace для старта.
Проверяет разницу между текущим состоянием и БД.
"""

import asyncio
from pathlib import Path
from typing import List, Optional, Callable
from datetime import datetime, timezone

from ingestor.adapters.base_storage import BaseStorage
from ingestor.app.storage import FileSummary
from ingestor.app.pipeline.scan import ScanStage
from ingestor.app.watchers.base import BaseFileSource


class FileScannerSource(BaseFileSource):
    """
    Сканер workspace для стартового полного скана.
    Проверяет изменения за время неактивности.
    """

    def __init__(
        self,
        workspace_path: str,
        storage: BaseStorage,
        on_files_changed: Callable[[List[FileSummary]], None]
    ):
        super().__init__(workspace_path)
        self.storage = storage
        self.on_files_changed = on_files_changed
        self._running = False
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Запускает сканер"""
        super()._load_gitignore_matchers()

        async with self._lock:
            if self._running:
                return
            self._running = True

        # Загружаем сохраненные файлы из БД
        saved_files = await self.storage.get_all_file_summaries()

        # Маппинг для быстрого поиска
        saved_by_path = {f.file_path: f for f in saved_files}

        # Получаем минимальное время мутации из БД
        min_mtime = 0
        if saved_files:
            for f in saved_files:
                mtime = f.metadata.get("mtime", 0) if f.metadata else 0
                if mtime > min_mtime:
                    min_mtime = mtime

        log.info("file_scanner.start", workspace=str(self.workspace_path), min_mtime=min_mtime)

        # Стартуем сканирование
        asyncio.create_task(self._scan_workspace(min_mtime))

        log.info("file_scanner.started")

    async def _scan_workspace(self, min_mtime: float) -> None:
        """Сканирует workspace и находит изменившиеся файлы"""
        try:
            scan_stage = ScanStage(str(self.workspace_path))
            all_files = await scan_stage.run()

            log.info("file_scanner.scan.complete", files_found=len(all_files))

            # Группируем файлы по статусу
            new_files = []
            changed_files = []

            for file in all_files:
                abs_path = self.workspace_path / file.relative_path
                current_mtime = abs_path.stat().st_mtime

                if current_mtime > min_mtime:
                    if file.relative_path not in saved_by_path:
                        new_files.append(file)
                    else:
                        # Проверяем контрольную сумму
                        saved_file = saved_by_path[file.relative_path]
                        current_checksum = self._calculate_file_checksum(abs_path)
                        saved_checksum = saved_file.metadata.get("checksum", "") if saved_file.metadata else ""

                        if current_checksum != saved_checksum:
                            changed_files.append(file)
                else:
                    # Этот файл не менялся за время неактивности - можно пропустить
                    pass

            log.info("file_scanner.diff.complete", new_files=len(new_files), changed_files=len(changed_files))

            if new_files or changed_files:
                # Сливаем файлы и отправляем в обработку
                files_to_index = new_files + changed_files
                log.info("file_scanner.triggers_indexing", count=len(files_to_index))
                self.on_files_changed(files_to_index)

        except Exception as e:
            log.error("file_scanner.scan.error", error=str(e), exc_info=True)

    def _calculate_file_checksum(self, file_path: Path) -> str:
        """Расчитывает контрольную сумму файла"""
        import hashlib
        try:
            hash_md5 = hashlib.md5()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception:
            return ""

    async def stop(self) -> None:
        """Останавливает сканер"""
        async with self._lock:
            self._running = False

        log.info("file_scanner.stopped")
