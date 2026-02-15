import asyncio
from typing import List, Dict, Any, Optional
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
        
        await self._queue.put({
            'query': query,
            'top_k': top_k,
            'filter_by_file': filter_by_file
        })

    async def stop(self):
        self.log.info("QuerySourceStage stopped")

    async def generate(self):
        """Реализация абстрактного метода generate (no-op, т.к. мы используем push_query)"""
        pass
