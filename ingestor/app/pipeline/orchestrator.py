"""
Pipeline Orchestrator

Координирует выполнение всех stages.
Детерминированный, перезапускаемый, можно остановить в любой момент.
"""

from typing import Optional

from llama_index.embeddings.openai import OpenAIEmbedding

from infra.logger import get_logger
from infra.llm import LLMClient
from ingestor.app.storage import InMemoryStorage
from ingestor.app.llm_lock import LLMLockManager
from ingestor.app.pipeline.scan import ScanStage
from ingestor.app.pipeline.parse import ParseStage
from ingestor.app.pipeline.enrich import EnrichStage
from ingestor.app.pipeline.embed import EmbedStage
from ingestor.app.pipeline.persist import PersistStage

log = get_logger("ingestor.pipeline.orchestrator")


class PipelineOrchestrator:
    """
    Управляет выполнением ingest pipeline.
    """

    def __init__(
        self,
        workspace_path: str,
        llm: LLMClient,
        lock_manager: LLMLockManager,
        storage: InMemoryStorage,
        embed_model: Optional[OpenAIEmbedding] = None,
    ) -> None:
        self.workspace_path = workspace_path
        self.llm = llm
        self.lock_manager = lock_manager
        self.storage = storage
        
        # Инициализируем stages
        self.scan_stage = ScanStage(workspace_path)
        self.parse_stage = ParseStage()
        self.enrich_stage = EnrichStage(llm, lock_manager)
        
        # Embed model (опционально для MVP)
        if embed_model:
            self.embed_stage = EmbedStage(embed_model)
        else:
            self.embed_stage = None
        
        self.persist_stage = PersistStage(storage)

    async def run_full_pipeline(self) -> None:
        """
        Запускает полный pipeline от начала до конца.
        """
        log.info("pipeline.start", workspace=self.workspace_path)
        
        try:
            # Stage 1: Scan (NO LLM)
            log.info("pipeline.stage.scan")
            files = await self.scan_stage.run()
            
            if not files:
                log.warning("pipeline.no_files")
                return
            
            # Stage 2: Parse (NO LLM)
            log.info("pipeline.stage.parse")
            chunks = await self.parse_stage.run(files)
            
            if not chunks:
                log.warning("pipeline.no_chunks")
                return
            
            # Stage 3: Enrich (LOCAL LLM, respects lock)
            log.info("pipeline.stage.enrich")
            await self.llm.wait_ready()  # Ждём готовности LLM
            chunks = await self.enrich_stage.run(chunks)
            
            # Stage 4: Embed (optional, NO LLM reasoning)
            if self.embed_stage:
                log.info("pipeline.stage.embed")
                chunks = await self.embed_stage.run(chunks)
            else:
                log.info("pipeline.stage.embed.skipped")
            
            # Stage 5: Persist (NO LLM)
            log.info("pipeline.stage.persist")
            await self.persist_stage.run(chunks)
            
            log.info("pipeline.complete")
            
        except Exception as e:
            log.error("pipeline.failed", error=str(e), exc_info=True)
            raise

    async def run_incremental(self, file_paths: list[str]) -> None:
        """
        Инкрементальная индексация конкретных файлов.
        Для будущего использования (file watcher, CI).
        """
        log.info("pipeline.incremental.start", files_count=len(file_paths))
        # TODO: implement incremental indexing
        log.warning("pipeline.incremental.not_implemented")
