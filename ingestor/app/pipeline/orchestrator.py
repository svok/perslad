"""
Pipeline Orchestrator

Координирует выполнение всех stages.
Детерминированный, перезапускаемый, можно остановить в любой момент.
"""

import asyncio

from infra.llm import LLMClient
from infra.logger import get_logger
from ingestor.core.ports.storage import BaseStorage
from ingestor.app.llm_lock import LLMLockManager
from ingestor.app.pipeline.embed import EmbedStage
from ingestor.app.pipeline.enrich import EnrichStage
from ingestor.app.pipeline.parse import ParseStage
from ingestor.app.pipeline.persist import PersistStage
from ingestor.app.pipeline.scan import ScanStage
from ingestor.app.pipeline.workers.collector import EnrichCollector
from ingestor.app.pipeline.workers.consumers import PipelineConsumers

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
        storage: BaseStorage,
        embed_url: str = "http://emb:8001/v1",
        embed_api_key: str = "sk-dummy",
    ) -> None:
        self.workspace_path = workspace_path
        self.llm = llm
        self.lock_manager = lock_manager
        self.storage = storage

        # Инициализируем stages
        self.scan_stage = ScanStage(workspace_path)
        self.parse_stage = ParseStage()
        self.enrich_stage = EnrichStage(llm, lock_manager)
        self.embed_stage = EmbedStage(embed_url, embed_api_key)
        self.persist_stage = PersistStage(storage)
        
        # Инициализируем consumers helper
        self.consumers = PipelineConsumers(
            self.parse_stage, 
            self.enrich_stage, 
            self.embed_stage
        )

    async def run_full_pipeline(self) -> None:
        """
        Запускает полный pipeline от начала до конца.
        """
        log.info("pipeline.start", workspace=self.workspace_path)

        try:
            files_queue = asyncio.Queue(maxsize=100)
            enriched_queue = asyncio.Queue(maxsize=100)
            embedded_queue = asyncio.Queue(maxsize=100)

            collector = EnrichCollector(self.storage, max_buffer=100, debounce=1.0)

            log.info("pipeline.tasks.created")

            scan_task = asyncio.create_task(self._scan_producer(files_queue))
            parse_enrich_task = asyncio.create_task(
                self.consumers.parse_enrich_consumer(files_queue, enriched_queue)
            )
            embed_task = asyncio.create_task(
                self.consumers.embed_consumer(enriched_queue, embedded_queue)
            )
            save_task = asyncio.create_task(
                self.consumers.save_consumer(embedded_queue, collector)
            )

            log.info("pipeline.tasks.running")
            await scan_task
            log.info("pipeline.task.scan.complete")

            await parse_enrich_task
            log.info("pipeline.task.parse_enrich.complete")

            await embed_task
            log.info("pipeline.task.embed.complete")

            await save_task
            log.info("pipeline.task.save.complete")

            log.info("pipeline.complete")

        except Exception as e:
            log.error("pipeline.failed", error=str(e), exc_info=True)
            raise

    async def _scan_producer(self, files_queue: asyncio.Queue) -> None:
        log.info("scan_producer.starting")
        files = await self.scan_stage.run()
        log.info("scan_producer.finished", files_count=len(files))

        for file in files:
            await files_queue.put(file)
            
        log.info("scan_producer.all_files_sent")
        log.info("scan_producer.preparing_sentinel")
        await files_queue.put(None)
        log.info("scan_producer.sentinel_sent")

    async def run_incremental(self, file_paths: list[str]) -> None:
        """
        Инкрементальная индексация конкретных файлов.
        Для будущего использования (file watcher, CI).
        """
        log.info("pipeline.incremental.start", files_count=len(file_paths))
        # TODO: implement incremental indexing
        log.warning("pipeline.incremental.not_implemented")
