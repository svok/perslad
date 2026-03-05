"""
Пример использования спанов в агентах.
Показывает как использовать константы из infra для трейсинга.
"""

from infra import SpanNames, SpanAttributes, ServiceNames, create_span_attributes
from infra.metrics import metrics_manager


def create_agent_span(agent_name: str, operation: str, **kwargs):
    """
    Создает атрибуты спана для операций агента.
    
    Пример:
        attrs = create_agent_span("my_agent", "execute", tool="calculator")
        with tracer.start_as_current_span(SpanNames.AGENT_EXECUTE, attributes=attrs):
            # выполнение агента
    """
    return create_span_attributes(
        ServiceNames.AGENTS.value,
        operation_name=operation,
        **{SpanAttributes.AGENT_NAME: agent_name, **kwargs}
    )


def create_tool_span(tool_name: str, **kwargs):
    """
    Создает атрибуты спана для операций с инструментами.
    """
    return create_span_attributes(
        ServiceNames.AGENTS.value,
        operation_name="tool_call",
        **{SpanAttributes.TOOL_NAME: tool_name, **kwargs}
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

# Инициализация метрик в main.py:
# metrics_manager.initialize(service_name="perslad-agents")

# Получение трейсера
tracer = metrics_manager.get_tracer()

if tracer:
    # Создание спана для выполнения агента
    with tracer.start_as_current_span(
        SpanNames.AGENT_EXECUTE,
        attributes=create_agent_span("my_agent", "execute", goal="solve math problem")
    ) as span:
        # Выполнение агента
        span.set_attribute("status.code", "success")
    
    # Создание спана для вызова инструмента
    with tracer.start_as_current_span(
        SpanNames.AGENT_TOOL_CALL,
        attributes=create_tool_span("calculator", input="2+2")
    ) as span:
        # Выполнение инструмента
        span.set_attribute("tool.output", "4")
        span.set_attribute("tool.success", True)
"""
