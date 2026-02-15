import asyncio
from dataclasses import asdict, replace
from pathlib import Path
from typing import List, Optional, Any

from infra.logger import get_logger
from ingestor.pipeline.models.pipeline_context import PipelineContext
from ..indexation.queues import ThrottledQueue
from ..utils.text_splitter_helper import TextSplitterHelper


class BasePipeline:
    """
    Базовый класс для всех пайплайнов индексации и поиска.
    Содержит общую логику управления очередями, стадиями и контекстом.
    """
    DEFAULT_CONFIG = {
        'queue_size': 1000,
    }

    def __init__(self, pipeline_context: PipelineContext):
        self.log = get_logger('ingestor.pipeline')
        self.config = {**self.DEFAULT_CONFIG, **(pipeline_context.config or {})}
        self.workspace_path = pipeline_context.workspace_path

        # Общие зависимости
        self.text_splitter_helper = TextSplitterHelper()
        self._ctx = replace(
            pipeline_context,
            config=self.config,
        )

        self._queues: List[ThrottledQueue] = []
        self._processors: List[Any] = []
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None

    async def _monitor_loop(self) -> None:
        """Фоновая задача для вывода статистики"""
        self.log.debug("Queue monitor loop started")
        try:
            while self._running:
                stats = []
                for q in self._queues:
                    size = q.qsize
                    stats.append(f"{q.name}: {size}")
                self.log.info(f"[STATS] Queues: {' | '.join(stats)}")
                await asyncio.sleep(10)
        except asyncio.CancelledError:
            self.log.debug("Queue monitor loop cancelled")
        except Exception as e:
            self.log.error(f"Monitor error: {e}")

    async def stop(self) -> None:
        if not self._running: return
        self._running = False

        if self._monitor_task:
            self._monitor_task.cancel()

        for proc in self._processors:
            await proc.stop()

        self.log.info(f"{self.__class__.__name__} stopped")
