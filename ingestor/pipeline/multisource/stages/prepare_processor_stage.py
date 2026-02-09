import asyncio
import hashlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

from infra.logger import get_logger
from ingestor.pipeline.multisource.fileinfo import FileInfo
from ingestor.pipeline.multisource.stages.pipeline_stage import PipelineStage


class PrepareProcessorStage(PipelineStage):
    """Стадия подготовки метаданных"""

    def __init__(self, workspace_path: Path, max_workers: int = 4):
        super().__init__("prepare", max_workers)
        self.log = get_logger('ingestor.scanner.prepare_stage')
        self.workspace_path = workspace_path
        self.executor = ThreadPoolExecutor(max_workers=4)

    async def process(self, file_path: Path) -> Optional[FileInfo]:
        """Собирает метаданные файла"""
        try:
            loop = asyncio.get_event_loop()

            # Параллельно получаем stat и checksum
            # noinspection PyTypeChecker
            stat_task = loop.run_in_executor(self.executor, file_path.stat)
            checksum_task = loop.run_in_executor(self.executor, self._calculate_checksum, file_path)

            # Дожидаемся выполнения обеих
            stat, checksum = await asyncio.gather(stat_task, checksum_task)

            return FileInfo(
                path=file_path,
                relative_path=str(file_path.relative_to(self.workspace_path)),
                size=stat.st_size,
                mtime=stat.st_mtime,
                checksum=checksum
            )
        except Exception as e:
            self.log.error(f"Prepare error for {file_path}", exc_info=True)
            return None

    def _calculate_checksum(self, file_path: Path) -> str:
        """Синхронное вычисление контрольной суммы"""
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception:
            self.log.error(f"Calculate checksum for {file_path}", exc_info=True)
            return ""
