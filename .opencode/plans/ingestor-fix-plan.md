# 🛠️ ПЛАН ИСПРАВЛЕНИЙ - Ingestor Pipeline

## 📋 СОСТОЯНИЕ ПРОБЛЕМЫ

### Критический баг: ProcessorStage падает при получении poison pill (None)

**Текущий код** (processor_stage.py:38-43):
```python
if item is None:
    self.log.debug(f"[{self.name}] Worker {wid}: received poison pill, will propagate")
    self.input_queue.task_done()
    if wid == 0 and self.output_queue:
        await self.output_queue.put(None)  # ← ПРОПАГИРУЕТ poison pill
    break  # ← СТОПИТ обработку, больше не ждет новых элементов
```

**Что происходит**:
```
1. Scanner заканчивает работу → возвращает None
   ↓
2. None попадает в Queue0
   ↓
3. Processor получает None → ставит None в Queue1
   ↓
4. Processor делает break → выходит из _worker_loop
   ↓
5. Processor больше не ждет новых элементов
   ↓
6. Inotify события висят в Queue0 (никто их не обрабатывает)
```

### Источник поблемы: Scanner имеет бесконечный цикл

**Текущий код** (scanner_source_stage.py:44-104):
```python
async def generate(self) -> AsyncGenerator[FileEvent, None]:
    self.log.info(f"[scanner] generate() ENTER")

    if not self.workspace_path.exists():
        while not self._stop_event.is_set():  # ← БЕСКОНЕЧНЫЙ ЦИКЛ
            await asyncio.sleep(60)
        return

    while not self._stop_event.is_set():  # ← БЕСКОНЕЧНЫЙ ЦИКЛ
        for root, dirs, files in os.walk(self.workspace_path):
            # ... обрабатывает файлы ...
        await asyncio.sleep(60)  # ... потом ждёт 60 сек
```

**Что происходит**:
- os.walk находит все файлы только один раз
- Потом Scanner бесконечно спит по 60 секунд
- SourceStage никогда не завершается естественным образом (никогда не возвращает None)

---

## 🎯 ЦЕЛЬ ИСПРАВЛЕНИЯ

1. ✅ ProcessorStage игнорирует poison pill и продолжает работу
2. ✅ ProcessorStage продолжает ждать новых элементов даже после получения None
3. ✅ Scanner возвращает None естественным образом после сканирования
4. ✅ Pipeline работает вечно, даже когда Scanner завершен
5. ✅ Inotify события доходят до IndexerSink

---

## 🔧 ПЛАН ИСПРАВЛЕНИЙ (Variant B)

### Шаг 1: Исправить ProcessorStage._worker_loop

**Файл**: `ingestor/app/scanner/stages/processor_stage.py`

**Текущие строки 38-43**:
```python
if item is None:
    self.log.debug(f"[{self.name}] Worker {wid}: received poison pill, will propagate")
    self.input_queue.task_done()
    if wid == 0 and self.output_queue:
        await self.output_queue.put(None)
    break
```

**Требуется изменить на**:
```python
if item is None:
    self.log.debug(f"[{self.name}] Worker {wid}: received poison pill, continuing...")
    self.input_queue.task_done()
    continue
```

**Что изменяется**:
| Старый код | Новый код | Результат |
|------------|----------|-----------|
| `await self.output_queue.put(None)` | `continue` | ❌ Не пропагирует poison pill |
| `break` | `continue` | ✅ Продолжает работать |

**Логика**:
- Убираем пропагацию poison pill в следующий stage
- Убираем break (останавливает worker)
- Заменяем на continue (продолжает цикл, игнорирует None)

### Шаг 2: Восстановить ScannerSourceStage.generate()

**Файл**: `ingestor/app/scanner/stages/scanner_source_stage.py`

**Текущий код (строки 44-104)**:
```python
async def generate(self) -> AsyncGenerator[FileEvent, None]:
    self.log.info(f"[scanner] generate() ENTER")

    if not self.workspace_path.exists():
        while not self._stop_event.is_set():  # ← БЕСКОНЕЧНЫЙ ЦИКЛ
            await asyncio.sleep(60)
        return

    while not self._stop_event.is_set():  # ← БЕСКОНЕЧНЫЙ ЦИКЛ
        for root, dirs, files in os.walk(self.workspace_path):
            # ... обрабатывает файлы ...
        await asyncio.sleep(60)
```

**Требуется изменить на**:
```python
async def generate(self) -> AsyncGenerator[FileEvent, None]:
    self.log.info(f"[scanner] generate() ENTER")

    if not self.workspace_path.exists():
        self.log.error(f"[scanner] Path does not exist: {self.workspace_path}")
        return

    self.log.info("[scanner] Starting os.walk...")

    for root, dirs, files in os.walk(self.workspace_path):
        self.log.info(f"[scanner] Walking: {root}, dirs={len(dirs)}, files={len(files)}")

        # Фильтруем директории
        filtered_dirs = []
        for d in dirs:
            dir_path = Path(root) / d
            if dir_path.name.startswith('.') or dir_path.name in ('__pycache__', 'node_modules'):
                self.log.debug(f"[scanner] Skipping dir by name: {d}")
                continue
            if self.checker.should_ignore(dir_path):
                self.log.debug(f"[scanner] Skipping dir by gitignore: {d}")
                continue
            filtered_dirs.append(d)

        removed = len(dirs) - len(filtered_dirs)
        if removed:
            self.log.info(f"[scanner] Filtered {removed} dirs in {root}")
        dirs[:] = filtered_dirs

        # Обрабатываем файлы
        for filename in files:
            file_path = Path(root) / filename

            if self.checker.should_ignore(file_path):
                self.log.debug(f"[scanner] Ignoring file: {file_path}")
                continue

            try:
                rel_path = file_path.relative_to(self.workspace_path)
            except ValueError as e:
                self.log.error(f"[scanner] relative_to failed: {e}")
                continue

            self.log.info(f"[scanner] Yielding: {rel_path}")

            yield FileEvent(
                path=rel_path,
                event_type="scan",
                abs_path=file_path
            )

    self.log.info("[scanner] Scan completed")
    return
```

**Что изменяется**:
| Убираем | Добавляем | Результат |
|---------|-----------|-----------|
| `while not self._stop_event.is_set():` после проверки path exists | `return` | ✅ Scanner возвращает None |
| `while not self._stop_event.is_set():` вокруг os.walk | `return` после os.walk | ✅ Scanner завершается |
| `await asyncio.sleep(60)` после os.walk | `self.log.info("Scan completed")` | ✅ Понятное логирование |
| `if not self.workspace_path.exists():` бесконечный цикл | Просто return | ✅ Без бесконечных проверок |

**Логика**:
- Scanner просто делает os.walk один раз
- После обхода директории возвращает None
- SourceStage завершается естественным образом
- ProcessorStage получит None и продолжит работу

---

## 📝 ПОСЛЕДОВАТЕЛЬНОСТЬ ДЕЙСТВИЙ

### 1. Изменение ProcessorStage
```bash
# Изменить файл ingestor/app/scanner/stages/processor_stage.py
# Заменить строки 38-43 на строки 38-40
```

### 2. Восстановление ScannerSourceStage
```bash
# Изменить файл ingestor/app/scanner/stages/scanner_source_stage.py
# Заменить метод generate() на новый вариант
```

### 3. Перезапуск контейнера
```bash
docker-compose restart ingestor
```

### 4. Тестирование
```bash
# Создать тестовый файл
echo "test content" > /workspace/test.txt

# Проверить логи
docker-compose logs -f ingestor
```

---

## ✅ КРИТЕРИИ УСПЕХА

После исправления должно быть видно в логах:

### ProcessorStage
```
[processor] Worker 0: received poison pill, continuing...
[processor] Worker 0: calling get()...
[processor] Worker 0: got item #3: FileEvent
[processor] Worker 0: calling process()...
```

### Scanner
```
[scanner] generate() ENTER
[scanner] Walking: /workspace, dirs=1, files=2
[scanner] Yielding: test.txt
[scanner] Scan completed
```

### Inotify
```
[inotify] Inotify event: /workspace/test2.txt
[inotify] Placing FileEvent in queue
```

### Queue sizes
```
Queue0 size: 2 (файлы от Scanner и Inotify)
Queue1 size: 1 (обработанные FileEvent)
```

### Индексер
```
[indexer] Received FileEvent
[indexer] Enriched: test content
[indexer] Indexing complete
```

---

## 🚫 ЧТО НЕ ДОЛЖНО МЕНЯТЬСЯ

1. ❌ Никаких очисток очередей
2. ❌ Никаких дополнительных источников данных
3. ❌ Никаких дополнительных stages
4. ❌ Никаких бесконечных циклов в Processor
5. ❌ Никаких сложных паттернов
6. ❌ Никаких дополнительных источников кроме Scanner и Inotify

---

## 🔍 ЧТО ЯВЛЯЕТСЯ ИСПРАВЛЕНИЕМ

**Исправление** (то, что изменится):
- ProcessorStage._worker_loop: `continue` вместо `break` + `put(None)`
- ScannerSourceStage.generate(): убрать бесконечные циклы, вернуть None

**НЕ исправление** (оставить как есть):
- EnrichStage - работает как надо
- InotifySourceStage - работает как надо
- Queue0/Queue1 - структура остается
- IndexerSink - работоспособность сохраняется

---

## 📊 ТЕСТОВЫЙ СЦЕНАРИЙ

### Сценарий 1: Scanner завершается первым
```
1. Перезапуск контейнера
2. Scanner находит 2 файла → возвращает None
3. Processor получает None, делает continue, продолжает ждать
4. Inotify обнаруживает новый файл → помещает в Queue0
5. Processor получает FileEvent → обрабатывает
6. Enrich обрабатывает → помещает в Queue1
7. IndexerSink получает → индексирует
8. Queue0 пуст (все обработано), Processor продолжает ждать новые элементы
```

### Сценарий 2: Inotify завершается первым (если когда-то будет)
```
1. Перезапуск контейнера
2. Inotify обнаруживает изменения → помещает в Queue0
3. Processor получает FileEvent → обрабатывает
4. Enrich обрабатывает → помещает в Queue1
5. IndexerSink получает → индексирует
6. Queue0 пуст, Processor продолжает ждать
7. Scanner позже найдет файл → поместит в Queue0
8. Processor получит FileEvent → продолжит обрабатывать
```

---

## ⚠️ ТРЕБУЕТ ОДОБРЕНИЯ

**План включает**:
1. Изменение ProcessorStage._worker_loop (удалить 2 строки, добавить continue)
2. Изменение ScannerSourceStage.generate() (удалить бесконечные циклы)

**Утверждать перед выполнением**: Да

**Следующий шаг**: Подтвердить план, я выполню изменения.