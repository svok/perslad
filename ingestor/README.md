# Ingestor

Batch-компонент для индексации кода и документации.

## Архитектура

```
┌─────────────────────────────────────────────────┐
│                   Ingestor                      │
├─────────────────────────────────────────────────┤
│                                                 │
│  ┌──────────────┐      ┌──────────────┐         │
│  │  HTTP API    │      │  Pipeline    │         │
│  │              │      │              │         │
│  │ - LLM Lock   │      │ 1. Scan      │         │
│  │ - Health     │      │ 2. Parse     │         │
│  │ - Stats      │      │ 3. Enrich    │         │
│  │ - Knowledge  │      │ 4. Embed     │         │
│  │   Port       │      │ 5. Persist   │         │
│  └──────────────┘      └──────────────┘         │
│         │                      │                │
│         └──────────┬───────────┘                │
│                    │                            │
│            ┌───────▼────────┐                   │
│            │    Storage     │                   │
│            │  (Postgres)    │                   │
│            │    or Memory   │                   │
│            └────────────────┘                   │
│                                                 │
└─────────────────────────────────────────────────┘
```

## Компоненты

### Pipeline

Ingestor обрабатывает код в последовательности этапов:

1. **Scan** — поиск файлов в workspace, фильтрация по расширениям
2. **Parse** — разделение кода на чанки (функции, классы) через LlamaIndex splitters
3. **Enrich** — генерация описаний для чанков и extraction purpose (использует LLM)
4. **Embed** — вычисление векторных представлений
5. **Persist** — сохранение в storage (Postgres или memory)

### LLM Lock Manager

Координирует доступ к LLM между agent и ingestor:

- Agent отправляет `POST /system/llm_lock` с `locked=true`
- Ingestor приостанавливает LLM-зависимые операции
- TTL защищает от deadlock
- Agent разблокирует через `POST /system/llm_lock` с `locked=false`

### Knowledge Port

Единственная точка интеграции с агентом:

- `POST /knowledge/search` — поиск по embedding
- `GET /knowledge/file/{path}` — контекст файла
- `GET /knowledge/overview` — обзор проекта

**Гарантия**: агент НИКОГДА не получает всю базу (max 50 KB per request).

### Storage

Поддерживает два backend'а через adapter pattern:

- **Memory**: in-process storage, быстрый для разработки, без persistence
- **PostgreSQL**: production-ready с pgvector, atomic операции, async API

**Архитектурный принцип**: storage полностью изолирован, изменение backend не требует изменений кода API.

### Configuration

Config разделен на модули по concerns:

- `runtime.py` — ENV, LOG_LEVEL, порт
- `storage.py` — тип storage, PostgreSQL connection
- `llm.py` — LLM endpoints, embeddings
- `llm_lock.py` — агент communication URL

## Запуск

### Локально

```bash
pip install -r requirements.txt
export WORKSPACE=/path/to/repo
export OPENAI_API_BASE=http://localhost:8000/v1
export STORAGE_TYPE=postgres
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export POSTGRES_DB=rag
export POSTGRES_USER=rag
export POSTGRES_PASSWORD=rag
python -m ingestor.main
```

### Docker

```bash
docker-compose up -d
docker-compose logs -f ingestor
```

## API Endpoints

### System

- `GET /` — статус сервиса
- `GET /health` — health check
- `GET /stats` — статистика storage

### LLM Lock (для агента)

- `POST /system/llm_lock` — установить блокировку
  ```json
  {"locked": true, "ttl_seconds": 300}
  ```
- `GET /system/llm_lock` — состояние блокировки

### Knowledge Port (для агента)

- `POST /knowledge/search` — поиск по embedding
- `GET /knowledge/file/{path}` — контекст файла
- `GET /knowledge/overview` — обзор проекта

## Принципы

1. **Детерминированность** — можно перезапустить в любой момент
2. **Изоляция** — storage — внутренняя деталь
3. **Координация** — уважает LLM lock от агента
4. **Эффективность** — батчинг, параллелизм где возможно
5. **Fail-safe** — TTL защищает от deadlock
6. **Extensibility** — adapter pattern для storage, modular config
