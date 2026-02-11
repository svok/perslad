from typing import List, Dict, Any
from ingestor.core.models.chunk import Chunk
from ingestor.pipeline.utils.text_splitter_helper import TextSplitterHelper
from ingestor.pipeline.base.processor_stage import ProcessorStage

class QueryParseStage(ProcessorStage):
    """
    Разбивает поисковый запрос на чанки, используя ту же логику, что и для файлов.
    """
    def __init__(self, max_workers: int = 1, text_splitter_helper: TextSplitterHelper = None):
        super().__init__("query_parse", max_workers)
        self.helper = text_splitter_helper or TextSplitterHelper()

    async def process(self, query_data: Dict[str, Any]) -> List[Chunk]:
        """
        Вход: {'query': str, 'top_k': int, 'filter_by_file': Optional[str]}
        Выход: Список объектов Chunk (без ID, т.к. это временные объекты для эмбеддинга)
        """
        query_text = query_data.get('query', '')
        if not query_text:
            return []

        try:
            # Используем логику разбивки из хелпера
            chunks_text = self.helper.split_query_by_sentences(query_text, max_chars=2000)
            
            chunks = []
            for i, text in enumerate(chunks_text):
                # Создаем временный Chunk для совместимости с EmbedChunksStage
                chunk = Chunk(
                    id=f"query_{i}",
                    file_path="query",
                    content=text,
                    start_line=0,
                    end_line=0,
                    chunk_type="query",
                    metadata={'original_query_data': query_data}
                )
                chunks.append(chunk)
            
            return chunks
        except Exception as e:
            self.log.error(f"Query parse error: {e}", exc_info=True)
            return []
