"""Tests for the retry policy against the gazette (ARCH-014).

A portfolio run of the audit catalogue on 2026-08-07 read `_get_json` and
`_get_text` by hand. They were the same loop twice, and it was missing every
property the check asks for — including the one that matters most in an outage:
it caught no network errors at all. `client.get` raising `httpx.ConnectError`
escaped the loop on the first attempt, so a 503 got three tries and a refused
connection from the same outage got none.

Every property has a counter-check. The previous implementation is the honest
thing to measure against, because it was in production until this branch.
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import httpx
import pytest
import respx

from amtsblatt_mcp import _http
from amtsblatt_mcp.constants import GAZETTE_BASE, GAZETTE_MAX_RETRIES, EgressDenied

PATH = "/api/v1/publications"
URL = f"{GAZETTE_BASE}{PATH}"


@pytest.fixture(autouse=True)
def _no_backoff(monkeypatch):
    """Zero the wait without disabling `asyncio.sleep` for the process.

    Patched on `_http._sleep`. `monkeypatch.setattr(_http.asyncio, "sleep", …)`
    would look local and reach the stdlib module — every test that uses
    `asyncio.sleep` to yield to the event loop would then measure nothing and
    stay green. `test_the_no_backoff_fixture_leaves_asyncio_sleep_alone` guards
    the seam.
    """

    async def _instant(_seconds: float) -> None:
        return None

    monkeypatch.setattr(_http, "_sleep", _instant)


def _resp(status: int, retry_after: str | None = None) -> httpx.Response:
    headers = {"Retry-After": retry_after} if retry_after is not None else {}
    return httpx.Response(status, headers=headers, json={"content": []})


# --- Retry-After: read at all, and both RFC 9110 forms -----------------------


def test_retry_after_reads_delta_seconds():
    assert _http._parse_retry_after(_resp(429, "120")) == 120.0


def test_retry_after_reads_an_http_date():
    when = datetime.now(UTC) + timedelta(seconds=60)
    got = _http._parse_retry_after(_resp(503, format_datetime(when, usegmt=True)))
    assert got is not None
    assert 55 <= got <= 61


def test_retry_after_treats_a_past_date_as_now():
    when = datetime.now(UTC) - timedelta(hours=1)
    assert _http._parse_retry_after(_resp(503, format_datetime(when, usegmt=True))) == 0.0


def test_retry_after_reads_a_naive_date_as_gmt_not_local():
    when = datetime.now(UTC) + timedelta(seconds=30)
    got = _http._parse_retry_after(_resp(503, when.strftime("%a, %d %b %Y %H:%M:%S")))
    assert got is not None
    assert 25 <= got <= 31


@pytest.mark.parametrize("raw", ["", "   ", "soon", "not-a-date"])
def test_an_unreadable_retry_after_falls_back_instead_of_crashing(raw):
    assert _http._parse_retry_after(_resp(429, raw)) is None


def test_retry_after_is_ignored_where_it_means_nothing():
    assert _http._parse_retry_after(_resp(500, "120")) is None
    assert _http._parse_retry_after(None) is None


# --- Jitter, and the cap that has to come after it ---------------------------


def test_the_delay_is_spread_not_deterministic():
    draws = {_http._retry_delay(1, None) for _ in range(50)}
    assert len(draws) > 1, "a fixed ladder brings every client back at the same moment"


def test_a_retry_after_delay_is_spread_one_sided():
    draws = [_http._retry_delay(1, _resp(429, "5")) for _ in range(50)]
    assert len(set(draws)) > 1
    assert all(5.0 <= d <= 6.25 for d in draws), sorted(draws)[:3]


def test_the_cap_is_a_real_bound_not_a_midpoint():
    # Jitter is random — one draw proves nothing.
    for attempt in range(1, 40):
        for _ in range(10):
            assert _http._retry_delay(attempt, None) <= _http.GAZETTE_MAX_DELAY
            assert _http._retry_delay(attempt, _resp(429, "86400")) <= _http.GAZETTE_MAX_DELAY


def test_capping_before_the_jitter_would_not_have_been_a_bound():
    """Counter-check for the ordering, so the test above is known to fail."""
    broken = min(_http.GAZETTE_RETRY_BACKOFF * 100, _http.GAZETTE_MAX_DELAY) * 1.5
    assert broken > _http.GAZETTE_MAX_DELAY


# --- What is retried ---------------------------------------------------------


@respx.mock
async def test_a_network_error_is_retried():
    """The core finding: the loop caught no network errors at all.

    `client.get` raising `ConnectError` escaped on the first attempt, so a 503
    got three tries and a refused connection from the same outage got none.
    """
    route = respx.get(URL).mock(side_effect=[httpx.ConnectError("refused"), _resp(200)])
    assert await _http._get_json(PATH) == {"content": []}
    assert route.call_count == 2


@respx.mock
async def test_a_read_timeout_is_retried():
    route = respx.get(URL).mock(side_effect=[httpx.ReadTimeout("slow"), _resp(200)])
    assert await _http._get_json(PATH) == {"content": []}
    assert route.call_count == 2


@respx.mock
async def test_a_network_error_that_never_clears_is_raised_unwrapped():
    respx.get(URL).mock(side_effect=httpx.ConnectError("refused"))
    with pytest.raises(httpx.ConnectError):
        await _http._get_json(PATH)


@respx.mock
async def test_a_500_is_retried():
    # `_TRANSIENT_STATUS` was {502, 503, 504}: a 500 fell through to
    # raise_for_status() on the first attempt.
    route = respx.get(URL).mock(side_effect=[_resp(500), _resp(200)])
    assert await _http._get_json(PATH) == {"content": []}
    assert route.call_count == 2


@respx.mock
async def test_a_429_is_retried():
    route = respx.get(URL).mock(side_effect=[_resp(429), _resp(200)])
    assert await _http._get_json(PATH) == {"content": []}
    assert route.call_count == 2


@respx.mock
async def test_a_404_fails_fast():
    route = respx.get(URL).mock(return_value=httpx.Response(404))
    with pytest.raises(httpx.HTTPStatusError):
        await _http._get_json(PATH)
    assert route.call_count == 1, "a third attempt does not turn a 404 into a 200"


@respx.mock
async def test_attempts_are_bounded_and_the_status_still_surfaces():
    route = respx.get(URL).mock(return_value=_resp(503))
    with pytest.raises(httpx.HTTPStatusError):
        await _http._get_json(PATH)
    assert route.call_count == GAZETTE_MAX_RETRIES


@respx.mock
async def test_an_egress_denial_is_not_retried():
    """A policy decision, not a transient failure.

    Retrying it would hammer the guard and hide the reason behind a delay.
    """
    route = respx.get(URL).mock(side_effect=EgressDenied("blocked"))
    with pytest.raises(EgressDenied):
        await _http._get_json(PATH)
    assert route.call_count == 1


@respx.mock
async def test_get_text_shares_the_same_policy():
    """The two entry points used to be the same loop written twice.

    They now share `_get_with_retry`; this pins that the text path did not stay
    behind on the old one.
    """
    route = respx.get(URL).mock(
        side_effect=[httpx.ConnectError("refused"), httpx.Response(200, text="<xml/>")]
    )
    assert await _http._get_text(PATH) == "<xml/>"
    assert route.call_count == 2


# --- The budget, measured on the wall clock ----------------------------------


@respx.mock
async def test_a_slow_response_is_cut_by_the_wall_clock_deadline(monkeypatch):
    """The assertion a fake clock cannot refute.

    A clock that only advances when something sleeps cannot disprove a claim
    about *real* time: the code that ignores the wall clock never sleeps, so no
    time passes and the broken version stays green. This test sleeps for real —
    deliberately, and it is the only one here that does.
    """
    monkeypatch.setattr(_http, "GAZETTE_TOTAL_BUDGET", 0.05)

    async def _slow(request):
        await asyncio.sleep(0.30)
        return _resp(200)

    respx.get(URL).mock(side_effect=_slow)
    started = time.monotonic()
    with pytest.raises(TimeoutError):
        await _http._get_json(PATH)
    assert time.monotonic() - started < 0.25, "REQUEST_TIMEOUT is not a budget"


@respx.mock
async def test_a_wait_that_would_outlast_the_budget_is_not_taken(monkeypatch):
    monkeypatch.setattr(_http, "GAZETTE_TOTAL_BUDGET", 1.0)
    monkeypatch.setattr(_http, "_retry_delay", lambda *_a, **_k: 999.0)
    route = respx.get(URL).mock(return_value=_resp(503))
    with pytest.raises(httpx.HTTPStatusError):
        await _http._get_json(PATH)
    assert route.call_count == 1


# --- The seam ----------------------------------------------------------------


async def test_the_no_backoff_fixture_leaves_asyncio_sleep_alone():
    """Guards the seam the autouse fixture patches.

    `monkeypatch.setattr(_http.asyncio, "sleep", …)` would look local and reach
    the stdlib module, disabling sleeping for the whole process — including
    foreign tests that use it to yield to the event loop, which then measure
    nothing and stay green. That is how a concurrency check broke in
    `srgssr-mcp` without turning red.
    """
    started = time.monotonic()
    await asyncio.sleep(0.05)
    assert time.monotonic() - started >= 0.04, "asyncio.sleep is disabled process-wide"
