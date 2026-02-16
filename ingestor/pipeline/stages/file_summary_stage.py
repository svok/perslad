import asyncio
import hashlib
from pathlib import Path

from ingestor.adapters import BaseStorage
from ingestor.core.models.file_summary import FileSummary
from ingestor.pipeline.base.processor_stage import ProcessorStage
from ingestor.pipeline.models.context import PipelineFileContext


class FileSummaryStage(ProcessorStage):
    def __init__(
        self, storage: BaseStorage, workspace_path: Path, max_workers: int = 2
    ):
        super().__init__("file_summary", max_workers)
        self.storage = storage
        self.workspace_path = Path(workspace_path)

    async def process(self, context: PipelineFileContext) -> PipelineFileContext:
        file_path = str(context.file_path)
        abs_path = Path(self.workspace_path) / file_path

        if not abs_path.exists():
            # Если файла нет, возможно его удалили.
            # Inotify delete event обрабатывается отдельно?
            # Если это scan event и файла нет -> странно.
            return context

        try:
            stat = await asyncio.to_thread(abs_path.stat)
            new_checksum = await self._calc_checksum(abs_path)
            
            # Проверяем на ошибки
            if context.has_errors or not context.chunks:
                # ========== БИТЫЙ ФАЙЛ ==========
                error_reasons = context.errors if context.errors else ["unknown error"]
                reason = "; ".join(error_reasons)
                
                summary = FileSummary(
                    file_path=file_path,
                    summary="", # Пустое summary
                    # chunk_ids removed
                    metadata={
                        "size": stat.st_size,
                        "mtime": stat.st_mtime,
                        "checksum": new_checksum,
                        "invalid_reason": reason,
                        "invalid_timestamp": asyncio.get_running_loop().time(), # Timestamp
                        "invalid_count": 1 # Можно инкрементировать, если читать старое
                    }
                )
            else:
                # ========== УСПЕШНЫЙ ФАЙЛ ==========
                summary = FileSummary(
                    file_path=file_path,
                    summary="", # Summary пока пустое (заполняется другим агентом или позже)
                    # chunk_ids removed
                    metadata={
                        "size": stat.st_size,
                        "mtime": stat.st_mtime,
                        "checksum": new_checksum,
                        "valid": True
                    }
                )
            
            await self.storage.save_file_summary(summary)
            self.log.info(f"FileSummary updated: {file_path} (valid={not context.has_errors})")

        except Exception as e:
            self.log.error(f"Error in FileSummaryStage: {e}", exc_info=True)

        return context

        # Нет чанков – ничего не делаем (summary не обновляем)
        if not context.chunks:
            return context

        file_path = str(context.file_path)
        abs_path = Path(self.workspace_path) / file_path

        if not abs_path.exists():
            return context

        try:
            stat = await asyncio.to_thread(abs_path.stat)
            new_checksum = await self._calc_checksum(abs_path)

            existing = await self.storage.get_file_summary(file_path)
            if existing and existing.metadata.get("checksum") == new_checksum:
                return context  # Не изменился

            summary = FileSummary(
                file_path=file_path,
                summary="",
                chunk_ids=[c.id for c in context.chunks],
                metadata={
                    "mtime": stat.st_mtime,
                    "checksum": new_checksum,
                    "size": stat.st_size,
                },
            )
            await self.storage.save_file_summary(summary)
            self.log.info(f"FileSummary updated: {file_path}")

        except Exception as e:
            self.log.error(f"Error in FileSummaryStage: {e}", exc_info=True)

        return context

    async def _calc_checksum(self, path: Path) -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._sync_hash, path)

    def _sync_hash(self, path: Path) -> str:
        h = hashlib.md5()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()
