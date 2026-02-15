"""
Knowledge Search Pipeline - Pipeline for searching indexed knowledge using stages and queues.
"""

import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional

from ingestor.core.ports.storage import BaseStorage
from ingestor.pipeline.base.base_pipeline import BasePipeline
from ingestor.pipeline.indexation.queues import ThrottledQueue
from .builder import KnowledgeSearchPipelineBuilder
from ..models.pipeline_context import PipelineContext
from ..stages.query_source_stage import QuerySourceStage
from ..stages.search_result_sink_stage import SearchResultSinkStage


class KnowledgeSearchPipeline(BasePipeline):
    """
    Пайплайн поиска знаний, построенный на тех же принципах, что и индексация.
    Использует стадии: QueryParse -> Embed -> SearchDB -> Sink
    """

    def __init__(
        self,
        pipeline_context: PipelineContext,
    ):
        super().__init__(pipeline_context)
        
        self._stage_defs = KnowledgeSearchPipelineBuilder.get_default_definitions()
        self._source = QuerySourceStage()
        self._sink = SearchResultSinkStage()

    async def start(self) -> None:
        if self._running: return
        self._running = True

        # 1. Создаем очереди
        num_queues = len(self._stage_defs) + 1
        self._queues = [ThrottledQueue(self.config['queue_size'], name=f"search_q_{i}") for i in range(num_queues)]

        # 2. Строим стадии через фабрики
        for i, defn in enumerate(self._stage_defs):
            stage = defn.factory(self._ctx)
            await stage.start(self._queues[i], self._queues[i+1])
            self._processors.append(stage)

        # 3. Source & Sink
        await self._source.start(self._queues[0])
        await self._sink.start(self._queues[-1])

        # 4. Мониторинг
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        self.log.info("KnowledgeSearchPipeline started with stages")

    async def search(
        self,
        query: str,
        top_k: int = 10,
        filter_by_file: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Выполняет поиск, прогоняя запрос через все стадии пайплайна.
        """
        if not self._running:
            await self.start()

        # Создаем Future для ожидания результата в Sink
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        self._sink.set_future(future)

        # Пушим запрос в начало пайплайна
        await self._source.push_query(query, top_k, filter_by_file)

        # Ждем результат из Sink
        try:
            raw_results = await asyncio.wait_for(future, timeout=30.0)
            ranked = await self._rank_and_deduplicate(raw_results, top_k)
            
            return {
                "results": ranked,
                "status": "success"
            }
        except asyncio.TimeoutError:
            self.log.error("Search pipeline timeout")
            return {"results": [], "error": "timeout"}

    async def _rank_and_deduplicate(
        self,
        results: List[Dict[str, Any]],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """
        Ранжирование и дедупликация (по файлам).
        """
        if not results:
            return []
        
        dedup_dict = {}
        for result in results:
            file_path = result["file_path"]
            if file_path not in dedup_dict:
                dedup_dict[file_path] = result
        
        ranked_results = list(dedup_dict.values())
        return ranked_results[:top_k]

    async def stop(self) -> None:
        if self._source: await self._source.stop()
        if self._sink: await self._sink.stop()
        await super().stop()
