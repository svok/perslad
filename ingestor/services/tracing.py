"""
Пример использования спанов в ingestor.
Показывает как использовать константы из infra для трейсинга.
"""

from infra import SpanNames, SpanAttributes, ServiceNames, create_span_attributes
from infra.metrics import metrics_manager


def create_ingestor_span(operation: str, **kwargs):
    """
    Создает атрибуты спана для операций ингестора.
    
    Пример:
        attrs = create_ingestor_span("process", source="file", document_id="doc123")
        with tracer.start_as_current_span(SpanNames.INGESTOR_PROCESS, attributes=attrs):
            # выполнение операции
    """
    return create_span_attributes(
        ServiceNames.INGESTOR.value,
        operation_name=operation,
        **kwargs
    )


def create_chunk_span(chunk_id: str, document_id: str, **kwargs):
    """
    Создает атрибуты спана для операций с чанками.
    """
    return create_span_attributes(
        ServiceNames.INGESTOR.value,
        operation_name="chunk",
        **{SpanAttributes.INGESTOR_CHUNK_ID: chunk_id,
           SpanAttributes.INGESTOR_DOCUMENT_ID: document_id,
           **kwargs}
    )


def get_tracer():
    """Получает трейсер из менеджера метрик."""
    if metrics_manager.is_enabled():
        return metrics_manager.get_tracer()
    return None


# Пример использования в коде:
"""
from infra.metrics import metrics_manager
from infra import SpanNames, get_quality_annotation_name

# Инициализация метрик в main.py уже есть:
# metrics_manager.initialize(service_name="perslad-ingestor")

# Получение трейсера
tracer = metrics_manager.get_tracer()

if tracer:
    # Создание спана для операции ингестора
    with tracer.start_as_current_span(
        SpanNames.INGESTOR_PROCESS,
        attributes=create_ingestor_span("process", source="file", document_id="doc123")
    ) as span:
        # Выполнение операции
        span.set_attribute("status.code", "success")
"""
