"""
Infrastructure primitives.

This package contains low-level building blocks for interacting
with external systems (LLM, MCP, network, lifecycle).

No business logic.
No framework dependencies.
"""

from .exceptions import PersladError
from .spans import (
    SpanAttributes,
    SpanNames,
    QualityMetrics,
    ServiceNames,
    get_span_name,
    create_span_attributes,
    get_quality_annotation_name,
)

__all__ = [
    "PersladError",
    "SpanAttributes",
    "SpanNames",
    "QualityMetrics",
    "ServiceNames",
    "get_span_name",
    "create_span_attributes",
    "get_quality_annotation_name",
]
