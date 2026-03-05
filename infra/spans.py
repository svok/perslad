"""
Константы для определения спанов и их атрибутов.
Используется для согласованной работы с OpenTelemetry и Phoenix во всех подпроектах.
"""

from enum import StrEnum
from typing import Final


class SpanAttributes:
    """OpenTelemetry span attributes (ключевые атрибуты для всех спанов)."""
    
    # Базовые атрибуты трейсинга
    TRACE_ID: Final[str] = "trace_id"
    SPAN_ID: Final[str] = "span_id"
    SPAN_NAME: Final[str] = "span_name"
    
    # Сервис и окружение
    SERVICE_NAME: Final[str] = "service.name"
    SERVICE_VERSION: Final[str] = "service.version"
    ENVIRONMENT: Final[str] = "environment"
    DEPLOYMENT_ENV: Final[str] = "deployment.environment"
    
    # Контекст операции
    OPERATION_NAME: Final[str] = "operation.name"
    OPERATION_TYPE: Final[str] = "operation.type"
    USER_ID: Final[str] = "user.id"
    SESSION_ID: Final[str] = "session.id"
    
    # Для LLM операций
    LLM_PROMPT: Final[str] = "llm.prompt"
    LLM_RESPONSE: Final[str] = "llm.response"
    LLM_MODEL: Final[str] = "llm.model"
    LLM_PROVIDER: Final[str] = "llm.provider"
    LLM_TOKEN_COUNT_PROMPT: Final[str] = "llm.token_count.prompt"
    LLM_TOKEN_COUNT_COMPLETION: Final[str] = "llm.token_count.completion"
    
    # Для ингестора
    INGESTOR_SOURCE: Final[str] = "ingestor.source"
    INGESTOR_DOCUMENT_ID: Final[str] = "ingestor.document_id"
    INGESTOR_DOCUMENT_TYPE: Final[str] = "ingestor.document_type"
    INGESTOR_CHUNK_ID: Final[str] = "ingestor.chunk_id"
    
    # Для агентов
    AGENT_NAME: Final[str] = "agent.name"
    AGENT_TOOL: Final[str] = "agent.tool"
    AGENT_GOAL: Final[str] = "agent.goal"
    
    # Для инструментов (tools)
    TOOL_NAME: Final[str] = "tool.name"
    TOOL_INPUT: Final[str] = "tool.input"
    TOOL_OUTPUT: Final[str] = "tool.output"
    TOOL_SUCCESS: Final[str] = "tool.success"
    
    # Для оценки качества
    EVAL_METRIC_NAME: Final[str] = "eval.metric_name"
    EVAL_METRIC_VALUE: Final[str] = "eval.metric_value"
    EVAL_GROUND_TRUTH: Final[str] = "eval.ground_truth"
    EVAL_PREDICTION: Final[str] = "eval.prediction"
    
    # Статус выполнения
    STATUS_CODE: Final[str] = "status.code"
    STATUS_MESSAGE: Final[str] = "status.message"
    ERROR_TYPE: Final[str] = "error.type"
    ERROR_MESSAGE: Final[str] = "error.message"


class SpanNames(StrEnum):
    """Стандартные имена спанов для разных типов операций."""
    
    # ===== LLM ОПЕРАЦИИ =====
    LLM_COMPLETION = "llm.completion"
    LLM_CHAT = "llm.chat"
    LLM_EMBEDDING = "llm.embedding"
    LLM_RERANK = "llm.rerank"
    
    # ===== ИНГЕСТОР ОПЕРАЦИИ =====
    INGESTOR_PROCESS = "ingestor.process"
    INGESTOR_CHUNK = "ingestor.chunk"
    INGESTOR_EMBED = "ingestor.embed"
    INGESTOR_STORE = "ingestor.store"
    
    # ===== АГЕНТСКИЕ ОПЕРАЦИИ =====
    AGENT_EXECUTE = "agent.execute"
    AGENT_THINK = "agent.think"
    AGENT_PLAN = "agent.plan"
    AGENT_TOOL_CALL = "agent.tool_call"
    
    # ===== ОЦЕНКА КАЧЕСТВА =====
    EVALUATION_GENERATE = "evaluation.generate"
    EVALUATION_ASSESS = "evaluation.assess"
    EVALUATION_JUDGE = "evaluation.judge"
    QUALITY_CHECK = "quality.check"
    
    # ===== РАБОТА С ДАННЫМИ =====
    DATA_PROCESS = "data.process"
    DATA_TRANSFORM = "data.transform"
    DATA_VALIDATE = "data.validate"
    
    # ===== СИСТЕМНЫЕ ОПЕРАЦИИ =====
    HTTP_REQUEST = "http.request"
    DATABASE_QUERY = "database.query"
    FILE_OPERATION = "file.operation"


class QualityMetrics(StrEnum):
    """Метрики качества для аннотаций в Phoenix."""
    
    # Основные метрики
    ACCURACY = "metric_accuracy"
    RELEVANCE = "metric_relevance"
    TOOL_CORRECTNESS = "metric_tool_correctness"
    HALLUCINATION = "metric_hallucination"
    
    # Дополнительные метрики
    COHERENCE = "metric_coherence"
    FLUENCY = "metric_fluency"
    SAFETY = "metric_safety"
    FAITHFULNESS = "metric_faithfulness"
    
    # Пользовательские метрики
    SCORE = "score"
    EXPLANATION = "explanation"
    RATING = "rating"


class ServiceNames(StrEnum):
    """Названия сервисов в системе."""
    
    AGENTS = "agents"
    INGESTOR = "ingestor"
    METRICS_LOADER = "metrics-loader"
    API = "api"
    WORKER = "worker"


def get_span_name(service: str, operation: str) -> str:
    """
    Формирует имя спана на основе сервиса и операции.
    
    Примеры:
        get_span_name("agents", "execute") -> "agents.execute"
        get_span_name("ingestor", "process") -> "ingestor.process"
    """
    return f"{service}.{operation}"


def create_span_attributes(service: str, **kwargs) -> dict:
    """
    Создает атрибуты спана с автоматическим добавлением сервиса.
    
    Пример:
        create_span_attributes("agent", agent_name="my_agent", tool="calculator")
        -> {"service.name": "agent", "agent.name": "my_agent", "tool.name": "calculator"}
    """
    attrs = {SpanAttributes.SERVICE_NAME: service}
    attrs.update(kwargs)
    return attrs


def get_quality_annotation_name(metric: str, span_name: str) -> str:
    """
    Формирует имя аннотации для метрики качества.
    
    Пример:
        get_quality_annotation_name("metric_accuracy", "llm.completion")
        -> "metric_accuracy_llm_completion"
    """
    # Заменяем точки на подчеркивания для корректных имен аннотаций
    safe_span_name = span_name.replace(".", "_")
    return f"{metric}_{safe_span_name}"


# Экспорты для удобного импорта
__all__ = [
    "SpanAttributes",
    "SpanNames",
    "QualityMetrics",
    "ServiceNames",
    "get_span_name",
    "create_span_attributes",
    "get_quality_annotation_name",
]