"""OBS-003: structured logging — stream, format, severity levels, per-call context.

This repo had no logging tests at all, which is part of why the 2026-07-27
re-audit was able to carry OBS-003 forward as `pass` on a single line of
evidence without anyone noticing that `DEBUG` was never emitted and that
nothing correlated the events of one call.

The stdout test is the load-bearing one, and it runs in a subprocess on purpose.
On a stdio transport stdout carries the MCP protocol, so one stray line corrupts
the session — exactly the kind of thing pytest's stream capture can hide from an
in-process assertion.
"""

from __future__ import annotations

import io
import json
import logging
import subprocess
import sys
import textwrap

import pytest
import structlog

from amtsblatt_mcp._log import configure_logging, log_event, logged_tool


@pytest.fixture
def events():
    """Capture real rendered output through the production processor chain.

    `structlog.testing.capture_logs` is not usable here: it replaces the whole
    chain, dropping `merge_contextvars` and every correlation id with it — so
    the context assertions below would pass without proving anything. This
    reconfigures with `processor_chain()`, the same list production uses.
    """
    buf = io.StringIO()
    configure_logging(level=logging.DEBUG, stream=buf, force=True)
    try:
        yield lambda: [json.loads(ln) for ln in buf.getvalue().splitlines() if ln.strip()]
    finally:
        structlog.contextvars.clear_contextvars()
        configure_logging(force=True)


# --- output stream --------------------------------------------------------


def test_logger_factory_targets_stderr() -> None:
    configure_logging()
    assert structlog.get_config()["logger_factory"]._file is sys.stderr


def test_nothing_reaches_stdout(tmp_path) -> None:
    """Run a real process and check stdout is byte-for-byte empty."""
    script = textwrap.dedent(
        """
        import asyncio, logging
        from amtsblatt_mcp._log import configure_logging, log_event, logged_tool

        configure_logging()

        @logged_tool("probe")
        async def probe():
            log_event(logging.WARNING, "mid_call")
            return 1

        asyncio.run(probe())
        log_event(logging.ERROR, "after")
        """
    )
    path = tmp_path / "emit.py"
    path.write_text(script)
    proc = subprocess.run(
        [sys.executable, str(path)],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", "LOG_LEVEL": "DEBUG", "PYTHONPATH": "src"},
        cwd=".",
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == "", f"stdout must stay empty, got: {proc.stdout!r}"

    lines = [ln for ln in proc.stderr.splitlines() if ln.strip()]
    assert lines, "expected events on stderr"
    for line in lines:
        payload = json.loads(line)  # every line must parse on its own
        assert "event" in payload and "level" in payload and "timestamp" in payload


# --- severity levels ------------------------------------------------------


async def test_all_four_severity_levels_are_used(events) -> None:
    """OBS-003 asks for at least four actively used. DEBUG was the missing one."""

    @logged_tool("probe_ok")
    async def ok():
        return 1

    @logged_tool("probe_err")
    async def err():
        raise ValueError("nope")

    await ok()                                       # debug + info
    with pytest.raises(ValueError):
        await err()                                  # debug + error
    log_event(logging.WARNING, "gazette_retry", attempt=1)

    levels = {e["level"] for e in events()}
    assert {"debug", "info", "warning", "error"} <= levels, levels


async def test_errored_call_logs_type_not_message(events) -> None:
    """The exception message never reaches the log."""

    @logged_tool("probe")
    async def boom():
        raise ValueError("https://internal.example/x?token=abc123")

    with pytest.raises(ValueError):
        await boom()

    recorded = events()
    assert "token=abc123" not in json.dumps(recorded)
    errors = [e for e in recorded if e["level"] == "error"]
    assert errors and errors[0]["error_type"] == "ValueError"


# --- per-call context -----------------------------------------------------


async def test_tool_call_carries_name_status_latency_and_correlation_id(events) -> None:
    @logged_tool("gazette_probe")
    async def probe():
        return "ok"

    await probe()

    done = [e for e in events() if e["event"] == "tool_call"]
    assert len(done) == 1
    assert done[0]["tool"] == "gazette_probe"
    assert done[0]["status"] == "ok"
    assert isinstance(done[0]["latency_ms"], int)
    assert len(done[0]["correlation_id"]) == 16


async def test_correlation_id_is_stable_within_a_call(events) -> None:
    """The start and finish events must be joinable — that is the whole point."""

    @logged_tool("probe")
    async def probe():
        return 1

    await probe()

    ids = {e["correlation_id"] for e in events() if "correlation_id" in e}
    assert len(ids) == 1, f"one call produced {len(ids)} correlation ids"


async def test_correlation_ids_differ_between_calls(events) -> None:
    @logged_tool("probe")
    async def probe():
        return 1

    await probe()
    await probe()

    ids = {e["correlation_id"] for e in events() if e["event"] == "tool_call"}
    assert len(ids) == 2


async def test_nested_event_inherits_the_calls_correlation_id(events) -> None:
    """This is why structlog earns its dependency.

    The retry and egress events are emitted deep in the HTTP path and take no
    context argument. contextvars is what lets them carry the surrounding
    call's id, so an operator can join a failure to the request that caused it.
    """

    @logged_tool("probe")
    async def probe():
        log_event(logging.WARNING, "gazette_retry", attempt=2)
        return 1

    await probe()

    recorded = events()
    retry = next(e for e in recorded if e["event"] == "gazette_retry")
    done = next(e for e in recorded if e["event"] == "tool_call")
    assert retry["correlation_id"] == done["correlation_id"]
    assert retry["tool"] == "probe"


async def test_context_does_not_leak_after_the_call(events) -> None:
    """A leaked contextvar would tag unrelated later events with a stale id."""

    @logged_tool("probe")
    async def probe():
        return 1

    await probe()
    log_event(logging.INFO, "unrelated")

    after = [e for e in events() if e["event"] == "unrelated"]
    assert len(after) == 1
    assert "correlation_id" not in after[0]
    assert "tool" not in after[0]


def test_every_registered_tool_is_wrapped() -> None:
    """A tool added without @logged_tool logs nothing — catch that here."""
    import amtsblatt_mcp.server as srv

    names = [
        "gazette_search_publications",
        "gazette_search_procurement",
        "gazette_get_publication",
        "gazette_list_rubrics",
        "gazette_source_status",
    ]
    for name in names:
        assert hasattr(getattr(srv, name), "__wrapped__"), f"{name} is not wrapped"


def test_configure_logging_is_idempotent() -> None:
    configure_logging()
    first = structlog.get_config()["processors"]
    configure_logging()
    assert structlog.get_config()["processors"] is first
