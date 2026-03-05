import os
import logging
from typing import Optional

from openinference.semconv.resource import ResourceAttributes
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

try:
    from openinference.instrumentation.langchain import LangChainInstrumentor
except ImportError:
    LangChainInstrumentor = None

logger = logging.getLogger(__name__)


class MetricsManager:
    """Manager for observability metrics using OpenTelemetry."""

    def __init__(self):
        self._provider: Optional[TracerProvider] = None
        self._enabled: bool = False

    def initialize(self, service_name: str = "perslad-agent") -> None:
        """Initialize OpenTelemetry tracer."""
        otlp_endpoint = os.getenv("OTLP_ENDPOINT", "http://phoenix:6006/v1/traces")
        project_name = os.getenv("PHOENIX_PROJECT_NAME", "perslad")

        if otlp_endpoint:
            try:
                # === Используем новые атрибуты ===
                resource = Resource(attributes={
                    ResourceAttributes.PROJECT_NAME: project_name,
                })

                self._provider = TracerProvider(resource=resource)
                trace.set_tracer_provider(self._provider)

                if not otlp_endpoint.endswith("/v1/traces"):
                    otlp_endpoint = f"{otlp_endpoint.rstrip('/')}/v1/traces"

                logger.info(f"Initializing OTLP HTTP exporter to {otlp_endpoint} for project {project_name}")

                otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
                span_processor = SimpleSpanProcessor(otlp_exporter)

                self._provider.add_span_processor(span_processor)

                if LangChainInstrumentor is not None:
                    try:
                        LangChainInstrumentor().instrument()
                        logger.info("✅ LangChain instrumentation enabled")
                    except Exception as e:
                        logger.warning(f"⚠️ Failed to instrument LangChain: {e}")
                else:
                    logger.info("ℹ️ LangChain instrumentation not available")

                self._enabled = True
                logger.info(f"✅ OTLP metrics initialized (endpoint: {otlp_endpoint})")

            except Exception as e:
                logger.warning(f"⚠️ Failed to initialize OTLP: {e}")
                self._enabled = False
        else:
            logger.info("ℹ️ OpenTelemetry not configured (OTLP_ENDPOINT not set)")
            self._enabled = False

    def instrument_fastapi(self, app) -> None:
        """Instrument FastAPI app with OpenTelemetry."""
        if self._enabled:
            try:
                FastAPIInstrumentor.instrument_app(app)
                logger.info("✅ FastAPI instrumentation enabled")
            except Exception as e:
                logger.warning(f"⚠️ Failed to instrument FastAPI: {e}")

    def is_enabled(self) -> bool:
        return self._enabled

    def get_tracer(self):
        """Get the OpenTelemetry tracer."""
        if self._enabled:
            return trace.get_tracer(__name__)
        return None


# Global instance
metrics_manager = MetricsManager()