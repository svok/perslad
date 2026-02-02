"""
Indexer Orchestrator

Координатор инкрементальной индексации
"""

import asyncio
import logging
from typing import List

from infra.llm import LLMClient
from ingestor.adapters.base_storage import BaseStorage
from ingestor.app.knowledge_port import KnowledgePort
from ingestor.app.llm_lock import LLMLockManager
from ingestor.app.pipeline.embed import EmbedStage
from ingestor.app.pipeline.enrich import EnrichStage
from ingestor.app.pipeline.parse import ParseStage
from ingestor.app.pipeline.persist import PersistStage
from ingestor.app.storage import FileSummary
from ingestor.app.watchers import FileScannerSource, FileNotifierSource

log = logging.getLogger("ingestor.indexer")


class IndexerOrchestrator:
    """
    Координирует:
    - Full workspace scan при старте
    - Runtime file watching
    - Индексацию изменившихся файлов
    """

    def __init__(
        self,
        workspace_path: str,
        llm: LLMClient,
        lock_manager: LLMLockManager,
        storage: BaseStorage,
        knowledge_port: KnowledgePort,
        embed_url: str = "http://emb:8001/v1",
        embed_api_key: str = "sk-dummy",
    ) -> None:
        self.workspace_path = workspace_path
        self.llm = llm
        self.lock_manager = lock_manager
        self.storage = storage
        self.knowledge_port = knowledge_port

        self.embed_stage = EmbedStage(embed_url, embed_api_key)
        self.enrich_stage = EnrichStage(llm, lock_manager)
        self.scan_stage = ParseStage()
        self.persist_stage = PersistStage(storage)

        self._running = False
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Запускает инкрементальный indexer"""
        log.info("indexer.starting", workspace=self.workspace_path)

        async with self._lock:
            if self._running:
                log.warning("indexer already running")
                return

            self._running = True

        # Стартуем наблюдатель
        self._notifier = FileNotifierSource(
            workspace_path=self.workspace_path,
            storage=self.storage,
            on_file_event=self._handle_file_event
        )

        asyncio.create_task(self._notifier.start())

        # Стартуем сканер (запустится при необходимости)
        self._scanner = None

        log.info("indexer.started")

    async def start_full_scan(self) -> None:
        """Запускает полный скан при старте"""
        log.info("indexer.starting_full_scan")

        self._scanner = FileScannerSource(
            workspace_path=self.workspace_path,
            storage=self.storage,
            on_files_changed=self._handle_files_changed
        )

        await self._scanner.start()

    async def _handle_file_event(self, file_path: str, event_type: str) -> None:
        """
        Обрабатывает события от нотификатора
        """
        try:
            log.debug("indexer.event", file=file_path, event=event_type)

            # TODO: Обновлять метаданные в БД
            # await self.storage.update_file_metadata(file_path, ..., ...)

            if event_type == "delete":
                await self._handle_delete(file_path)
            elif event_type == "create":
                await self._handle_create(file_path)
            elif event_type == "rename":
                await self._handle_rename(file_path)

        except Exception as e:
            log.error("indexer.event.failed", file=file_path, error=str(e), exc_info=True)

    async def _handle_files_changed(self, files: List[FileSummary]) -> None:
        """
        Обрабатывает список файлов из сканера
        """
        try:
            log.info("indexer.files_changed", count=len(files))
            await self._index_files(files)
        except Exception as e:
            log.error("indexer.files_changed.failed", error=str(e), exc_info=True)

    async def _handle_create(self, file_path: str) -> None:
        """Обрабатывает создание файла"""
        log.info("indexer.create", file=file_path)

        await self._index_single_file(file_path)

    async def _handle_delete(self, file_path: str) -> None:
        """Обрабатывает удаление файла"""
        log.info("indexer.delete", file=file_path)

        try:
            # TODO: Удалить из БД
            await self.storage.delete_chunks_by_file_paths([file_path])
            await self.storage.delete_file_summaries([file_path])
        except Exception as e:
            log.error("indexer.delete.failed", file=file_path, error=str(e), exc_info=True)

    async def _handle_rename(self, file_path: str) -> None:
        """Обрабатывает переименование файла"""
        log.info("indexer.rename", file=file_path)

        # TODO: Обновить пути в БД
        # Это сложная операция - нужно найти все чанки с путями, содержащими old_path
        pass

    async def _index_files(self, files: List[FileSummary]) -> None:
        """Индексирует список файлов"""
        for file in files:
            await self._index_single_file(file.file_path)

    async def _index_single_file(self, file_path: str) -> None:
        """Индексирует один файл"""
        try:
            file_path_obj = Path(self.workspace_path) / file_path
            if not file_path_obj.exists():
                log.warning("indexer.file_not_found", file=file_path)
                return

            # Обновляем метаданные
            await self.storage.update_file_metadata(
                file_path,
                file_path_obj.stat().st_mtime,
                self._calculate_checksum(file_path_obj)
            )

            # Парсим файл
            chunks = await self.scan_stage.run([file_path_obj])
            if not chunks:
                log.warning("indexer.no_chunks", file=file_path)
                return

            # Enrich и Embed
            enriched_chunks = await self.enrich_stage.run(chunks)
            await self.embed_stage.run(enriched_chunks)

            # Persist
            await self.persist_stage.run(enriched_chunks)

            log.info("indexer.indexed", file=file_path, chunks=len(enriched_chunks))

        except Exception as e:
            log.error("indexer.index_failed", file=file_path, error=str(e), exc_info=True)

    def _calculate_checksum(self, file_path: Path) -> str:
        """Расчитывает MD5"""
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
        """Останавливает indexer"""
        async with self._lock:
            if not self._running:
                return

            self._running = False
            log.info("indexer.stopping")

        # Останавливаем watcher
        if hasattr(self, '_notifier') and self._notifier:
            await self._notifier.stop()

        log.info("indexer.stopped")

    async def wait_closed(self) -> None:
        """Ждет остановки"""
        await self.stop()
