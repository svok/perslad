# ПЛАН РЕФАКТОРИНГА: переход на llama_index (Финальная версия)

## КРИТИЧЕСКОЕ ПРЕДУПРЕЖДЕНИЕ

**Перед началом миграции необходимо выполнить Фазу 0 (Экстренные исправления)**. Эти задачи исправляют опасные проблемы в текущем коде:

- **HTTP client per request** → socket exhaustion风险
- **Нет retry на embedding** → lost data при transient errors
- **Нет rate limiting** → API throttling в production
- **O(n) vector search** → не масштабируется за 1000+ chunks
- **KeyError risks** → runtime crashes
- **Безымянные except** → silent failures
- **Config scattering** → maintenance nightmare

Без Фазы 0 система **непригодна для production**. Выполняем сразу.

---

## Целевое состояние

Полностью заменить кастомную логику индексации и поиска на компоненты llama_index:

- **VectorStore**: PGVectorVectorStore (PostgreSQL) + FaissVectorStore (memory)
- **Index**: VectorStoreIndex для управления индексом
- **Retrieval**: VectorIndexRetriever для поиска
- **LLM/Embeddings**: Стандартные адаптеры llama_index с retry, rate limit, circuit breaker
- **Pipeline**: Упрощенный пайплайн, эффективный асинхронный батчинг

**Оставить кастомный код только для**:
- Файлового сканирования и inotify (специфичная логика ОС)
- Управления очередями и параллелизацией (если needed)
- FileSummary хранение (не-векторные операции)

---

## ПРИНЦИПЫ РЕФАКТОРИНГА

1. **DRY**: Удалять устаревший код сразу после замены, не оставлять дубли
2. **Работоспособность**: После каждой задачи система должна проходить тесты и работать
3. **Безопасность**: Сохранять логику переподключений из `infra.managers.base.BaseManager`
4. **Производительность**: Не ухудшать latency и throughput (должна улучшиться)
5. **Тестируемость**: Добавлять tests параллельно с кодом

---

## ФАЗА 0: Экстренные исправления (BEFORE MIGRATION)

Эти задачи **обязательны** и должны быть выполнены до основной миграции. Они стабилизируют текущую систему.

### Задача 0.1: Добавить shared HTTP client в EmbeddingModel
**Файл**: `adapters/embedding_model.py`
**Проблема**: Создает новый `AsyncClient` на КАЖДЫЙ запрос (строки 55, 97, 173) → socket exhaustion
**Действие**:
```python
class EmbeddingModel:
    def __init__(self, embed_url: str, api_key: str, served_model_name: str):
        self._client = httpx.AsyncClient(timeout=30.0)  # ← добавить
        # ... остальные поля
    
    async def close(self):
        await self._client.aclose()  # ← добавить
```
И использовать `self._client` во всех методах вместо `async with httpx.AsyncClient(...)`.
**Проверка**: Один клиент используется для множества запросов, соединения пулятся.

### Задача 0.2: Добавить retry с экспоненциальной задержкой в EmbeddingModel
**Файл**: `adapters/embedding_model.py`
**Проблема**: Нет retry при временных сбоях (502, 503, network timeouts)
**Действие**: Использовать `tenacity` (уже есть в `postgres/connection.py:40-44`)
```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception(lambda e: isinstance(e, (httpx.HTTPError, TimeoutError)))
)
async def get_embedding(self, text: str): ...
```
Применить ко всем HTTP методам: `get_embedding()`, `get_embeddings()`, `get_embedding_dimension()`
**Проверка**: Temporary failures автоматически ретраятся, не падает пайплайн

### Задача 0.3: Добавить rate limiting для embedding API
**Файл**: `config/emb.py`
**Действие**: Добавить `EMB_RATE_LIMIT_RPM: int = 100` (или из .env)
**Файл**: `adapters/embedding_model.py`
```python
from asyncio import Semaphore

def __init__(self, ...):
    self._rate_limiter = Semaphore(emb_config.EMB_RATE_LIMIT_RPM // 60)
    
async def get_embeddings(self, texts: List[str]):
    async with self._rate_limiter:  # ← ограничиваем
        # ... HTTP запрос
```
**Проверка**: Не превышает лимит даже при высокой нагрузке

### Задача 0.4: Исправить KeyError risks в builder'ах
**Файлы**:
- `pipeline/indexation/builder.py` (строки 22,27,33,40,46,53,58)
- `pipeline/knowledge_search/builder.py` (строки 19,26,34)
**Проблема**: `ctx.config["enrich_workers"]` упадет если ключ отсутствует
**Действие**: Заменить все на `.get()` с дефолтами:
```python
factory=lambda ctx: EnrichStage(
    ctx.workspace_path,
    ctx.config.get("enrich_workers", 2)  # ← безопасно
)
```
**Проверка**: При старте без конфига пайплайн использует default values

### Задача 0.5: Добавить close() вызовы в main.py
**Файл**: `main.py`
**Проблема**: `EmbeddingModel` и другие адаптеры не закрываются → утечки соединений
**Действие**: В `finally` блоке или graceful shutdown:
```python
try:
    await app.run()
finally:
    await embed_model.close()
    await llm_manager.close()
    await storage.close()
```
**Проверка**: Все AsyncClient и connection pools корректно закрываются

### Задача 0.6: Убрать bare except: везде
**Файлы**:
- `pipeline/stages/inotify_source.py:115`
- `pipeline/stages/incremental_filter_stage.py:118`
- другие места с `except:`
**Действие**: Заменить на конкретные исключения или `except Exception as e:` с логированием
**Проверка**: Нет "TypeError: catching classes that do not inherit from BaseException"

### Задача 0.7: Вынести все hard-coded значения в конфиг
**Файлы**:
- `pipeline/indexation/builder.py:22` (batch_size=100, max_wait=3.0)
- `pipeline/indexation/pipeline.py:17-18` (worker counts)
- `knowledge_search/pipeline.py:76` (timeout=30.0)
- `embedding_model.py:91` (MAX_CHARS=8000), `:141` (batch_size=10)
- `postgres/connection.py:66` (pool min=2, max=10)
**Действие**: Добавить соответствующие поля в конфиг-файлы с default values
**Проверка**: Все tuning параметры настраиваются через env/config, не через код

### Задача 0.8: Исправить PGVECTOR_DIMENSIONS hack
**Файл**: `config/storage.py:17`
**Проблема**: Comment: "The number MUST differ from real to track possible errors" - опасная практика
**Действие**: 
- Либо удалить и использовать реальную dim (1536)
- Либо сделать `Optional[int] = None` и автоопределение
**Проверка**: DimensionValidator сопоставляет dim корректно

### Задача 0.9: Создать единую конфигурационную модель
**Файлы**: `config/base.py` (новый), обновить `config/llm.py`, `config/emb.py`, `config/storage.py`, `config/runtime.py`
**Действие**:
```python
# config/base.py
from pydantic import BaseModel, Field
from typing import Optional

class BaseServiceConfig(BaseModel):
    url: str
    api_key: str | None = None
    model_name: str | None = None
    timeout: float = 30.0
    batch_size: int = 10
    max_workers: int = 2

class LLMConfig(BaseServiceConfig):
    temperature: float = 0.1
    max_retries: int = 2

class EmbeddingConfig(BaseServiceConfig):
    rate_limit_rpm: int = 100
    max_chars: int = 8000

class StorageConfig(BaseServiceConfig):
    type: str = "postgres"  # or "memory"
    vector_dim: Optional[int] = None  # auto-detect if None

# объединить в один PipelineConfig
class PipelineConfig(BaseModel):
    llm: LLMConfig
    embedding: EmbeddingConfig
    storage: StorageConfig
    enrich_workers: int = 2
    parse_workers: int = 1
    indexing_workers: int = 2
    queue_size: int = 1000
```
**Проверка**: Конфиг валидируется при старте, типизирован

### Задача 0.10: Добавить missing get_embedding_dimension в BaseStorage интерфейс
**Файл**: `core/ports/storage.py`
**Проблема**: Уже есть метод (line 131-133), но `services/validator.py:49` использует `hasattr()` вместо строгого интерфейса. Это указывает на плохое adherence.
**Действие**: Удалить `hasattr` check в `validator.py`, полагаться на abstract method
**Проверка**: Все storage implementations имеют `get_embedding_dimension()`

---

## ФАЗА 1: Векторное хранилище на llama_index (КРИТИЧЕСКАЯ МИГРАЦИЯ)

**Цель**: Удалить кастомный векторный поиск (O(n) linear scan) и заменить на `VectorStore` с HNSW indexing.

### Задача 1.1: Добавить зависимости llama_index vector stores
**Файл**: `requirements.txt`
**Действие**: Добавить
```
llama-index-vector-stores-postgres>=0.1.4
llama-index-vector-stores-simple>=0.1.4  # for memory (faiss/annoy)
```
**Проверка**: `pip install -r requirements.txt` успешно

### Задача 1.2: Создать VectorStoreAdapter с retry
**Файл**: `adapters/vector_store.py` (новый)
**Действие**:
```python
from llama_index.core.vector_stores import VectorStore, VectorStoreQuery, VectorStoreQueryResult
from llama_index.core.schema import TextNode
from tenacity import retry, wait_exponential, stop_after_attempt

class LlamaPostgresVectorStore(VectorStore):
    """Adapter over PGVectorVectorStore with retry logic."""
    
    def __init__(self, connection_string: str, table_name: str = "chunks"):
        from llama_index.vector_stores.postgres import PGVectorStore
        self._store = PGVectorStore(
            connection_string=connection_string,
            table_name=table_name,
            embed_dim=1536,  # from config
        )
    
    @retry(wait=wait_exponential(min=2, max=30), stop=stop_after_attempt(3))
    async def add_nodes(self, nodes: list[TextNode]) -> list[str]:
        return await self._store.async_add(nodes)
    
    @retry(wait=wait_exponential(min=2, max=30), stop=stop_after_attempt(3))
    async def query(self, query: VectorStoreQuery) -> VectorStoreQueryResult:
        return await self._store.async_query(query)
    
    # ... другие методы: delete, get, etc.
```
**Проверка**: Может добавлять узлы и делать векторный поиск с retry

### Задача 1.3: Создать InMemoryVectorStore с Faiss
**Файл**: `adapters/vector_store.py` (дополняем)
**Действие**:
```python
from llama_index.vector_stores.simple import SimpleVectorStore

class LlamaMemoryVectorStore(VectorStore):
    """In-memory vector store using Faiss/HNSW for O(log n) search."""
    
    def __init__(self):
        self._store = SimpleVectorStore()
    
    async def add_nodes(self, nodes: list[TextNode]) -> list[str]:
        return self._store.add(nodes)
    
    async def query(self, query: VectorStoreQuery) -> VectorStoreQueryResult:
        return self._store.query(query)
```
**Проверка**: Поиск по 10,000 chunks выполняется за <10ms (вместо 50-200ms)

### Задача 1.4: Удалить кастомный векторный поиск из PostgreSQLStorage
**Файлы**:
- `adapters/postgres/repositories/chunk.py` → удалить метод `search_vector()` (строки 120-146)
- `adapters/postgres/storage.py` → удалить метод `search_vector()` (строки 63-69)
**Действие**: Векторный поиск теперь через VectorStoreAdapter
**Проверка**: Компиляция проходит, storage методы search_vector пока не используются

### Задача 1.5: Обновить PostgreSQLStorage как фасад
**Файл**: `adapters/postgres/storage.py`
**Действие**:
```python
class PostgreSQLStorage(BaseStorage):
    def __init__(self, connection_string: str, operation_timeout: float = 60.0):
        self._conn = PostgresConnection(operation_timeout)
        self._vector_store = LlamaPostgresVectorStore(connection_string)
        # файловые summaries остаются через репозитории (не-векторные)
    
    async def search_vector(self, vector, top_k=10, filter_by_file=None):
        from llama_index.core.vector_stores import FilterOperator, Filter
        filters = None
        if filter_by_file:
            filters = Filter.from_dict({"file_path": {"$eq": filter_by_file}})
        
        query = VectorStoreQuery(
            query_embedding=vector,
            similarity_top_k=top_k,
            filters=filters,
        )
        result = await self._vector_store.query(query)
        # Конвертация VectorStoreNode → Chunk
        return [self._node_to_chunk(node) for node in result.nodes]
```
**Проверка**: search_vector возвращает те же данные, что и раньше (или лучше с фильтрацией)

### Задача 1.6: Удалить ChunkRepository полностью
**Файлы**:
- `adapters/postgres/repositories/chunk.py` - УДАЛИТЬ ВЕСЬ ФАЙЛ
- `adapters/postgres/storage.py`: удалить импорт и использование `ChunkRepository`
- `adapters/postgres/mappers.py`: удалить или упростить (оставить только для FileSummary/ModuleSummary если нужно)
**Действие**: Все CRUD для chunks теперь через `vector_store.add_nodes()` и `vector_store.delete()`
**Проверка**: Ни один файл не импортирует ChunkRepository

### Задача 1.7: Упростить MemoryStorage
**Файл**: `adapters/memory/storage.py`
**Действие**:
- Удалить метод `search_vector` (весь векторный поиск, строки 145-176)
- Оставить только `save_chunk`, `save_chunks`, `get_chunk`, `get_chunks_by_file` для совместимости (или удалить если не используются)
- Или заменить на `LlamaMemoryVectorStore` прокси
**Проверка**: Тесты (если есть) проходят

---

## ФАЗА 2: Перепроектирование пайплайна индексации

**Цель**: Убрать EmbedChunksStage и PersistChunksStage, заменить на IndexingStage с авто-эмбеддингом.

### Задача 2.1: Создать LlamaEmbedding adapter с retry и rate limiting
**Файл**: `adapters/embeddings.py` (новый)
**Действие**:
```python
from llama_index.core.embeddings import BaseEmbedding
from llama_index.embeddings.openai import OpenAIEmbedding
from tenacity import retry, wait_exponential, stop_after_attempt

class LlamaEmbedding(BaseEmbedding):
    """Embedding adapter with retry and rate limiting."""
    
    def __init__(self, config: EmbeddingConfig):
        self._config = config
        self._rate_limiter = asyncio.Semaphore(config.rate_limit_rpm // 60)
        self._embedder = OpenAIEmbedding(
            api_base=config.url,
            api_key=config.api_key,
            model_name=config.model_name,
        )
    
    @retry(wait=wait_exponential(min=2, max=30), stop=stop_after_attempt(3))
    async def _get_text_embedding(self, text: str) -> List[float]:
        async with self._rate_limiter:
            return await self._embedder.aget_text_embedding(text)
    
    @retry(wait=wait_exponential(min=2, max=30), stop=stop_after_attempt(3))
    async def _get_query_embedding(self, query: str) -> List[float]:
        async with self._rate_limiter:
            return await self._embedder.aget_query_embedding(query)
```
**Проверка**: Генерация эмбеддингов с теми же параметрами, что и старый EmbeddingModel

### Задача 2.2: Удалить старый EmbeddingModel
**Файл**: `adapters/embedding_model.py` - УДАЛИТЬ
**Файлы** для обновления импортов:
- `main.py`, `services/validator.py`, `pipeline/stages/` - заменить импорты
**Действие**: Во всех местах использовать `LlamaEmbedding`
**Проверка**: Никаких `from adapters.embedding_model import EmbeddingModel` не осталось

### Задача 2.3: Удалить EmbedChunksStage
**Файлы**:
- `pipeline/stages/embed_chunks_stage.py` - УДАЛИТЬ
- `pipeline/indexation/builder.py` - удалить стадию `embed`
**Действие**: Эмбеддинги генерируются автоматически при `vector_store.add_nodes()` если передан embed_model
**Проверка**: Пайтелайн без embed стадии компилируется (пока без эмбеддингов в БД)

### Задача 2.4: Обновить ParseProcessorStage для TextNode
**Файл**: `pipeline/stages/parse_stage.py`
**Действие**:
```python
from llama_index.core.schema import TextNode

async def process(self, context: PipelineFileContext) -> PipelineFileContext:
    # ... чтение файла
    nodes = splitter.get_nodes_from_documents([Document(text=content, metadata={"file_path": rel_path})])
    
    context.nodes = []
    for node in nodes:
        # enrich node metadata
        node.metadata["file_path"] = rel_path
        node.metadata["extension"] = ext
        # node.id будет автоматически сгенерирован в vector_store
        context.nodes.append(node)
    
    return context
```
**Проверка**: Stage возвращает `List[TextNode]` с правильной metadata

### Задача 2.5: Обновить EnrichChunksStage для TextNode
**Файл**: `pipeline/stages/enrich_chunks_stage.py`
**Действие**:
```python
from llama_index.core.llms import LLM
from pydantic import BaseModel, Field

class EnrichmentResult(BaseModel):
    summary: str = Field(..., description="1-2 sentences")
    purpose: str = Field(..., description="code purpose")

class EnrichChunksStage(ProcessorStage):
    def __init__(self, llm: LLM, lock_manager: LLMLockManager, max_workers: int = 2):
        super().__init__("chunk_enrich", max_workers)
        self.llm = llm
        self.lock_manager = lock_manager
    
    async def process(self, context: PipelineFileContext) -> PipelineFileContext:
        if context.status != "success" or not context.nodes:
            return context
        
        await self._enrich_nodes(context.nodes)
        return context
    
    async def _enrich_nodes(self, nodes: List[TextNode]) -> None:
        if await self.lock_manager.is_locked():
            await self.lock_manager.wait_unlocked()
        
        tasks = [self._enrich_node(node) for node in nodes]
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _enrich_node(self, node: TextNode) -> None:
        prompt = f"""..."""  # как раньше
        try:
            result = await self.llm.astructured_predict(
                EnrichmentResult,
                prompt  # или использовать chat с JSON mode
            )
            node.metadata["summary"] = result.summary
            node.metadata["purpose"] = result.purpose
        except Exception as e:
            self.log.error("enrich.failed", node_id=node.node_id, error=str(e))
```
**Проверка**: Nodes получают enrichment в metadata без кастомного парсинга

### Задача 2.6: Создать IndexingStage
**Файл**: `pipeline/stages/indexing_stage.py` (новый)
**Действие**:
```python
class IndexingStage(ProcessorStage):
    def __init__(self, vector_store: VectorStore, embed_model: BaseEmbedding, batch_size: int = 100, max_workers: int = 2):
        super().__init__("indexing", max_workers)
        self.vector_store = vector_store
        self.embed_model = embed_model
        self.batch_size = batch_size
    
    async def process(self, context: PipelineFileContext) -> PipelineFileContext:
        if context.status != "success" or not context.nodes:
            return context
        
        # Басе ritmis: удалить старые ноды для этого файла (если нужно)
        # await self._delete_existing_nodes(context.nodes)
        
        # Добавить nodes батчами
        for i in range(0, len(context.nodes), self.batch_size):
            batch = context.nodes[i:i+self.batch_size]
            try:
                # Embeddings добавятся автоматически если vector_store имеет embed_model
                node_ids = await self.vector_store.add_nodes(batch)
                self.log.info("indexing.batch.success", count=len(batch), first_id=node_ids[0] if node_ids else None)
            except Exception as e:
                self.log.error("indexing.batch.failed", batch_start=i, error=str(e))
                #Decision: fail-fast или continue?
                raise  # fail-fast
        
        return context
```
**Проверка**: Nodes сохраняются в vector store с эмбеддингами

### Задача 2.7: Удалить PersistChunksStage и FileSummaryStage
**Файлы**:
- `pipeline/stages/persist_stage.py` - УДАЛИТЬ
- `pipeline/stages/file_summary_stage.py` - УДАЛИТЬ
**Файл**: `pipeline/indexation/builder.py` - удалить эти стадии
**Действие**: FileSummary сохранять отдельно (не в пайплайне). Можно создать background task или отдельный пайплайн.
**Проверка**: Индексация работает без этих стадий

### Задача 2.8: Перестроить IndexationPipelineBuilder
**Файл**: `pipeline/indexation/builder.py`
**Новый порядок**:
1. `IncrementalFilterStage` (no change)
2. `EnrichStage` (no change - enrich file metadata)
3. `ParseProcessorStage` (returns List[TextNode])
4. `EnrichChunksStage` (enriches TextNode.metadata)
5. `IndexingStage` (new - persists to vector store)
**Убрать stays**: embed, persist
**Обновить конфиг**: убрать `embed_workers`, `persist_workers`; добавить `indexing_workers`
**Проверка**: `IndexationPipelineBuilder.get_default_definitions()` возвращает 5 стадий

### Задача 2.9: Удалить модель Chunk
**Файл**: `core/models/chunk.py` - УДАЛИТЬ ВЕСЬ ФАЙЛ
**Файлы** для обновления:
- Везде, где импортировали `Chunk`, заменить на `TextNode` из `llama_index.core.schema`
- `adapters/postgres/storage.py` - методы `save_chunk`, `save_chunks` больше не нужны (весь CRUD через vector store)
- `adapters/postgres/storage.py`: оставить только file_summary, module_summary методы
**Проверка**: Никаких `Chunk` импортов не осталось

### Задача 2.10: Обновить TextSplitterHelper
**Файл**: `pipeline/utils/text_splitter_helper.py`
**Действие**:
```python
from llama_index.core.schema import TextNode

@staticmethod
async def chunk_file(...) -> Tuple[List[TextNode], Optional[str]]:
    # ... читаем файл
    nodes = splitter.get_nodes_from_documents([Document(text=content, metadata={"file_path": rel_path, "extension": ext})])
    
    # Дополняем metadata
    for idx, node in enumerate(nodes):
        node.metadata["file_path"] = rel_path
        node.metadata["extension"] = ext
        node.metadata["chunk_index"] = idx
    
    return nodes, None  # ← возвращаем TextNode, не dicts
```
Удалить `generate_chunk_id()` - не нужно, vector store сам сгенерирует ID.
**Проверка**: Splitter возвращает `List[TextNode]` с полной metadata

---

## ФАЗА 3: Замена Search Pipeline

### Задача 3.1: Создать KnowledgeIndex
**Файл**: `ingestor/search/knowledge_index.py` (новый)
**Действие**:
```python
from llama_index.core import VectorStoreIndex, StorageContext
from llama_index.core.retrievers import VectorIndexRetriever
from llama_index.core.vector_stores import Filter, FilterOperator

class KnowledgeIndex:
    def __init__(self, vector_store: VectorStore, embed_model: BaseEmbedding):
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        self._index = VectorStoreIndex(
            nodes=[],
            storage_context=storage_context,
            embed_model=embed_model,
        )
    
    async def search(self, query: str, top_k: int = 10, filter_by_file: Optional[str] = None) -> List[Dict]:
        retriever = VectorIndexRetriever(
            index=self._index,
            similarity_top_k=top_k * 2,  # больше для дедупликации
        )
        
        # Фильтрация по file_path
        if filter_by_file:
            retriever._filters = Filter.from_dict({"file_path": {"$eq": filter_by_file}})
        
        nodes = await retriever.aretrieve(query)
        
        # Дедупликация по файлам (как раньше в pipeline/knowledge_search/pipeline.py:87-105)
        seen_files = set()
        results = []
        for node in nodes:
            file_path = node.metadata.get("file_path")
            if file_path and file_path not in seen_files:
                seen_files.add(file_path)
                results.append({
                    "file_path": file_path,
                    "content": node.text,
                    "score": node.score if hasattr(node, 'score') else None,
                    "metadata": node.metadata,
                    "start_line": node.metadata.get("start_line", 0),
                    "end_line": node.metadata.get("end_line", 0),
                })
                if len(results) >= top_k:
                    break
        
        return results
```
**Проверка**: Поиск возвращает до `top_k` уникальных файлов с правильными полями

### Задача 3.2: Удалить KnowledgeSearchPipeline полностью
**Файлы** на удаление:
- `pipeline/knowledge_search/pipeline.py`
- `pipeline/knowledge_search/builder.py`
- `pipeline/stages/query_source_stage.py`
- `pipeline/stages/search_result_sink_stage.py`
- `pipeline/stages/search_db_stage.py` (если есть)
**Проверка**: Все импорты заменены на `KnowledgeIndex`

### Задача 3.3: Обновить services/knowledge.py
**Файл**: `services/knowledge.py`
**Действие**:
```python
class KnowledgeService:
    def __init__(self, knowledge_index: KnowledgeIndex):
        self._index = knowledge_index
    
    async def search(self, query: str, top_k: int = 10, filter_by_file: Optional[str] = None):
        return await self._index.search(query, top_k, filter_by_file)
```
Удалить весь код, связанный с `KnowledgeSearchPipeline`.
**Проверка**: Сервис работает

### Задача 3.4: Обновить API endpoints
**Файл**: `api/server.py`
**Действие**: Вместо создания `KnowledgeSearchPipeline` передавать `KnowledgeIndex` в конструкторе `IngestorAPI`
**Проверка**: `POST /v1/knowledge/search` возвращает те же поля (status, results/error)

---

## ФАЗА 4: Конфигурация и инициализация

### Задача 4.1: Создать ComponentFactory
**Файл**: `ingestor/factory.py` (новый)
**Действие**:
```python
class ComponentFactory:
    @staticmethod
    def create_vector_store(config: StorageConfig) -> VectorStore:
        if config.type == "postgres":
            return LlamaPostgresVectorStore(config.connection_string, config.table_name)
        elif config.type == "memory":
            return LlamaMemoryVectorStore()
        else:
            raise ValueError(f"Unknown vector store type: {config.type}")
    
    @staticmethod
    def create_embedding(config: EmbeddingConfig) -> BaseEmbedding:
        return LlamaEmbedding(config)
    
    @staticmethod
    def create_llm(config: LLMConfig) -> LLM:
        # InfraLLMAdapter или LlamaOpenAI
        from adapters.llama_llm import InfraLLMAdapter
        llm_manager = LLMManager(...)
        return InfraLLMAdapter(llm_manager, context_window=8192, model_name=config.model_name)
    
    @staticmethod
    def create_knowledge_index(vector_store: VectorStore, embed_model: BaseEmbedding) -> KnowledgeIndex:
        return KnowledgeIndex(vector_store, embed_model)
```
**Проверка**: Все компоненты создаются через factory

### Задача 4.2: Обновить main.py
**Файл**: `main.py`
**Действие**:
```python
async def main():
    config = PipelineConfig.from_env()  # или из файла
    
    # Инициализация
    storage = PostgreSQLStorage(config.storage.connection_string)
    await storage.initialize()
    
    vector_store = ComponentFactory.create_vector_store(config.storage)
    embed_model = ComponentFactory.create_embedding(config.embedding)
    llm = ComponentFactory.create_llm(config.llm)
    knowledge_index = ComponentFactory.create_knowledge_index(vector_store, embed_model)
    
    # Pipeline context (устареет в будущем)
    pipeline_context = PipelineContext(
        workspace_path=config.runtime.workspace_path,
        storage=storage,
        llm=llm,
        embed_model=embed_model,
        # ...
    )
    
    # Services
    indexer = IndexerService(
        storage=storage,
        knowledge_index=knowledge_index,
        pipeline_context=pipeline_context,
    )
    
    api = IngestorAPI(
        knowledge_index=knowledge_index,
        storage=storage,
        # ...
    )
    
    await api.run()
```
**Проверка**: Приложение запускается с новыми компонентами

### Задача 4.3: Обновить PipelineContext (упростить или удалить)
**Файл**: `pipeline/models/pipeline_context.py`
**Действие**: Постепенно упрощать, в перспективе удалить в пользу прямого DI
**Проверка**: Контекст создается, если еще используется

---

## ФАЗА 5: Оптимизация и бесшовный переход

### Задача 5.1: Интегрировать эмбеддинги в vector_store.add_nodes()
**Вопрос**: Как transferred nodes получают embeddings?
**Решение**: `VectorStore.add_nodes()` должно:
1. Проверить, есть ли у nodes уже embeddings
2. Если нет, использовать embed_model для генерации (батчево)
3. Затем сохранить в store

```python
# В LlamaPostgresVectorStore.add_nodes():
async def add_nodes(self, nodes: list[TextNode]) -> list[str]:
    # Фильтруем nodes без embedding
    nodes_with_emb = [n for n in nodes if n.embedding]
    nodes_without_emb = [n for n in nodes if not n.embedding]
    
    if nodes_without_emb:
        # Генерируем батчем
        texts = [n.get_text() for n in nodes_without_emb]
        embeddings = await self.embed_model.aget_text_embeddings(texts)
        for node, emb in zip(nodes_without_emb, embeddings):
            node.embedding = emb
    
    # Теперь все nodes имеют embeddings, добавляем
    return await self._store.async_add(nodes)
```
**Проверка**: Эмбеддинги генерируются автоматически при индексации

### Задача 5.2: Добавить circuit breaker для embedding и vector_store
**Файлы**: `adapters/embeddings.py`, `adapters/vector_store.py`
**Действие**: Использовать библиотеку `circuitbreaker` или свой на `tenacity`:
```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

def circuit_breaker_aware():
    def decorator(func):
        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            retry=retry_if_exception(lambda e: isinstance(e, ServiceUnavailableError))
        )
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        return wrapper
    return decorator
```
**Проверка**: При падении embedding service пайплайн продолжает с деградацией (логирует ошибки)

### Задача 5.3: Добавить embedding cache (опционально)
**Файл**: `adapters/embeddings.py`
**Действие**:
```python
from cachetools import TTLCache

class LlamaEmbedding(BaseEmbedding):
    def __init__(self, config: EmbeddingConfig):
        # ...
        self._cache = TTLCache(maxsize=10000, ttl=3600)  # 1 hour
    
    async def _get_text_embedding(self, text: str) -> List[float]:
        if text in self._cache:
            return self._cache[text]
        emb = await self._real_get_embedding(text)
        self._cache[text] = emb
        return emb
```
**Проверка**: Повторные тексты не вызывают HTTP запросы

### Задача 5.4: Добавить OpenTelemetry callbacks
**Файл**: `main.py` или новый `ingestor/observability.py`
**Действие**:
```python
from llama_index.core.callbacks import CallbackManager, OpenInferenceCallbackHandler
from opentelemetry import trace

tracer = trace.get_tracer(__name__)
callback_handler = OpenInferenceCallbackHandler(tracer)
Settings.callback_manager = CallbackManager([callback_handler])
```
**Проверка**: Трассировка этапов пайплайна в Jaeger/Zipkin

---

## ФАЗА 6: Очистка legacy кода

### Задача 6.1: Удалить адаптер embedding_model.py (уже сделано в 2.2)
**Проверка**: Очистка

### Задача 6.2: Удалить InfraLLMAdapter (опционально)
**Файл**: `adapters/llama_llm.py`
**Дилемма**: 
- InfraLLMAdapter сохраняет переподключения через LLMManager (ценность)
- Но это layer между llama_index LLM и LLMManager

**Варианты**:
1. Оставить как есть (проще)
2. Заменить на `LlamaOpenAI` напрямую и делегировать переподключения `tenacity` (дублирование!)
3. Вынести reconnect logic в отдельный mixin, который используют и InfraLLMAdapter, и embedding

**Рекомендация**: Оставить InfraLLMAdapter, он уже корректно делегирует переподключения LLMManager. Не трогать.

### Задача 6.3: Удалить TextSplitterHelper после полного перехода
**Файл**: `pipeline/utils/text_splitter_helper.py` - УДАЛИТЬ
**Действие**: Использовать `Settings.node_parser` глобально:
```python
from llama_index.core import Settings

def get_splitter_for_extension(ext: str):
    if ext == ".py":
        return CodeSplitter(chunk_lines=40, chunk_lines_overlap=15, max_chars=1500)
    elif ext == ".md":
        return MarkdownNodeParser()
    else:
        return SentenceSplitter(chunk_size=512, chunk_overlap=50)

# В ParseProcessorStage:
splitter = get_splitter_for_extension(ext)
nodes = splitter.get_nodes_from_documents([...])
```
**Проверка**: Сплиттинг работает без helper

### Задача 6.4: Удалить PipelineContext (долгосрочная цель)
**Файл**: `pipeline/models/pipeline_context.py` - УДАЛИТЬ
**Действие**: Передавать зависимости явно через конструкторы stage
**Проверка**: DI через factory

### Задача 6.5: Удалить pipeline/base/ если не используется
**Файлы**:
- После перехода на simplified pipeline, проверить используются ли:
  - `pipeline/base/base_pipeline.py`
  - `pipeline/base/processor_stage.py`
  - `pipeline/base/source_stage.py`
  - `pipeline/base/base_stage.py`
  - `pipeline/base/queues.py`
- Если `IndexationPipeline` все еще наследуется от `BasePipeline` и использует очереди - оставить.
- Если можно упростить до `asyncio.TaskGroup` - удалить.

**Проверка**: Импорты не ломаются

### Задача 6.6: Удалить Postgres маппинг и репозитории (уже сделано в 1.6)
**Проверка**: Чистота

---

## ФАЗА 7: Тестирование и верификация

### Задача 7.1: Добавить unit tests для новых адаптеров
**Директория**: `.opencode/skills/ingestor/tests/` или `tests/`
**Файлы**:
- `test_vector_store.py` - мокаем PGVectorStore, тестируем retry logic
- `test_embeddings.py` - мокаем HTTP, тестируем rate limiting, cache
- `test_llama_llm.py` - тесты для InfraLLMAdapter
- `test_knowledge_index.py` - тесты поиска с фильтрами

**Действие**: Покрытие >80%
**Проверка**: `pytest` проходят

### Задача 7.2: Добавить integration tests
**Файлы**:
- `tests/integration/test_full_indexing.py`: 
  - Индексируем тестовый workspace (10+ файлов)
  - Проверяем, что все chunks сохранились
  - Выполняем поиск, проверяем результаты
- `tests/integration/test_retry.py`: мокаем embedding API, симулируем 500 errors, проверяем retry
- `tests/integration/test_rate_limiting.py`: запускаем параллельные запросы, проверяем limit
**Проверка**: Интеграционные тесты проходят

### Задача 7.3: Бенчмарк производительности
**Файл**: `tests/benchmark/benchmark.py`
**Действие**:
```python
import time

# Before/after сравнение:
# - Индексация 1000 файлов
# - Поиск по 10,000 чанков
# - Memory usage
```
**Проверка**: Результаты не хуже (ожидается улучшение в памяти и скорость поиска)

### Задача 7.4: Migration существующих данных (если нужно)
**Проблема**: В PostgreSQL есть таблица `chunks` с эмбеддингами от старого формата Chunk.
**Решение**: 
1. Написать migration script, который конвертирует старые Chunk записи в TextNode format
2. ИЛИ: оставить обратную совместимость в `LlamaPostgresVectorStore` для чтения обоих форматов
3. При следующей полной реиндексации данные перезапишутся

**Файл**: `scripts/migrate_chunks.py` (новый)
**Проверка**: Существующие данные доступны после миграции

---

## КРИТЕРИИ УСПЕШНОГО ЗАВЕРШЕНИЯ

1. ✅ **Фаза 0 выполнена**: Все экстренные исправления применены
2. ✅ **Векторный поиск**: Заменен на VectorStore (O(log n) вместо O(n))
3. ✅ **Embedding**: Использует LlamaEmbedding с retry, rate limit, shared client
4. ✅ **Pipeline**: Упрощен до 5 стадий (filter → enrich → parse → enrich_nodes → indexing)
5. ✅ **Search**: Заменен на KnowledgeIndex (прямой вызов вместо 4-стадийного пайплайна)
6. ✅ **Код**: Удален весь дублирующийся код (EmbeddingModel, PersistStage, Chunk model, и т.д.)
7. ✅ **Конфиг**: Централизован в Pydantic моделях, нет hard-coded values
8. ✅ **Тесты**: Есть unit + integration coverage >80%
9. ✅ **Производительность**: Latency индексации и поиска не ухудшилась (ожидается улучшение)
10. ✅ **Безопасность**: Обработка ошибок корректна, нет bare except, есть retry
11. ✅ **Переподключения**: Сохранена вся логика из BaseManager (через LLMManager → InfraLLMAdapter)
12. ✅ **DRY**: Нет дублирования функционала
13. ✅ **Количество строк**: Сократилось на 30%+ (удалены ~1000 строк кастомного кода)

---

## РИСКИ И МИТИГАЦИИ

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| Миграция данных несовместима | Средняя | Высокое | Сделать dual-read поддержку в VectorStoreAdapter на переходный период |
| Производительность упадет | Низкая | Среднее | Бенчмарк на каждом этапе, оптимизация |
| LLMManager API changes сломает InfraLLMAdapter | Средняя | Среднее | Изолировать InfraLLMAdapter, писать адаптер с запасом |
| Tenacity retry conflicts с пайплайном таймаутами | Низкая | Среднее | Настраивать retry timeout < пайплайн timeout |
| PGVector version incompatibility | Низкая | Высокое | Зафиксировать версии в requirements, тестировать перед деплоем |
| Потеря file_summaries при удалении FileSummaryStage | Высокая | Среднее | Вынести file summary создание в background task, НЕ в пайплайн |

---

## ОТВЕТЫ НА КЛЮЧЕВЫЕ ВОПРОСЫ

### Q: "Где еще недосмотры? Список всех проблем?"
**A**: Найдены следующие (см. comprehensive analysis):
1. O(n) vector search в memory storage (критично)
2. HTTP client per request в embedding (критично)
3. Нет retry на embedding operations (критично)
4. Нет rate limiting (высоко)
5. Config scattering + magic numbers (высоко)
6. KeyError в builder (высоко)
7. Bare except (средне)
8. Duplicate error handling (средне)
9. Нет tests (высоко)
10. No circuit breaker (средне)
11. No embedding cache (низко)
12. Custom pipeline vs IngestionPipeline (средне) - но оставляем для контроля

Все они адресованы в Фазе 0 и основной миграции.

### Q: "Как сохранить переподключения из BaseManager?"
**A**: InfraLLMAdapter уже правильно использует LLMManager. Не трогаем. Для embedding и vector_store используем `tenacity` retry decorator (как в `postgres/connection.py`). Это эквивалентно reconnect logic для stateless HTTP/DB queries.

### Q: "Оставлять ли Langchain в ingestor?"
**A**: НЕТ. После миграции ingestor должен зависеть только от:
- `llama-index` (core)
- `llama-index-vector-stores-postgres`
- `llama-index-vector-stores-simple`
- `llama-index-embeddings-openai`
- `llama-index-llms-openai` (опционально, если не используем InfraLLMAdapter)

`LLMManager` (langchain) используется только для `InfraLLMAdapter`, которыйadaptiert его к llama_index интерфейсу. Но сам `ChatOpenAI` остается. Это ОК - адаптер скрывает зависимость.

**Идеально**: Если убрать langchain полностью, нужно переписать `LLMManager` на `llama_index.llms.openai.OpenAI` напрямую. Но это рискованно, если agents зависят от LLMManager. **Оставляем как есть** - InfraLLMAdapter изолирует.

---

## ПОРЯДОК ВЫПОЛНЕНИЯ (обновленный)

**Критически важно**: Фаза 0 → Фаза 1 → Фаза 2 → Фаза 3 → Фаза 4 → Фаза 5 → Фаза 6 → Фаза 7

1. **Фаза 0** (Экстренные исправления) - задачи 0.1-0.10
2. **Фаза 1** (VectorStore) - задачи 1.1-1.7
3. **Фаза 2** (Pipeline Indexation) - задачи 2.1-2.10
4. **Фаза 3** (Search) - задачи 3.1-3.4
5. **Фаза 4** (Configuration) - задачи 4.1-4.3
6. **Фаза 5** (Optimization) - задачи 5.1-5.4
7. **Фаза 6** (Cleanup) - задачи 6.1-6.6
8. **Фаза 7** (Testing) - задачи 7.1-7.4

Каждую задачу:
- Внести изменения
- Запустить `pytest` (или существующие тесты)
- Запустить smoke test (индексация 1-2 файлов + поиск)
- Commit с ясным сообщением
- Если сломалось → immediate fix или revert

---

## ЗАКЛЮЧЕНИЕ

Этот план учитывает:
1. **Все критические недосмотры** (выявлены deep analysis)
2. **Логику переподключений** (сохраняем через BaseManager + tenacity)
3. **DRY** (удаляем весь дублирующийся код)
4. **Постепенный переход** (каждая задача оставляет работающую систему)
5. **Производительность** (O(n) → O(log n), shared clients, rate limiting, caching)
6. **Тестируемость** (добавляем tests параллельно)
7. **Безопасность** (proper error handling, no bare except, retry, circuit breaker)

Готов приступить к реализации. Рекомендую начать с **Фазы 0** немедленно.
