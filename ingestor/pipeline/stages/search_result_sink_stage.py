import asyncio
from typing import List, Dict, Any, Optional
from ingestor.pipeline.base.sink_stage import SinkStage

class SearchResultSinkStage(SinkStage):
    """
    Сборщик результатов поиска.
    """
    def __init__(self):
        super().__init__("search_sink")
        self._results = []
        self._future = None

    def set_future(self, future: asyncio.Future):
        self._future = future
        self._results = []

    async def process(self, results: List[Dict[str, Any]]) -> None:
        if results:
            self._results.extend(results)
        
        # Сигнал о завершении (в контексте поиска мы обычно ждем один пакет)
        if self._future and not self._future.done():
            self._future.set_result(self._results)

    async def consume(self, results):
        """Реализация абстрактного метода consume"""
        await self.process(results)

    async def get_results(self) -> List[Dict[str, Any]]:
        return self._results
