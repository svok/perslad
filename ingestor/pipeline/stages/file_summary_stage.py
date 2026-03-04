import asyncio
import hashlib
import time
from pathlib import Path

from ingestor.adapters import BaseStorage
from ingestor.core.models.file_summary import FileSummary
from ingestor.pipeline.base.processor_stage import ProcessorStage
from ingestor.pipeline.models.pipeline_file_context import PipelineFileContext
from ingestor.services.summary_generator import SummaryGenerator
from infra.logger import get_logger


class FileSummaryStage(ProcessorStage):
    def __init__(
        self, 
        storage: BaseStorage, 
        workspace_path: Path, 
        llm,  # LLM instance (OpenAILike)
        lock_manager,  # LLMLockManager
        max_workers: int = 2
    ):
        super().__init__("file_summary", max_workers)
        self.storage = storage
        self.workspace_path = Path(workspace_path)
        self.summary_generator = SummaryGenerator(llm, lock_manager)
        self.log = get_logger("ingestor.file_summary_stage")
    
    async def process(self, context: PipelineFileContext) -> PipelineFileContext:
        file_path = str(context.file_path)
        abs_path = Path(self.workspace_path) / file_path

        # Удаление файла
        if context.event_type == "delete" or not abs_path.exists():
            if not abs_path.exists() and context.event_type != "delete":
                self.log.warning(f"File not found for file_summary: {file_path} (event_type={context.event_type})")
            await self.storage.delete_file_summary(file_path)
            # Также удаляем все чанки файла из БД
            await self.storage.delete_chunks_by_file_paths([file_path])
            self.log.info(f"FileSummary and chunks deleted: {file_path}")
            return context

        try:
            stat = await asyncio.to_thread(abs_path.stat)
            new_checksum = await self._calc_checksum(abs_path)
            
            # Get existing summary if any
            existing_summary = await self.storage.get_file_summary(file_path)
            
            # Check for errors or empty nodes
            if context.has_errors or not context.nodes:
                error_reasons = context.errors if context.errors else ["unknown error"]
                reason = "; ".join(error_reasons)
                
                # Удаляем чанки, если они есть (файл стал невалидным или был ранее валиден)
                await self.storage.delete_chunks_by_file_paths([file_path])
                
                summary = FileSummary(
                    file_path=file_path,
                    summary="",
                    metadata={
                        "size": stat.st_size,
                        "mtime": stat.st_mtime,
                        "checksum": new_checksum,
                        "invalid_reason": reason,
                        "invalid_timestamp": time.time(),
                        "invalid_count": 1,
                        "last_summarized_at": time.time(),
                    }
                )
            else:
                # Collect summaries from chunk nodes (NEW: using chunk summaries instead of raw content)
                chunk_summaries = [
                    node.metadata.get("summary", "")
                    for node in context.nodes
                    if node.metadata.get("summary")
                ]
                
                # Limit to first 20 chunks to save tokens
                combined_summaries = "\n".join(chunk_summaries[:20])
                
                # Generate summary if we don't have one or file changed
                force_regenerate = not existing_summary or existing_summary.metadata.get("checksum") != new_checksum
                
                if force_regenerate:
                    # Generate summary using chunk summaries
                    file_summary_text = await self.summary_generator.generate_file_summary(
                        content=combined_summaries,
                        metadata={
                            "file_path": file_path,
                            "extension": context.nodes[0].metadata.get("extension", ""),
                            "chunk_type": context.nodes[0].metadata.get("chunk_type", ""),
                        }
                    )
                else:
                    # Keep existing summary
                    file_summary_text = existing_summary.summary
                
                summary = FileSummary(
                    file_path=file_path,
                    summary=file_summary_text[:500] if file_summary_text else "",  # Limit to 500 chars
                    metadata={
                        "size": stat.st_size,
                        "mtime": stat.st_mtime,
                        "checksum": new_checksum,
                        "valid": True,
                        "last_summarized_at": time.time(),
                        "chunks_count": len(context.nodes),
                    }
                )
            
            await self.storage.save_file_summary(summary)
            self.log.info(f"FileSummary updated: {file_path} (valid={not context.has_errors}, summary_len={len(summary.summary)})")

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
