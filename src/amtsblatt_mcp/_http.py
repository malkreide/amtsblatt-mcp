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
    GAZETTE_MAX_RETRIES,
    GAZETTE_RETRY_BACKOFF,
    REQUEST_TIMEOUT,
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


async def _get_json(path: str, params: dict | None = None) -> Any:
    """GET a JSON endpoint with retry on transient 5xx (502/503/504)."""
    client = _get_client()
    for attempt in range(1, GAZETTE_MAX_RETRIES + 1):
        r = await client.get(f"{GAZETTE_BASE}{path}", params=params)
        if r.status_code in _TRANSIENT_STATUS and attempt < GAZETTE_MAX_RETRIES:
            log_event(
                logging.WARNING,
                "gazette_retry",
                path=path,
                status=r.status_code,
                attempt=attempt,
            )
            await asyncio.sleep(GAZETTE_RETRY_BACKOFF * attempt)
            continue
        r.raise_for_status()
        return r.json()


async def _get_text(path: str, params: dict | None = None) -> str:
    """GET an endpoint returning raw text (XML), with the same retry policy."""
    client = _get_client()
    for attempt in range(1, GAZETTE_MAX_RETRIES + 1):
        r = await client.get(f"{GAZETTE_BASE}{path}", params=params)
        if r.status_code in _TRANSIENT_STATUS and attempt < GAZETTE_MAX_RETRIES:
            log_event(
                logging.WARNING,
                "gazette_retry",
                path=path,
                status=r.status_code,
                attempt=attempt,
            )
            await asyncio.sleep(GAZETTE_RETRY_BACKOFF * attempt)
            continue
        r.raise_for_status()
        return r.text


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
