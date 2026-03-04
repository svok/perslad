# АКТУАЛИЗИРОВАННЫЙ ПЛАН РЕФАКТОРИНГА (TEST-GREEN GUARANTEE)

**Дата актуализации:** 2026-02-26 14:00  
**Изменения:** Добавлен **"Test-Green Guarantee"** — после каждой фазы `./scripts/run_e2e_tests.sh all --parallel=4` проходит **100%**.  
**Текущее состояние:** Phase 0 ✅, Phase 1 ✅, Phase 2 ✅ (функционал работает, тесты 75% green).  
**Цель:** Постепенная миграция **без поломки тестов**.

---

## 🎯 **ПРИНЦИП "TEST-GREEN GUARANTEE"**

### Структура каждой фазы:
1. **Core Changes** (основные изменения)
2. **Test Updates** (обновление всех затронутых тестов **в той же фазе**)
3. **Verification** (`./scripts/run_e2e_tests.sh all` → 100% green)

**Правила:**
- Schema/API changes → сразу обновить conftest.py fixtures + все использующие файлы
- **Fallback**: Mock/adapter для legacy (удалить в Phase 5)
- **Команды верификации:**
  ```bash
  cd e2e-tests
  ./scripts/run_e2e_tests.sh all --parallel=4  # 100% green
  make test-coverage  # >80%
  ```

---

## 📊 **CURRENT TEST STATUS (Phase 2)**

| Test File | Passing | Failing | Notes |
|-----------|---------|---------|-------|
| test_agents_ingestor_integration.py | 10/11 | 1 | orphan_files (изоляция) |
| test_component_ingestor.py | 11/13 | 2 | /v1/chunks endpoint |
| test_indexation_workflows.py | 11/13 | 2 | chunks queries |
| test_db_operations.py | 7/15 | 8 | direct chunks SQL |
| **Total** | **39/52** | **13** | **75%** |

---

## ✅ **COMPLETED PHASES**

### Phase 0 ✅ (100% tests green)
### Phase 1 ✅ (core + inline test fixes)
### Phase 2 ✅ (core + inline test fixes, 75% green)

---

## 🔄 **CORRECTED PHASES (Test-Green)**

### **Phase 1 Extension: 100% Green Tests** (1-2 дня, **PRIORITY 1**)
**Core**: Fix remaining 13 tests.

**Tasks + Test Updates:**
1. **test_db_operations.py**: **DELETE FILE** (obsolete low-level SQL)
2. **test_indexation_workflows.py**: Replace `chunks` → `data_chunks_vectors`
3. **test_component_ingestor.py**: Remove `TestChunksEndpoint`
4. **conftest.py clean_database**: Update schema to `data_chunks_vectors` + cleanup temp files
5. **test_no_orphan_files_in_db**: Ignore temp files (`concurrent_*`)
6. **Verification**: `./scripts/run_e2e_tests.sh all` → **100% green**

**Criterion**: All tests pass.

### **Phase 3: Config & Reliability** (2 дня)
**Core Changes** (central config, retries).

**Test Updates**: Mock env vars, config loading tests.

**Verification**: Tests 100% green + config smoke test.

### **Phase 4: Graph DB** (separate, no tests impact)

### **Phase 5: Legacy Cleanup** (1 день)
**Core**: Remove deprecated.

**Test Updates**: None.

### **Phase 6: Full Test Modernization** (2 дня)
**New Tests**: Summary generation, vector ops, performance.

**Coverage**: >85%.

---

## 📋 **ROADMAP (Test-Green Order)**

1. ✅ Phase 0
2. ✅ Phase 1
3. ✅ Phase 2
4. 🔄 **Phase 1 Extension** (NOW: 100% green)
5. ⏳ Phase 3
6. ⏳ Phase 5
7. ⏳ Phase 6

**Next**: Execute **Phase 1 Extension** for **100% green tests**.

**Approve?**

### **File Summary: Синхронная генерация с last_summarized_at**
- Генерировать при каждом индексации файла (после EnrichChunksStage)
- Использовать LLM (локальная qwen2.5-7B — быстрая и бесплатная)
- Добавить поле `last_summarized_at: float` в metadata для отслеживания
- Формат: агрегировать chunk summaries (первые N=20) → file-level summary (2-3 предложения)
- **Преимущество**: Простота, синхронность, нет фоновых задач

### **Module Summary: Иерархическое агрегирование по директориям**
- Граница модуля = директория с `__init__.py` + все поддиректории (рекурсивно)
- Каждая такая директория = модуль (module_path относительный путь)
- Генерировать на основе file summaries модуля (только файлы с `valid=True`)
- Использовать дерево саммаризации: 
  - Leaf: file summaries (уже есть)
  - Intermediate: aggregate дочерних модулей → parent module summary
  - Root: project overview
- Запускать после FileSummaryStage (в том же пайплайне или фоном)

### **Графовая БД (NebulaGraph/Neo4j) — отдельная фаза**
- Только учесть в архитектуре: export из vector_store в граф
- Позже: факты (imports, calls, definitions) → ребра графа
- Сейчас не реализовывать

---

## 📋 АКТУАЛИЗИРОВАННЫЙ ПЛАН (практический)

### **ФАЗА 0: Экстренные исправления** (1-2 дня)

| № | Задача | Файлы | Статус |
|---|--------|-------|--------|
| 0.1 | Shared HTTP client + close() | `adapters/embedding_model.py` | ❌ |
| 0.2 | Retry (tenacity) на embedding | `adapters/embedding_model.py` | ❌ |
| 0.3 | Rate limiting (semaphore) | `adapters/embedding_model.py` | ❌ |
| 0.4 | KeyError: `.get()` в builder | `pipeline/indexation/builder.py` | ⚠️ Частично |
| 0.5 | Graceful shutdown в main.py | `main.py` | ❌ |
| 0.6 | Bare except → Exception | `pipeline/stages/inotify_source.py:115` | ⚠️ |
| 0.7 | Central config activation | `main.py` + `config/base.py` | ❌ |
| 0.8 | PGVECTOR_DIMENSIONS hack | `config/storage.py` | ❌ |
| 0.9 | Вынести hard-coded в config | builder, stages, main.py | ❌ |
| 0.10 | Bare except везде | все stage'ы | ⚠️ |

**Критерий:** Все e2e-тесты проходят, нет socket exhaustion, корректный shutdown.

---

### **ФАЗА 1: Убрать велосипед — консолидация хранилища** (2-3 дня)

**Цель:** Оставить только `chunks_vectors` (PGVectorStore) как единый источник истины.

#### 1.1 Удалить `chunks` table и `ChunkRepository`
- Удалить `adapters/postgres/repositories/chunk.py` целиком
- Удалить `adapters/postgres/mappers.py` (не нужен без Chunk)
- Удалить CREATE TABLE `chunks` из `adapters/postgres/connection.py`
- Оставить: `file_summaries`, `module_summaries`, `stats` таблицы

#### 1.2 Убрать dual-write в IndexingStage
- Удалить блок `if self.storage is not None: ... save_chunks()` (строки 62-86 в `indexing_stage.py`)
- Оставить только `await self.vector_store.async_add(batch)`

#### 1.3 Переделать `PostgreSQLStorage`: убрать chunk-методы из интерфейса
Удалить из `BaseStorage` и реализаций:
- `save_chunk()`, `save_chunks()`
- `get_chunk()`, `get_all_chunks()`
- `get_chunks_by_file()` → **сохранить, но изменить реализацию** (см. 1.5)
- `delete_chunks_by_file_paths()` → переделать на vector_store.delete()

#### 1.4 Настроить PGVectorStore с `indexed_metadata_keys`
```python
PGVectorStore(
    connection_string=...,
    table_name="chunks_vectors",
    embed_dim=1536,
    index_metadata_keys=["file_path"]  # B-tree индекс для быстрой фильтрации
)
```
Это позволит эффективно выполнять `get_chunks_by_file()` через metadata filter.

#### 1.5 Реализовать `get_chunks_by_file()` через vector_store
```python
async def get_chunks_by_file(self, file_path: str) -> List[Chunk]:
    from llama_index.core.vector_stores import Filter, MetadataFilters
    
    filters = MetadataFilters(
        filters=[Filter(key="file_path", operator=FilterOperator.EQ, value=file_path)]
    )
    query = VectorStoreQuery(
        query_embedding=None,  # нет query, просто фильтр
        similarity_top_k=1000,  # достаточное число
        filters=filters,
    )
    result = await self._vector_store.query(query)
    
    # Конвертация TextNode → Chunk (для совместимости)
    return [
        Chunk(
            id=node.node_id,
            file_path=node.metadata.get("file_path", ""),
            content=node.text,
            start_line=node.metadata.get("start_line", 0),
            end_line=node.metadata.get("end_line", 0),
            chunk_type=node.metadata.get("chunk_type", ""),
            summary=node.metadata.get("summary", ""),
            purpose=node.metadata.get("purpose", ""),
            embedding=node.embedding,
            metadata=node.metadata,
        )
        for node in result.nodes
    ]
```

#### 1.6 Исправить удаление векторов
`delete_chunks_by_file_paths()` должно удалять и из vector_store:
```python
async def delete_chunks_by_file_paths(self, file_paths: List[str]) -> None:
    # Удаляем из vector_store (через метаданные)
    for file_path in file_paths:
        filters = MetadataFilters(
            filters=[Filter(key="file_path", operator=FilterOperator.EQ, value=file_path)]
        )
        await self._vector_store.delete(filters=filters)
    
    # Удаляем из репозиториев (file_summaries, module_summaries также)
    await self._file_summaries.delete_by_files(file_paths)
```

---

### **ФАЗА 2: File & Module Summary Generation** (2-3 дня)

#### 2.1 Добавить `last_summarized_at` в FileSummary
`core/models/file_summary.py`:
```python
@dataclass
class FileSummary:
    file_path: str
    summary: str  # БУДЕТ генерироваться
    metadata: Dict:
        size: int
        mtime: float
        checksum: str
        valid: bool | None  # или invalid_reason
        last_summarized_at: float | None  # NEW: время последней генерации
```

#### 2.2 FileSummaryStage: синхронная генерация summary
`pipeline/stages/file_summary_stage.py`:
```python
async def process(self, context):
    file_path = str(context.file_path)
    abs_path = Path(self.workspace_path) / file_path
    
    # Удаление файла
    if context.event_type == "delete" or not abs_path.exists():
        await self.storage.delete_file_summary(file_path)
        await self.storage.delete_chunks_by_file_paths([file_path])
        return context
    
    # Проверка валидности
    if context.has_errors or not context.nodes:
        # Невалидный файл: summary пустой
        summary = FileSummary(
            file_path=file_path,
            summary="",
            metadata={
                "size": stat.st_size,
                "mtime": stat.st_mtime,
                "checksum": new_checksum,
                "valid": False,
                "invalid_reason": reason,
                "last_summarized_at": None,
            }
        )
    else:
        # Генерация file-level summary из chunk summaries
        chunk_summaries = [
            n.metadata.get("summary", "") 
            for n in context.nodes 
            if n.metadata.get("summary")
        ]
        # Ограничиваем количеством чанков для экономии токенов
        combined_summaries = "\n".join(chunk_summaries[:20])
        
        prompt = FILE_SUMMARY_PROMPT_TEMPLATE.format(
            file_path=file_path,
            chunk_summaries=combined_summaries,
            total_chunks=len(chunk_summaries),
        )
        
        try:
            response = await self.llm.acomplete(prompt)
            file_summary_text = response.text.strip()[:500]  # лимит
        except Exception as e:
            self.log.error("file_summary.generation_failed", file=file_path, error=str(e))
            file_summary_text = ""  # fallback
        
        summary = FileSummary(
            file_path=file_path,
            summary=file_summary_text,
            metadata={
                "size": stat.st_size,
                "mtime": stat.st_mtime,
                "checksum": new_checksum,
                "valid": True,
                "last_summarized_at": time.time(),
            }
        )
    
    await self.storage.save_file_summary(summary)
    return context
```

#### 2.3 Module Summary: обнаружение модулей и генерация
**Новый stage:** `ModuleSummaryStage`

**Модуль detection algorithm:**
```python
def discover_modules(workspace_path: Path) -> List[Path]:
    """Найти все директории с __init__.py (Python packages)"""
    modules = []
    for root, dirs, files in os.walk(workspace_path):
        if "__init__.py" in files:
            module_path = Path(root).relative_to(workspace_path)
            modules.append(module_path)
    return modules
```

**ModuleSummaryStage логика:**
- Триггер: после `FileSummaryStage` или по расписанию (если много файлов)
- Собрать все `file_summary` для файлов в модуле (и подмодулях)
- Отфильтровать `valid=True` файлы
- Агрегировать:
  - Список file_paths
  - Статистика: total_files, total_chunks, total_lines
  - Combined summaries → LLM prompt для модульного overview
- Сохранить `ModuleSummary(module_path, summary, metadata)`

**Иерархия:**
- Последовательная генерация: file → submodule → module → top-level
- Или параллельная с кэшированием

---

### **ФАЗА 3: Конфиг + Reliability** (1-2 дня)

#### 3.1 Активировать PipelineConfig.from_env()
В `main.py`:
```python
from ingestor.config.base import PipelineConfig

config = PipelineConfig.from_env()  # читает из .env
pipeline_context = PipelineContext(config=config)
```

#### 3.2 Перенести ВСЕ hard-coded параметры в PipelineConfig
Добавить в `config/base.py`:
```python
class PipelineConfig(BaseModel):
    # Workers
    enrich_workers: int = 2
    parse_workers: int = 1
    indexing_workers: int = 2
    file_summary_workers: int = 2
    module_summary_workers: int = 2
    
    # Batch sizes
    filter_batch_size: int = 100
    filter_max_wait: float = 3.0
    indexing_batch_size: int = 100
    collector_batch_size: int = 10
    collector_max_wait: float = 0.5
    
    # Text splitter
    python_chunk_lines: int = 40
    python_chunk_overlap: int = 15
    python_max_chars: int = 1500
    doc_chunk_size: int = 512
    doc_chunk_overlap: int = 50
    config_chunk_size: int = 512
    config_chunk_overlap: int = 50
    
    # Embedding & LLM
    embed_rate_limit_rpm: int = 100
    embed_max_chars: int = 8000
    embed_batch_size: int = 10
    file_summary_max_chunks: int = 20  # лимит для aggregation
    
    # Timeouts
    postgres_operation_timeout: float = 60.0
    postgres_query_timeout: float = 10.0
    postgres_acquire_timeout: float = 5.0
    search_timeout: float = 30.0
```

Удалить все hard-coded из stages, builder, connection, main.py.

#### 3.3 Tenacity retry + rate limit + shared client
- `EmbeddingModel`: shared `AsyncClient` + `@retry` + `Semaphore`
- `PostgreSQLStorage`: retry на все DB операции
- `PGVectorStoreAdapter`: обертка с retry

#### 3.4 Graceful shutdown
`main.py`:
```python
try:
    await app.run()
finally:
    await embed_model.aclose()
    await llm_manager.aclose()
    await storage.aclose()
```

---

### **ФАЗА 4: Graph DB подготовка** (отдельно, но проектировать)

**Не реализовывать сейчас, только спроектировать:**

#### 4.1 NebulaGraph schema design
- **Vertices**: File, Module, Class, Function, Variable
- **Edges**: BELONGS_TO (File→Module), IMPORTS, CALLS, DEFINES, REFERENCES
- **Properties**: Для каждой вершины — атрибуты (summary, checksum, line count)

#### 4.2 Exporter architecture
- Модуль `graph/exporter.py` (не в repo yet)
- Источник: `vector_store` (metadatafilter → all nodes)
- Трансформация: AST parsing + LLM extraction для фактов
- Нагрузка: bulk upsert через NebulaGraph client
- Триггеры: по событию file_indexed, или по cron

**Примечание:** Это тема на отдельный рефакторинг, только зафиксировать идею.

---

### **ФАЗА 5: Очистка legacy** (1 день)

#### 5.1 Удалить неиспользуемые классы
- `ChunkRepository` (уже в 1.1)
- `Chunk` model (оставить только для DTO возвратов, но упростить)
- `adapters/postgres/mappers.py`
- `KnowledgeSearchPipeline` (все равно не используется, есть KnowledgeIndex)

#### 5.2 Упростить storage интерфейс
Оставить только:
- FileSummary: `save/get/get_all/delete`
- ModuleSummary: `save/get/get_all/delete`
- Vector search: `search_vector()` (делегирует vector_store)
- Metadata: `get_file_metadata/update_file_metadata/get_files_metadata`

Убрать методы прямого доступа к chunks (кроме `get_chunks_by_file`, который теперь через vector_store).

---

### **ФАЗА 6: Тестирование** (2-3 дня)

#### 6.1 Переписать тесты, зависящие от chunks table
Поскольку удаляется `chunks` table, тесты должны использовать storage layer:

**Что изменить:**
- `e2e-tests/tests/conftest.py`:
  - `get_chunks_count_for_file()` → `len(await storage.get_chunks_by_file(file_path))`
  - `get_chunks_count()` → агрегация по всем file_summaries или vector_store
  
- `test_db_operations.py`: 
  - **Удалить полностью** (это были низкоуровневые тесты SQL, теперь абстрагированы)
  - Или переписать на тесты vector_store operations

**Тесты, требующие изменений:**
- Все, что проверяют `chunks_count == 0` для invalid/deleted files
- Все, что проверяют `chunks_count > 0` для valid files
- `test_chunks_have_embeddings_and_summaries` → query через storage
- `test_chunks_have_required_fields` → validate на результате `get_chunks_by_file`

#### 6.2 Добавить тесты для нового поведения
- Интеграционный: file summary генерируется и сохраняется
- Интеграционный: module summary агрегируется из file summaries
- Интеграционный: удаление файла очищает и vector_store, и file_summary
- Unit: `get_chunks_by_file()` через vector_store с фильтром

#### 6.3 Бенчмарки
- Сравнить latency индексации до/после (убрана dual-write)
- Проверить correctness: один source of truth

---

## 📊 МАТРИЦА ЗАВИСИМОСТЕЙ

```
IndexationPipeline:
  IncrementalFilterStage → EnrichStage → ParseProcessorStage → EnrichChunksStage → 
  IndexingStage → FileSummaryStage → [ModuleSummaryStage] → IndexerSinkStage

Storage:
  PostgreSQLStorage:
    - vector_store (PGVectorStore) → chunks_vectors table (основное)
    - FileSummaryRepository → file_summaries table
    - ModuleSummaryRepository → module_summaries table
    - stats repository
  
  MemoryStorage:
    - SimpleVectorStore (in-memory)
    - in-memory file/module summaries

API:
  GET /v1/knowledge/file/{path} → KnowledgePort.get_file_context() → 
    storage.get_chunks_by_file() (из vector_store) + file_summary
  
  POST /v1/knowledge/search → KnowledgeIndex.search() → vector_store.query()
  
  GET /v1/knowledge/overview → KnowledgePort.get_project_overview() → 
    file_summaries + module_summaries

Agents:
  read_file_context tool → GET /v1/knowledge/file/{path}
```

---

## ⚠️ КРИТИЧЕСКИЕ РИСКИ

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| Тесты ломаются после удаления `chunks` table | Высокая | Высокое | Переписать тесты на storage API (Фаза 6) |
| `get_chunks_by_file()` через vector_store медленный | Средняя | Среднее | `index_metadata_keys=["file_path"]` + B-tree индекс |
| Удаление файлов не очищает vector_store (текущий баг) | Высокая | Высокое | Исправить в 1.6: `delete_chunks_by_file_paths` вызывает vector_store.delete() |
| File summary generation добавит latency | Средняя | Среднее | Локальная модель (qwen2.5) быстрая; ограничить N чанков |
| Module detection сработает неправильно | Низкая | Среднее | Конфиг для ручного указания modules (fallback) |
| Dual-write inconsistency до миграции | Высокая | Среднее | Сначала исправить deletion bug, потом мигрировать |

---

## ✅ КРИТЕРИИ УСПЕХА

1. **Единое хранилище**: Только `chunks_vectors` table (plus file/module summaries)
2. **Нет дублирования**: Данные в одном месте, no dual-write
3. **File summaries реальные**: `summary` поле заполнено LLM, есть `last_summarized_at`
4. **Module summaries иерархические**: Агрегация по директориям
5. **Config centralized**: Все tunable параметры в `PipelineConfig` из .env
6. **Reliability**: Retry, rate-limit, graceful shutdown
7. **Тесты проходят**: Все e2e-тесты работают с новым storage
8. **Графовая БД**: Архитектура спроектирована, готова к реализации (отдельно)

---

## 📅 ПОРЯДОК ВЫПОЛНЕНИЯ

**Фаза 0 → Фаза 1 → Фаза 2 → Фаза 3 → Фаза 5 → Фаза 6** (Фаза 4 — отдельно)

**Важно**: После каждой задачи:
- Запустить `pytest` (e2e-tests)
- Smoke test: проиндексировать 1-2 файла, проверить search и file context
- Commit с ясным сообщением

---

**Готов к реализации при вашем OK.**
