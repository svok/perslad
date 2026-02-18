import asyncio
from typing import List, Optional

from ingestor.pipeline.base.base_stage import BaseStage
from ingestor.pipeline.base.queues import ThrottledQueue
from ingestor.pipeline.models.pipeline_file_context import PipelineFileContext
from ingestor.adapters import BaseStorage  # Для тип hinted, но storage передается в __init__


class IncrementalFilterStage(BaseStage):
    """
    Фильтрует PipelineFileContext, пропуская только измененные или новые файлы.
    Собирает события сканирования в батчи для эффективной проверки в БД.
    События inotify пропускает немедленно.
    """

    def __init__(self, storage, batch_size: int = 100, max_wait: float = 3.0):
        super().__init__("incremental_filter")
        self.storage: BaseStorage = storage
        self.batch_size = batch_size
        self.max_wait = max_wait
        self._buffer: List[PipelineFileContext] = []
        self._lock = asyncio.Lock()
        self._flush_event = asyncio.Event()
        self.input_queue: Optional[ThrottledQueue] = None
        self.output_queue: Optional[ThrottledQueue] = None
        self._workers: List[asyncio.Task] = []

    async def start(self, input_queue: ThrottledQueue, output_queue: Optional[ThrottledQueue] = None) -> None:
        self.input_queue = input_queue
        self.output_queue = output_queue
        self._stop_event.clear()
        self._workers = [
            asyncio.create_task(self._main_loop(), name="filter_main"),
            asyncio.create_task(self._flush_loop(), name="filter_flusher"),
        ]
        self.log.info(f"IncrementalFilterStage started: batch_size={self.batch_size}, max_wait={self.max_wait}")

    async def _main_loop(self):
        """Основной цикл обработки очереди"""
        while not self._stop_event.is_set():
            try:
                context = await self.input_queue.get()

                if context is None:
                    async with self._lock:
                        if self._buffer:
                            await self._process_and_flush()
                    if self.output_queue:
                        await self.output_queue.put(None)
                    break

                # Логика разделения: inotify - сразу, scan - в батч
                if context.event_type != "scan":
                    if self.output_queue:
                        await self.output_queue.put(context)
                    self.input_queue.task_done()
                    continue

                # Добавляем в буфер для сканирования
                async with self._lock:
                    self._buffer.append(context)
                    if len(self._buffer) >= self.batch_size:
                        self._flush_event.set()

                self.input_queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.log.error(f"Error in main loop: {e}", exc_info=True)

    async def _flush_loop(self):
        """Цикл сброса по таймауту"""
        while not self._stop_event.is_set():
            try:
                try:
                    await asyncio.wait_for(self._flush_event.wait(), timeout=self.max_wait)
                except asyncio.TimeoutError:
                    pass

                async with self._lock:
                    if self._buffer:
                        await self._process_and_flush()
                    self._flush_event.clear()

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.log.error(f"Error in flush loop: {e}", exc_info=True)

    async def _process_and_flush(self):
        """Обработка батча событий сканирования"""
        if not self._buffer:
            return

        current_batch = self._buffer
        self._buffer = []
        
        try:
            paths = [str(ctx.file_path) for ctx in current_batch]
            db_metadata = await self.storage.get_files_metadata(paths)
            
            for ctx in current_batch:
                path_str = str(ctx.file_path)
                if path_str not in db_metadata:
                    # Новый файл
                    if self.output_queue:
                        await self.output_queue.put(ctx)
                    continue
                
                db_mtime = db_metadata[path_str].get("mtime", 0)
                try:
                    if ctx.abs_path and ctx.abs_path.exists():
                        current_mtime = ctx.abs_path.stat().st_mtime
                    else:
                        current_mtime = 0
                except Exception:
                    current_mtime = 0
                
                if current_mtime > db_mtime + 0.01:
                    # Файл изменился
                    if self.output_queue:
                        await self.output_queue.put(ctx)
                else:
                    self.log.debug(f"Skipping unchanged scanned file: {path_str}")
            
            self.log.info(f"Filtered scan batch: {len(current_batch)} processed")

        except Exception as e:
            self.log.error(f"Error processing batch: {e}", exc_info=True)
            if self.output_queue:
                for ctx in current_batch:
                    await self.output_queue.put(ctx)

    async def stop(self):
        self._stop_event.set()
        for w in self._workers:
            if not w.done():
                w.cancel()
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
        self.log.info("IncrementalFilterStage stopped")
