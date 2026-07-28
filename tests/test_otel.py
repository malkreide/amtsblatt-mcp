"""OBS-006: a root span per tool call.

Auto-instrumentation gives HTTP client spans, which is not the same thing:
without a root span per tool call, a trace shows the requests a tool made and
never the call that made them — and a tool that fails *before* reaching the
network produces no trace at all. `test_span_is_recorded_when_no_http_happens`
is the test for that second case.
"""

from __future__ import annotations

import pytest

pytest.importorskip("opentelemetry.sdk")

from opentelemetry import trace  # noqa: E402
from opentelemetry.sdk.trace import TracerProvider  # noqa: E402
from opentelemetry.sdk.trace.export import SimpleSpanProcessor  # noqa: E402
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (  # noqa: E402
    InMemorySpanExporter,
)

from amtsblatt_mcp._log import logged_tool  # noqa: E402

# The tracer provider is process-global and `set_tracer_provider` ignores repeat
# calls, so it is installed once here. A per-test fixture that tried to install
# its own provider silently got no spans after the first test — which is how the
# first version of this file "passed" one test and failed five.
_EXPORTER = InMemorySpanExporter()
_PROVIDER = TracerProvider()
_PROVIDER.add_span_processor(SimpleSpanProcessor(_EXPORTER))
trace.set_tracer_provider(_PROVIDER)


@pytest.fixture
def spans():
    _EXPORTER.clear()
    yield _EXPORTER
    _EXPORTER.clear()


async def test_span_carries_the_tool_name(spans) -> None:
    @logged_tool("gazette_search_publications")
    async def tool():
        return "ok"

    await tool()
    (span,) = spans.get_finished_spans()
    assert span.attributes["mcp.tool.name"] == "gazette_search_publications"
    assert span.name == "mcp.tool/gazette_search_publications"


async def test_span_records_success(spans) -> None:
    @logged_tool("gazette_source_status")
    async def tool():
        return "ok"

    await tool()
    (span,) = spans.get_finished_spans()
    assert span.attributes["mcp.tool.result.is_error"] is False


async def test_span_records_an_error_without_the_message(spans) -> None:
    """The type only: an exception message can carry upstream content, and
    OBS-002 keeps that away from the model and the logs alike."""

    @logged_tool("gazette_get_publication")
    async def tool():
        raise RuntimeError("upstream said /srv/secret/app.py exploded")

    with pytest.raises(RuntimeError):
        await tool()

    (span,) = spans.get_finished_spans()
    assert span.attributes["mcp.tool.result.is_error"] is True
    assert span.attributes["mcp.tool.error_type"] == "RuntimeError"
    assert "/srv/secret" not in str(span.attributes)


async def test_span_is_recorded_when_no_http_happens(spans) -> None:
    """The gap auto-instrumentation leaves: a tool refused by the allow-list
    never opens a connection, so httpx spans alone would show nothing at all."""

    @logged_tool("gazette_search_publications")
    async def tool():
        return "Die Rubrik «KK» steht nicht auf der Freigabe-Liste."

    await tool()
    assert len(spans.get_finished_spans()) == 1


async def test_span_carries_the_correlation_id(spans) -> None:
    """The id is what joins a span to the log line holding the detail — which
    is why the span itself carries no argument values."""

    @logged_tool("gazette_list_rubrics")
    async def tool():
        return "ok"

    await tool()
    (span,) = spans.get_finished_spans()
    assert len(span.attributes["mcp.correlation_id"]) == 16


async def test_span_carries_no_argument_values(spans) -> None:
    """Tool arguments include free-text keywords a user typed. Putting them in
    a span moves them into a backend with different retention and access than
    this server's own logs."""

    @logged_tool("gazette_search_publications")
    async def tool(keyword: str):
        return "ok"

    await tool(keyword="a-very-distinctive-search-term")
    (span,) = spans.get_finished_spans()
    assert "a-very-distinctive-search-term" not in str(span.attributes)
