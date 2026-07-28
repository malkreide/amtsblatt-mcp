"""Optional OpenTelemetry wiring for amtsblatt-mcp.

Activates only when `OTEL_EXPORTER_OTLP_ENDPOINT` is set in the environment.
The opentelemetry packages are an opt-in extra (`pip install amtsblatt-mcp[otel]`);
without them this module logs a warning and stays silent — no hard dependency.
"""

from __future__ import annotations

import logging
import os

from . import __version__ as _VERSION
from ._log import log_event


def init_otel() -> bool:
    """Install OTLP tracing if configured. Returns True when active."""
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    if not endpoint:
        return False
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        log_event(
            logging.WARNING,
            "otel_disabled_missing_deps",
            endpoint=endpoint,
            hint="install amtsblatt-mcp[otel]",
        )
        return False

    resource = Resource.create(
        {
            "service.name": os.environ.get("OTEL_SERVICE_NAME", "amtsblatt-mcp"),
            "service.version": os.environ.get("OTEL_SERVICE_VERSION", _VERSION),
        }
    )
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
    trace.set_tracer_provider(provider)
    HTTPXClientInstrumentor().instrument()
    log_event(logging.INFO, "otel_enabled", endpoint=endpoint)
    return True
