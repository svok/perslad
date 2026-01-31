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
│            │  (in-memory)   │                   │
│            └────────────────┘                   │
│                                                 │
└─────────────────────────────────────────────────┘
```

## Компоненты

### Pipeline Stages

1. **Scan** (NO LLM)
   - Сканирует workspace
   - Фильтрует файлы по расширениям
   - Исключает служебные директории

2. **Parse** (NO LLM)
   - Использует LlamaIndex splitters
   - Разбивает код на функции/классы
   - Разбивает документы на секции

3. **Enrich** (LOCAL LLM)
   - Генерирует summaries для чанков
   - Извлекает purpose
   - Уважает LLM lock от агента

4. **Embed** (NO LLM reasoning)
   - Вычисляет embeddings
   - Батчинг для эффективности
   - Можно делать при LLM lock

5. **Persist** (NO LLM)
   - Сохраняет в storage
   - Атомарные операции

### LLM Lock Manager

Координирует доступ к LLM между agent и ingestor:

- Agent отправляет `POST /system/llm_lock` с `locked=true`
- Ingestor приостанавливает LLM-зависимые операции
- TTL защищает от deadlock
- Agent разблокирует через `POST /system/llm_lock` с `locked=false`

### Knowledge Port

Единственная точка интеграции с агентом:

- `POST /knowledge/search` - поиск по embedding
- `GET /knowledge/file/{path}` - контекст файла
- `GET /knowledge/overview` - обзор проекта

**Гарантия**: агент НИКОГДА не получает всю базу (max 50 KB per request).

## Запуск

### Локально

```bash
# Установка зависимостей
pip install -r requirements.txt

# Переменные окружения
export WORKSPACE=/path/to/repo
export OPENAI_API_BASE=http://localhost:8000/v1
export OPENAI_API_KEY=dummy
export INGESTOR_PORT=8001

# Запуск
python -m ingestor.app.main
```

### Docker

```bash
docker build -f ingestor/Dockerfile -t ingestor .
docker run -v /path/to/repo:/workspace \
  -e OPENAI_API_BASE=http://llm:8000/v1 \
  -p 8001:8001 \
  ingestor
```

## API Endpoints

### System

- `GET /` - статус сервиса
- `GET /health` - health check
- `GET /stats` - статистика storage

### LLM Lock (для агента)

- `POST /system/llm_lock` - установить блокировку
  ```json
  {"locked": true, "ttl_seconds": 300}
  ```
- `GET /system/llm_lock` - получить состояние блокировки

### Knowledge Port (для агента)

- `POST /knowledge/search` - поиск по embedding
  ```json
  {
    "query_embedding": [...],
    "top_k": 5
  }
  ```
- `GET /knowledge/file/{path}` - контекст файла
- `GET /knowledge/overview` - обзор проекта

### Debug

- `GET /chunks?limit=10` - список чанков

## Конфигурация

Через переменные окружения:

- `WORKSPACE` - путь к репозиторию (default: `/workspace`)
- `INGESTOR_PORT` - порт HTTP API (default: `8001`)
- `OPENAI_API_BASE` - URL LLM сервера
- `OPENAI_API_KEY` - API ключ
- `ENV` - окружение (`dev`/`prod`)

## Принципы

1. **Детерминированность**: можно перезапустить в любой момент
2. **Изоляция**: storage — внутренняя деталь
3. **Координация**: уважает LLM lock от агента
4. **Эффективность**: батчинг, параллелизм где возможно
5. **Fail-safe**: TTL защищает от deadlock

## Будущее

- [ ] Incremental indexing (file watcher)
- [ ] Hierarchical summaries (cloud LLM)
- [ ] Postgres storage
- [ ] gRPC API
- [ ] Distributed processing
