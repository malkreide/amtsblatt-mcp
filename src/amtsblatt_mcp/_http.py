"""The single pooled client, and the two gates every request passes.

Extracted from `server.py` for `ARCH-011`.

Two controls live here and both are pre-request rather than post-hoc.
`_enforce_egress_allowlist` runs as an httpx event hook, so a host outside
`ALLOWED_HOSTS` raises `EgressDenied` before a connection is opened — including
on a followed redirect, which is the case a URL check at call sites misses.
`_assert_green_params` re-checks the outgoing query string against the rubric
allow-list, so a blocked rubric cannot reach the source even if a caller path
forgot to validate.

The client is pooled process-wide, which is the point, but it binds to the event
loop that created it — hence `_reset_client`, which `tests/conftest.py` calls
around every test. Without it a client built in one test raises
`RuntimeError: Event loop is closed` on first use in the next.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from . import __version__
from ._log import log_event
from ._net import PinnedResolverTransport
from .constants import (
    _TRANSIENT_STATUS,
    ALLOWED_GAZETTE_PARAMS,
    ALLOWED_HOSTS,
    GAZETTE_BASE,
    GAZETTE_IGNORED_FILTER_THRESHOLD,
    GAZETTE_JITTER_SPREAD,
    GAZETTE_MAX_DELAY,
    GAZETTE_MAX_RETRIES,
    GAZETTE_RETRY_AFTER_JITTER,
    GAZETTE_RETRY_BACKOFF,
    GAZETTE_TOTAL_BUDGET,
    REQUEST_TIMEOUT,
    RETRY_AFTER_STATUSES,
    EgressDenied,
    GazetteFilterIgnored,
    RubricBlocked,
)
from .rubrics import explain_blocked, is_green

# ---------------------------------------------------------------------------
# HTTP plumbing
# ---------------------------------------------------------------------------


async def _enforce_egress_allowlist(request: httpx.Request) -> None:
    """httpx event hook: reject requests to hosts outside ALLOWED_HOSTS.

    Runs before send AND on each redirect (httpx fires a `request` event per
    hop when `follow_redirects=True`), so an unexpected 3xx Location cannot
    exfiltrate the request.
    """
    # SEC-004: the scheme is checked as well as the host. Checking only the
    # host left a gap that reads as covered — `http://amtsblattportal.ch/...`
    # passes an allow-list keyed on hostname while sending the request in the
    # clear. Checked first, so a plaintext URL reports the scheme rather than
    # sending the reader after the wrong problem.
    if request.url.scheme != "https":
        log_event(
            logging.ERROR,
            "egress_denied",
            reason="non_https",
            scheme=request.url.scheme,
            url=str(request.url),
        )
        raise EgressDenied(
            f"Egress over {request.url.scheme!r} is refused; HTTPS is required",
            request=request,
        )

    host = (request.url.host or "").lower()
    if host not in ALLOWED_HOSTS:
        log_event(
            logging.ERROR,
            "egress_denied",
            host=host,
            url=str(request.url),
            allowed=sorted(ALLOWED_HOSTS),
        )
        raise EgressDenied(f"Egress to host {host!r} is not in ALLOWED_HOSTS", request=request)


def _make_client() -> httpx.AsyncClient:
    """Create an async HTTP client with the egress guard installed."""
    return httpx.AsyncClient(
        timeout=REQUEST_TIMEOUT,
        headers={
            "Accept": "application/json",
            "User-Agent": f"amtsblatt-mcp/{__version__} (Swiss Public Data MCP Portfolio)",
        },
        follow_redirects=True,
        event_hooks={"request": [_enforce_egress_allowlist]},
        # SEC-004 / SEC-005: resolve once, check the address against the
        # blocklist, then connect to the address that was checked. The event
        # hook above answers "is this the name we meant?"; this answers "is this
        # the machine we meant?", which the hostname cannot.
        transport=PinnedResolverTransport(),
    )


# A single AsyncClient is shared across all requests so TCP connections and TLS
# sessions are pooled instead of re-established per call. Created lazily on
# first use (so direct tool invocation in tests works without the server
# lifespan) and closed on shutdown by the server lifespan below.
_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    """Return the shared AsyncClient, (re)creating it on first use or if closed."""
    global _client
    if _client is None or _client.is_closed:
        _client = _make_client()
    return _client


async def _close_client() -> None:
    """Close the shared client if open. Called on server shutdown."""
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
    _client = None


def _reset_client() -> None:
    """Test helper: drop the shared client between tests."""
    global _client
    _client = None


# Indirection so tests can zero the wait without patching `asyncio.sleep`
# itself. `_http.asyncio` *is* the stdlib module, so a patch there disables
# sleeping for the whole process — including foreign tests that use it to yield
# to the event loop and would then measure nothing while staying green.
_sleep = asyncio.sleep


def _parse_retry_after(resp: httpx.Response | None) -> float | None:
    """Seconds to wait per the response's ``Retry-After``, or ``None``.

    RFC 9110 section 10.2.3 allows two forms — delta-seconds (``120``) and an
    HTTP-date. Both appear in the wild, so both are read. Anything unparseable
    yields ``None`` and the caller falls back to its own curve: a malformed
    header must not become a crash on the error path, which is the one path
    already going badly.
    """
    if resp is None or resp.status_code not in RETRY_AFTER_STATUSES:
        return None
    raw = (resp.headers.get("retry-after") or "").strip()
    if not raw:
        return None
    if raw.isdigit():
        return float(raw)
    try:
        when = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None
    if when.tzinfo is None:  # RFC 9110 dates are GMT; a naive one means UTC
        when = when.replace(tzinfo=UTC)
    return max(0.0, (when - datetime.now(UTC)).total_seconds())  # past date -> now


def _retry_delay(attempt: int, resp: httpx.Response | None) -> float:
    """Seconds to wait before the next attempt (``attempt`` is 1-based).

    The cap wraps the jitter and not the other way round. ``min(cap, base) *
    jitter`` and ``min(cap, base * jitter)`` both contain a cap and a jitter;
    only the second is bounded — a value capped and then multiplied by up to
    1.5 exceeds the constant that claims to bound it. That ordering shipped in
    six portfolio servers.
    """
    hinted = _parse_retry_after(resp)
    if hinted is not None:
        return min(hinted * (1.0 + random.random() * GAZETTE_RETRY_AFTER_JITTER), GAZETTE_MAX_DELAY)
    return min(
        GAZETTE_RETRY_BACKOFF
        * attempt
        * (1.0 - GAZETTE_JITTER_SPREAD + random.random() * 2 * GAZETTE_JITTER_SPREAD),
        GAZETTE_MAX_DELAY,
    )


async def _get_with_retry(path: str, params: dict | None = None) -> httpx.Response:
    """GET a gazette endpoint under the retry policy (`ARCH-014`).

    Retries transient statuses (`_TRANSIENT_STATUS`) **and network errors**.
    The second half is the one that used to be missing entirely: `client.get`
    raising `httpx.ConnectError` escaped the loop on the first attempt, so a
    503 got three tries and a refused connection from the same outage got none.

    Each wait is jittered and capped; a `Retry-After` on a 429 or 503 beats our
    own curve. The whole call is bounded by `GAZETTE_TOTAL_BUDGET` seconds of
    wall clock — `REQUEST_TIMEOUT` is not a budget, because httpx bounds each
    operation and its read timeout restarts with every chunk.

    Raises the original `httpx` exception unwrapped so callers can branch on
    the type and read `.response` where it exists.
    """
    client = _get_client()
    deadline = time.monotonic() + GAZETTE_TOTAL_BUDGET
    last_error: Exception | None = None
    last_response: httpx.Response | None = None

    for attempt in range(1, GAZETTE_MAX_RETRIES + 1):
        if attempt > 1:
            delay = _retry_delay(attempt - 1, last_response)
            # A wait that outlasts the budget is a wait for nobody: the caller
            # has given up by the time it ends. Stop instead of sleeping.
            if delay >= deadline - time.monotonic():
                break
            await _sleep(delay)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        try:
            # `asyncio.timeout` is the wall-clock deadline the budget promises;
            # REQUEST_TIMEOUT stays alongside it as the per-operation bound.
            async with asyncio.timeout(remaining):
                r = await client.get(f"{GAZETTE_BASE}{path}", params=params)
        except TimeoutError as exc:  # the budget is gone, not just this try
            last_error = exc
            break
        except EgressDenied:
            raise  # a policy decision, not a transient failure
        except httpx.RequestError as exc:
            last_error = exc
            last_response = None
            log_event(
                logging.WARNING,
                "gazette_retry",
                path=path,
                error=type(exc).__name__,
                attempt=attempt,
            )
            continue
        if r.status_code in _TRANSIENT_STATUS and attempt < GAZETTE_MAX_RETRIES:
            last_response = r
            last_error = None
            log_event(
                logging.WARNING,
                "gazette_retry",
                path=path,
                status=r.status_code,
                attempt=attempt,
            )
            continue
        r.raise_for_status()
        return r

    if last_error is not None:
        raise last_error
    # Attempts or budget exhausted on a transient status: surface it the way a
    # non-retryable status would have been surfaced.
    assert last_response is not None  # pragma: no cover - loop guarantees one
    last_response.raise_for_status()
    return last_response  # pragma: no cover - raise_for_status always raises


async def _get_json(path: str, params: dict | None = None) -> Any:
    """GET a JSON endpoint under the shared retry policy."""
    return (await _get_with_retry(path, params)).json()


async def _get_text(path: str, params: dict | None = None) -> str:
    """GET an endpoint returning raw text (XML), same retry policy."""
    return (await _get_with_retry(path, params)).text


def _build_params(raw: dict[str, Any]) -> dict[str, Any]:
    """Build the query dict EXCLUSIVELY from the allow-list.

    `publicationStates` is mandatory upstream — omitting it yields HTTP 401,
    not 400 — so it is always injected.
    """
    params: dict[str, Any] = {"publicationStates": "PUBLISHED"}
    for key, value in raw.items():
        if value in (None, "", []):
            continue
        if key not in ALLOWED_GAZETTE_PARAMS:
            continue  # defensive: drop anything not explicitly allowed
        params[key] = value
    return params


def _assert_green_params(params: dict[str, Any]) -> None:
    """Last line of defence before the query string is built.

    Every rubric/subRubric value about to be sent is re-checked against the
    green allow-list. This duplicates the tool-level gate on purpose: it is a
    structural guarantee that no future code path can smuggle a blocked rubric
    into a request, independent of which tool constructed it.
    """
    for key in ("rubrics", "subRubrics"):
        value = params.get(key)
        if not value:
            continue
        codes = value if isinstance(value, list) else [value]
        for code in codes:
            if not is_green(code):
                log_event(logging.ERROR, "green_gate_violation", param=key, code=code)
                raise RubricBlocked(explain_blocked(code, kind=key.rstrip("s")))


async def _search(raw_params: dict[str, Any]) -> dict:
    """Run a /publications search behind the green gate and the quirk guards."""
    params = _build_params(raw_params)
    _assert_green_params(params)
    data = await _get_json("/publications", params=params)
    if not isinstance(data, dict):
        return {"content": [], "total": 0}
    total = data.get("total")
    # Plausibility check: a filtered request still reporting the whole corpus
    # means the filter was silently dropped upstream. This is the only defence
    # against a silent parameter rename on the provider side.
    if isinstance(total, int) and total > GAZETTE_IGNORED_FILTER_THRESHOLD:
        log_event(logging.ERROR, "gazette_filter_ignored", total=total, params=sorted(params))
        raise GazetteFilterIgnored(
            f"Filter wurde vom Upstream ignoriert — Ergebnis nicht vertrauenswürdig "
            f"(total={total:,}, erwartet < {GAZETTE_IGNORED_FILTER_THRESHOLD:,}). "
            "Ursache: Silent Ignore unbekannter Parameter."
        )
    return data


# ---------------------------------------------------------------------------
