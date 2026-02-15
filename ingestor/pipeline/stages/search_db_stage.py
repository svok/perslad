from typing import List, Dict, Any
from ingestor.core.models.chunk import Chunk
from ingestor.pipeline.base.processor_stage import ProcessorStage

class SearchDBStage(ProcessorStage):
    """
    Выполняет векторный поиск в БД на основе эмбеддингов чанков запроса.
    """
    def __init__(self, storage, max_workers: int = 2):
        super().__init__("search_db", max_workers)
        self.storage = storage

    async def process(self, chunks: List[Chunk]) -> List[Dict[str, Any]]:
        """
        Вход: Список чанков с эмбеддингами
        Выход: Список найденных результатов из БД
        """
        if not chunks:
            return []

        all_results = []
        try:
            for chunk in chunks:
                if chunk.embedding is None:
                    continue
                
                # Извлекаем параметры поиска из метаданных (проброшены из QueryParseStage)
                query_data = chunk.metadata.get('original_query_data', {})
                top_k = query_data.get('top_k', 5)
                filter_by_file = query_data.get('filter_by_file')

                # Нативный поиск в БД
                db_results = await self.storage.search_vector(
                    chunk.embedding,
                    top_k=top_k,
                    filter_by_file=filter_by_file
                )

                for res in db_results:
                    all_results.append({
                        "chunk_id": res.id,
                        "file_path": res.file_path,
                        "content": res.content,
                        "summary": res.summary,
                        "purpose": res.purpose,
                        "similarity": 0, # В будущем можно прокинуть score
                        "metadata": res.metadata,
                        "chunk_type": res.chunk_type,
                        "query_chunk": chunk.content
                    })
            
            return all_results
        except Exception as e:
            self.log.error(f"DB Search error: {e}", exc_info=True)
            return []
