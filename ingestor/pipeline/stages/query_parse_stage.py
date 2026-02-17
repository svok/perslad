"""
Query Parse Stage

Разбивает поисковый запрос на чанки.
"""

from typing import Dict, Any
from ingestor.core.models.chunk import Chunk
from ingestor.pipeline.models.pipeline_search_context import PipelineSearchContext
from ingestor.pipeline.utils.text_splitter_helper import TextSplitterHelper
from ingestor.pipeline.base.processor_stage import ProcessorStage


class QueryParseStage(ProcessorStage):
    """
    Разбивает поисковый запрос на чанки.
    """

    def __init__(self, max_workers: int = 1, text_splitter_helper: TextSplitterHelper = None):
        super().__init__("query_parse", max_workers)
        self.helper = text_splitter_helper or TextSplitterHelper()

    async def process(self, context: PipelineSearchContext) -> PipelineSearchContext:
        """
        Вход: PipelineSearchContext с query_data
        Выход: PipelineSearchContext с chunks
        """
        query_data: Dict[str, Any] = context.query_data
        query_text = query_data.get('query', '')
        
        if not query_text:
            context.mark_error("Empty query")
            return context

        try:
            # Разбиваем запрос на чанки
            # В будущем: использовать text_splitter_helper если нужно
            # Сейчас создаем один чанк с полным текстом
            context.chunks = [
                Chunk(
                    id="query_0",
                    file_path="query",
                    content=query_text,
                    start_line=0,
                    end_line=0,
                    chunk_type="query",
                    metadata={'original_query_data': query_data}
                )
            ]
            
            # Важно: не меняем статус на success здесь,
            # пусть следующая стадия (Embed) успешно отработает и проставит
            return context
        except Exception as e:
            context.mark_error(f"Query parse error: {e}")
            return context
