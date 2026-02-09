import asyncio
import hashlib
from pathlib import Path
from typing import List, Set

from ingestor.adapters import BaseStorage
from ingestor.app.scanner.stages.processor_stage import ProcessorStage
from ingestor.app.storage import Chunk, FileSummary


class FileSummaryStage(ProcessorStage):
    def __init__(self, storage: BaseStorage, workspace_path: Path, max_workers: int = 2):
        super().__init__("file_summary", max_workers)
        self.storage = storage
        self.workspace_path = workspace_path
        self._processed: Set[str] = set()
        self._lock = asyncio.Lock()

    async def process(self, chunks: List[Chunk]) -> List[Chunk]:

        self.log.debug("FS: DB Pr0")

        if not chunks:
            return chunks

        # Берем данные первого чанка для идентификации файла
        file_path = chunks[0].file_path
        abs_path = self.workspace_path / file_path

        # Если файла нет, просто пробрасываем чанки дальше
        if not abs_path.exists():
            return chunks

        try:
            # Считаем состояние (выносим в поток, чтобы не блокировать loop)
            self.log.debug(f"FS: DB Pr1 {file_path}")
            stat = await asyncio.to_thread(abs_path.stat)
            self.log.debug(f"FS: DB Pr2 {file_path}")
            new_checksum = await self._calc_checksum(abs_path)

            # Проверяем, нужно ли обновлять (без локов!)
            self.log.debug(f"FS: DB Get Start {file_path}")
            existing = await self.storage.get_file_summary(file_path)
            self.log.debug(f"FS: DB Get End {file_path}")

            if existing and existing.metadata.get("checksum") == new_checksum:
                return chunks

            summary = FileSummary(
                file_path=file_path,
                summary="",
                chunk_ids=[c.id for c in chunks],
                metadata={
                    "mtime": stat.st_mtime,
                    "checksum": new_checksum,
                    "size": stat.st_size
                }
            )

            # Если здесь будет ошибка (например, из-за $1..$6),
            # мы её увидим в логе, и воркер перейдет к следующей задаче
            await self.storage.save_file_summary(summary)
            self.log.info(f"FileSummary updated: {file_path}")

        except Exception as e:
            self.log.error(f"Error in FileSummaryStage: {e}", exc_info=True)

        return chunks

    async def _calc_checksum(self, path: Path) -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._sync_hash, path)

    def _sync_hash(self, path: Path) -> str:
        h = hashlib.md5()
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                h.update(chunk)
        return h.hexdigest()
