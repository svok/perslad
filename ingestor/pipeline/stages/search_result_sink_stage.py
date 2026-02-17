"""
Search Result Sink Stage

Сборщик результатов поиска.
Принимает PipelineSearchContext и извлекает results.
"""

import asyncio
from typing import List, Dict, Any, Optional
from ingestor.pipeline.base.sink_stage import SinkStage
from ingestor.pipeline.models.pipeline_search_context import PipelineSearchContext


class SearchResultSinkStage(SinkStage):
    """
    Сборщик результатов поиска.
    """

    def __init__(self):
        super().__init__("search_sink")
        self._results: List[Dict[str, Any]] = []
        self._future: Optional[asyncio.Future] = None

    def set_future(self, future: asyncio.Future):
        self._future = future
        self._results = []

    # Принимаем PipelineSearchContext вместо List[Dict]
    async def process(self, context: PipelineSearchContext) -> None:
        # Извлекаем результаты из контекста
        if context.result:
            self._results.extend(context.result)

        # Сигнал о завершении
        if self._future and not self._future.done():
            self._future.set_result(self._results)

    async def consume(self, context):
        """Реализация абстрактного метода consume"""
        await self.process(context)

    async def get_results(self) -> List[Dict[str, Any]]:
        return self._results
