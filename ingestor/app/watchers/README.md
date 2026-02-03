# File Watchers

Модуль для индексации файлов с поддержкой gitignore и двух типов источников:

- **Full scan**: полный скан workspace для проверки изменений
- **Notifier**: runtime monitoring с native inotify (C)

## Структура

```
watchers/
├── __init__.py          # Exports
├── base.py              # BaseFileSource - базовый класс с gitignore
├── scanner.py           # FileScannerSource - полный скан
└── notifier.py          # FileNotifierSource - runtime watching
```

## Использование

### 1. Full Workspace Scan (при старте)

```python
from ingestor.app.watchers import FileScannerSource

scanner = FileScannerSource(
    workspace_path="/workspace",
    storage=storage,
    on_files_changed=lambda files: index_files(files)
)

await scanner.start()
```

**Как работает:**
1. Загружает все файлы из БД для получения min_mtime
2. Сканирует workspace и сравнивает:
   - Новые файлы (mtime > min_mtime) → индексация
   - Измененные файлы (mtime изменился или checksum изменился) → индексация
3. Отправляет список файлов для индексации

### 2. Runtime Monitoring (во время работы)

```python
from ingestor.app.watchers import FileNotifierSource

notifier = FileNotifierSource(
    workspace_path="/workspace",
    storage=storage,
    on_file_event=lambda file_path, event_type: handle_event(file_path, event_type)
)

await notifier.start()
```

**События:**
- `create`: файл создан → индексация
- `delete`: файл удален → удаление из БД
- `rename`: файл переименован → обновление путей
- `modified`: файл изменен → переиндексация

**Фильтрация:**
Автоматически применяет .gitignore фильтры

## Базовый класс

```python
class BaseFileSource:
    """Базовый класс с gitignore поддержкой"""

    def _load_gitignore_matchers() -> None
        # Загружает все .gitignore файлы

    def _should_ignore_path(path) -> bool
        # Проверяет, нужно ли игнорировать путь

    def _calculate_file_metadata(file_path) -> FileSummary
        # Расчитывает mtime, checksum, размер
```

**Особенности:**
- Оптимизирован для парсинга всех .gitignore файлов
- Кэширует matchers для повторных вызовов
- Безопасная работа с путями

## Indexer Orchestrator

Упрощенный координатор:

```python
from ingestor.app.indexer import IndexerOrchestrator

indexer = IndexerOrchestrator(
    workspace_path="/workspace",
    llm=llm,
    lock_manager=lock_manager,
    storage=storage,
    knowledge_port=knowledge_port,
)

# Старстует watcher
await indexer.start()

# Запускает full scan
await indexer.start_full_scan()

# Управление:
await indexer.stop()
```

## Сравнение: Scanner vs Notifier

| Feature | FileScannerSource | FileNotifierSource |
|---------|-------------------|-------------------|
| Use Case | Startup | Runtime |
| Event Type | Callback with list | Callback per file |
| Filtering | Gitignore ✓ | Gitignore ✓ |
| Performance | Scan all files | Poll changes only |
| Memory | Streams batches | Event-based |

## Dependencies

- **inotify-simple** (==2.0.1) - Native inotify wrapper (C)
- **gitignore-parser** - Gitignore support

## Пример

```python
from ingestor.app.watchers import BaseFileSource, FileScannerSource, FileNotifierSource

# Инициализируем источник с gitignore
source = BaseFileSource("/workspace")

# Проверяем, нужно ли игнорировать файл
if source._should_ignore_path(Path("src/main.py")):
    print("File will be ignored")
else:
    print("File will be indexed")

# Full scan при старте
scanner = FileScannerSource(
    workspace_path="/workspace",
    storage=storage,
    on_files_changed=handle_files
)

# Runtime watching
notifier = FileNotifierSource(
    workspace_path="/workspace",
    storage=storage,
    on_file_event=handle_event
)
```

## TODO

- [ ] Улучшить обработку RENAME событий
- [ ] Добавить debounce для повторных событий
- [ ] Rate limiting для горячих файлов
- [ ] Lazy checksum calculation
