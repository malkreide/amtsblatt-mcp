"""Optional OpenTelemetry wiring for amtsblatt-mcp.

Activates only when `OTEL_EXPORTER_OTLP_ENDPOINT` is set in the environment.
The opentelemetry packages are an opt-in extra (`pip install amtsblatt-mcp[otel]`);
without them this module logs a warning and stays silent — no hard dependency.
"""

from __future__ import annotations

import contextlib
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


def tool_span(tool_name: str, correlation_id: str):
    """Context manager yielding a span for one tool call (OBS-006).

    Auto-instrumentation gives HTTP client spans, which is not the same thing:
    without a root span per tool call, a trace shows the requests a tool made
    and never the call that made them, and a tool that fails *before* reaching
    the network produces no trace at all.

    Returns a no-op context manager when OpenTelemetry is absent or unconfigured,
    so the caller needs no branch and the import stays optional.

    Deliberately carries no argument values. Tool arguments here include free-text
    keywords and rubric codes; a keyword is a search term a user typed, and
    putting it in a span attribute moves it into a telemetry backend with a
    different retention and access model than this server's own logs. The
    correlation id is enough to join a span to the log line that has the detail.
    """
    try:
        from opentelemetry import trace
    except ImportError:
        return contextlib.nullcontext()

    tracer = trace.get_tracer("amtsblatt-mcp")
    span_cm = tracer.start_as_current_span(f"mcp.tool/{tool_name}")

    @contextlib.contextmanager
    def _managed():
        with span_cm as span:
            span.set_attribute("mcp.tool.name", tool_name)
            span.set_attribute("mcp.correlation_id", correlation_id)
            try:
                yield span
            except Exception as exc:
                span.set_attribute("mcp.tool.result.is_error", True)
                # The type only — the message can carry upstream content, and
                # OBS-002 keeps that away from the model and the logs alike.
                span.set_attribute("mcp.tool.error_type", type(exc).__name__)
                raise
            else:
                span.set_attribute("mcp.tool.result.is_error", False)

    return _managed()
