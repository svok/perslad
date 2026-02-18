"""
Query Source Stage

Источник для поисковых запросов.
Создает PipelineSearchContext из параметров запроса.
"""

import asyncio
from typing import Dict, Any, Optional
from datetime import datetime

from ingestor.pipeline.models.pipeline_search_context import PipelineSearchContext
from ingestor.pipeline.base.source_stage import SourceStage


class QuerySourceStage(SourceStage):
    """
    Источник для поисковых запросов.
    """

    def __init__(self):
        super().__init__("query_source")
        self._queue = None

    async def start(self, output_queue):
        self._queue = output_queue
        self.log.info("QuerySourceStage started")

    async def push_query(self, query: str, top_k: int = 5, filter_by_file: Optional[str] = None):
        if not self._queue:
            raise RuntimeError("Stage not started")

        # Создаем PipelineSearchContext с обязательным query_data
        context = PipelineSearchContext(
            query_data={
                'query': query,
                'top_k': top_k,
                'filter_by_file': filter_by_file
            },
            status="pending"
        )
        context.created_at = datetime.now().timestamp()

        await self._queue.put(context)

    async def stop(self):
        self.log.info("QuerySourceStage stopped")

    async def generate(self):
        """Реализация абстрактного метода generate (no-op)"""
        pass
