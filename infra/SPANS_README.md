# Константы спанов (Span Constants)

Этот модуль содержит набор констант для работы с OpenTelemetry спанами и Phoenix метриками.

## Структура

### SpanAttributes
Ключевые атрибуты для всех спанов:
- `SERVICE_NAME` - имя сервиса
- `TRACE_ID` - ID трейса
- `SPAN_ID` - ID спана
- `SPAN_NAME` - имя спана
- `LLM_PROMPT`, `LLM_RESPONSE` - для LLM операций
- `INGESTOR_SOURCE`, `INGESTOR_DOCUMENT_ID` - для ингестора
- `AGENT_NAME`, `AGENT_TOOL` - для агентов
- `EVAL_METRIC_NAME`, `EVAL_METRIC_VALUE` - для оценки качества

### SpanNames
Стандартные имена спанов (StrEnum):
- `LLM_COMPLETION`, `LLM_CHAT`, `LLM_EMBEDDING` - LLM операции
- `INGESTOR_PROCESS`, `INGESTOR_CHUNK`, `INGESTOR_EMBED` - операции ингестора
- `AGENT_EXECUTE`, `AGENT_TOOL_CALL` - операции агентов
- `EVALUATION_GENERATE`, `EVALUATION_ASSESS` - операции оценки
- `DATA_PROCESS`, `DATA_TRANSFORM` - операции с данными
- `HTTP_REQUEST`, `DATABASE_QUERY` - системные операции

### QualityMetrics
Метрики качества для аннотаций в Phoenix:
- `ACCURACY` - точность
- `RELEVANCE` - релевантность
- `TOOL_CORRECTNESS` - корректность инструментов
- `HALLUCINATIONS` - галлюцинации
- `COHERENCE` - связность
- `SCORE`, `EXPLANATION` - пользовательские метрики

### ServiceNames
Названия сервисов:
- `AGENTS` - агенты
- `INGESTOR` - ингестор
- `METRICS_LOADER` - метрик-лоадер
- `API` - API
- `WORKER` - воркер

## Использование

### Базовый пример
```python
from infra import SpanNames, SpanAttributes, ServiceNames, create_span_attributes

# Создание атрибутов спана
attrs = create_span_attributes(
    ServiceNames.AGENTS.value,
    agent_name="my_agent",
    tool="calculator"
)

# Использование в коде
tracer = metrics_manager.get_tracer()
with tracer.start_as_current_span(SpanNames.AGENT_EXECUTE, attributes=attrs):
    # выполнение операции
    pass
```

### Для LLM
```python
from infra import SpanNames, SpanAttributes, create_span_attributes

attrs = create_span_attributes(
    "llm",
    model="gpt-4",
    provider="openai"
)

with tracer.start_as_current_span(SpanNames.LLM_COMPLETION, attributes=attrs):
    # вызов LLM
    pass
```

### Для ингестора
```python
from infra import SpanNames, SpanAttributes, create_span_attributes

attrs = create_span_attributes(
    "ingestor",
    source="file",
    document_id="doc123"
)

with tracer.start_as_current_span(SpanNames.INGESTOR_PROCESS, attributes=attrs):
    # обработка документа
    pass
```

### Для метрик качества
```python
from infra import QualityMetrics, get_quality_annotation_name

# Получение имени аннотации для метрики
annotation_name = get_quality_annotation_name(
    QualityMetrics.ACCURACY.value,
    "llm.completion"
)
# -> "metric_accuracy_llm_completion"

# Использование в Phoenix client
annotation = SpanAnnotationData(
    name=annotation_name,
    annotator_kind="CODE",
    span_id=span_id,
    metadata={"score": 0.95}
)
```

## Добавление новых спанов

Чтобы добавить новый спан:

1. Добавьте имя в `SpanNames` (если это новая операция)
2. Добавьте атрибуты в `SpanAttributes` (если нужны новые атрибуты)
3. Добавьте метрику в `QualityMetrics` (если нужна новая метрика качества)
4. Обновите `__all__` в `__init__.py`

## Интеграция с подпроектами

### Agents
См. `agents/app/tracing.py` для примеров использования.

### Ingestor
См. `ingestor/services/tracing.py` для примеров использования.

### Metrics Loader
См. `metrics_loader/main.py` для примеров использования метрик качества.
