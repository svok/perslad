import asyncio
import hashlib
from pathlib import Path
from typing import List, Set

from ingestor.app.scanner.stages.processor_stage import ProcessorStage
from ingestor.app.storage import Chunk, FileSummary


class FileSummaryStage(ProcessorStage):
    def __init__(self, storage, workspace_path: Path, max_workers: int = 2):
        super().__init__("file_summary", max_workers, batch_size=1, output_is_batch=True)
        self.storage = storage
        self.workspace_path = workspace_path
        self._processed: Set[str] = set()
        self._lock = asyncio.Lock()

    async def process(self, chunks: List[Chunk]) -> List[Chunk]:
        if not chunks:
            return chunks

        file_path = chunks[0].file_path

        async with self._lock:
            if file_path in self._processed:
                return chunks
            self._processed.add(file_path)

        abs_path = self.workspace_path / file_path
        mtime, checksum, size = 0, "", 0

        if abs_path.exists():
            stat = abs_path.stat()
            mtime = stat.st_mtime
            size = stat.st_size
            checksum = await self._calc_checksum(abs_path)

        summary = FileSummary(
            file_path=file_path,
            summary="",
            chunk_ids=[c.id for c in chunks],
            metadata={"mtime": mtime, "checksum": checksum, "size": size}
        )

        await self.storage.save_file_summary(summary)
        self.log.info(f"Saved file: {file_path}")

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
