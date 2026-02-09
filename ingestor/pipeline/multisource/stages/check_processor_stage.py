from typing import Optional

from ingestor.adapters import BaseStorage
from ingestor.pipeline.multisource.fileinfo import FileInfo
from ingestor.pipeline.multisource.stages.pipeline_stage import PipelineStage


class CheckProcessorStage(PipelineStage):
    """Стадия проверки изменений в БД"""

    def __init__(self, storage: BaseStorage, batch_size: int = 50, max_workers: int = 2):
        super().__init__("check", max_workers)
        self.storage = storage
        self.batch_size = batch_size
        self._current_batch = []

    async def process(self, file_info: FileInfo) -> Optional[FileInfo]:
        """Накопление батча и проверка в БД"""
        self._current_batch.append(file_info)

        if len(self._current_batch) >= self.batch_size:
            changed = await self._check_batch(self._current_batch.copy())
            self._current_batch.clear()
            # Возвращаем список измененных файлов
            return changed if changed else None

        return None

    async def _check_batch(self, batch) -> list:
        """Проверяет батч файлов в БД"""
        changed_files = []

        for file_info in batch:
            try:
                saved_file = await self.storage.get_file_summary(file_info.relative_path)

                if saved_file is None:
                    changed_files.append(file_info)
                    continue

                saved_meta = saved_file.metadata or {}
                saved_mtime = saved_meta.get("mtime", 0)
                saved_checksum = saved_meta.get("checksum", "")

                if (abs(saved_mtime - file_info.mtime) > 0.001 or
                        saved_checksum != file_info.checksum):
                    changed_files.append(file_info)

            except Exception as e:
                changed_files.append(file_info)  # При ошибке переиндексируем
                raise

        return changed_files

    async def stop(self):
        """Обрабатывает последний батч при остановке"""
        if self._current_batch:
            changed = await self._check_batch(self._current_batch)
            if changed and self.output_queue:
                await self.output_queue.put(changed)
        await super().stop()
