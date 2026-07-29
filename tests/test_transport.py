"""Transport selection: streamable-http by default, SSE deprecated but working.

Until 0.18.0 this server spoke SSE and nothing else, which is why `SCALE-002`
carried the note that `MCP_STATELESS` "is not available here". Spec `2026-07-28`
reclassified HTTP+SSE as deprecated with a twelve-month removal window and
removed protocol-level sessions outright, so the transport had to move.

It moved *alongside* rather than *instead*: the endpoint changes from
`/sse` + `/messages` to `/mcp`, and this server is cloud-deployed. A hard
cutover would break every client at once on an upgrade, which is exactly what a
deprecation window exists to avoid. SSE therefore still builds, still carries
the full middleware stack, and logs a warning naming the deadline.
"""

from __future__ import annotations

import io
import json
import logging

import pytest
import structlog

from amtsblatt_mcp import server as srv
from amtsblatt_mcp._log import configure_logging

API_KEY = "test-key-not-a-real-secret"


@pytest.fixture(autouse=True)
def _api_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MCP_API_KEY", API_KEY)
    monkeypatch.delenv("MCP_CORS_ORIGINS", raising=False)
    monkeypatch.delenv("MCP_STATELESS", raising=False)


def _paths(app) -> set[str]:
    return {p for p in (getattr(r, "path", None) for r in app.routes) if p}


def test_streamable_http_serves_the_spec_endpoint() -> None:
    """`/mcp` is the path a 2026-07-28 client expects to find."""
    assert _paths(srv.build_http_app("streamable-http")) == {"/mcp"}


def test_sse_still_serves_its_legacy_pair() -> None:
    """Deprecated is not removed — a deployed client must keep working."""
    assert _paths(srv.build_http_app("sse")) == {"/sse", "/messages"}


def test_streamable_http_is_the_default() -> None:
    """Calling without a kind must not silently give back the deprecated one."""
    assert _paths(srv.build_http_app()) == {"/mcp"}


# --- MCP_STATELESS: reachable for the first time ---------------------------


def _record(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Capture what `build_http_app` actually asks the SDK for.

    Asserted at the call rather than through a global, because `stateless_http`
    is an argument of `streamable_http_app()` in `mcp` 2.x — there is no
    setting to read back afterwards, and the value that reaches the SDK is the
    one that matters anyway.
    """
    seen: dict = {}
    real = srv.mcp.streamable_http_app

    def _spy(*args, **kwargs):
        seen.update(kwargs)
        return real(*args, **kwargs)

    monkeypatch.setattr(srv.mcp, "streamable_http_app", _spy)
    return seen


def test_stateless_reaches_the_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reading the env var and never applying it is the failure this catches."""
    monkeypatch.setenv("MCP_STATELESS", "1")
    seen = _record(monkeypatch)
    srv.build_http_app("streamable-http")
    assert seen.get("stateless_http") is True


def test_stateless_is_off_unless_asked_for(monkeypatch: pytest.MonkeyPatch) -> None:
    """The negative control: the flag must not ride along by accident."""
    seen = _record(monkeypatch)
    srv.build_http_app("streamable-http")
    assert seen.get("stateless_http") is False


def test_sse_never_reaches_the_streamable_builder(monkeypatch: pytest.MonkeyPatch) -> None:
    """SSE has no stateless mode; building it as if it had would misreport.

    Telling an operator they run session-free when they do not is worse than
    refusing, because it reads as enforced.
    """
    monkeypatch.setenv("MCP_STATELESS", "1")

    def _explode(*_args, **_kwargs):
        raise AssertionError("SSE must not be built through streamable_http_app")

    monkeypatch.setattr(srv.mcp, "streamable_http_app", _explode)
    srv.build_http_app("sse")  # must not raise


# --- the deprecation is announced, not silent ------------------------------


@pytest.fixture
def events():
    """Capture rendered output through the production processor chain.

    `caplog` sees nothing here: structlog writes to its own stderr factory
    rather than propagating through the stdlib root logger. Same approach and
    same reason as the fixture in `test_logging.py` — reconfigure onto a buffer
    with the real chain, so what is asserted is what production emits.
    """
    buf = io.StringIO()
    configure_logging(level=logging.DEBUG, stream=buf, force=True)
    try:
        yield lambda: [json.loads(ln) for ln in buf.getvalue().splitlines() if ln.strip()]
    finally:
        structlog.contextvars.clear_contextvars()
        configure_logging(force=True)


def test_building_sse_warns_with_the_migration_path(events) -> None:
    """A deadline nobody can see is not a deadline.

    The warning has to name the replacement *and* the endpoint change, because
    the endpoint is the part that silently breaks a client config.
    """
    srv.build_http_app("sse")
    warn = [e for e in events() if e.get("event") == "sse_transport_deprecated"]
    assert len(warn) == 1, "the deprecation must be announced exactly once per build"
    assert warn[0]["level"] == "warning"
    assert "streamable-http" in warn[0]["hint"]
    assert "/mcp" in warn[0]["hint"]


def test_building_streamable_http_does_not_warn(events) -> None:
    """The negative control: a warning on every start would be ignored on both."""
    srv.build_http_app("streamable-http")
    assert not [e for e in events() if e.get("event") == "sse_transport_deprecated"]


def test_the_built_transport_is_recorded(events) -> None:
    """An operator reading the logs must be able to tell which one is running."""
    srv.build_http_app("streamable-http")
    built = [e for e in events() if e.get("event") == "http_app_built"]
    assert len(built) == 1
    assert built[0]["transport"] == "streamable-http"
    assert built[0]["stateless"] is False


# --- the dispatch table ----------------------------------------------------


def test_every_http_transport_name_is_dispatchable() -> None:
    """`HTTP_TRANSPORTS` and the builder must not drift apart.

    `main()` decides by membership in this set; a name in the set that the
    builder cannot serve would fail at startup instead of at import.
    """
    for name in srv.HTTP_TRANSPORTS:
        kind = "sse" if name == "sse" else "streamable-http"
        assert _paths(srv.build_http_app(kind))


def test_http_transports_contains_the_documented_names() -> None:
    assert srv.HTTP_TRANSPORTS == {"streamable-http", "http", "sse"}
