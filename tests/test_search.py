"""Search, procurement, pagination, deduplication and graceful degradation."""

from __future__ import annotations

import json
from time import monotonic

import httpx
import pytest
import respx

from amtsblatt_mcp import server
from amtsblatt_mcp.server import (
    GAZETTE_BASE,
    ProcurementInput,
    SearchInput,
    _procurement_scope,
    _reset_rubrics_cache,
    _to_bool,
    search_procurement,
    search_publications,
)

from .fixtures import (
    MOCK_RUBRICS,
    MOCK_SEARCH,
    MOCK_SEARCH_CORPUS,
    MOCK_SEARCH_EMPTY,
    MOCK_SEARCH_MULTILANG,
    MOCK_SEARCH_PAGE_2,
)


@pytest.fixture(autouse=True)
def _clear_caches():
    _reset_rubrics_cache()
    yield
    _reset_rubrics_cache()


def _seed_rubrics():
    server._rubrics_cache = (monotonic(), MOCK_RUBRICS)


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_green_rubric_search_returns_hits_with_source_url():
    _seed_rubrics()
    with respx.mock:
        route = respx.get(f"{GAZETTE_BASE}/publications").mock(
            return_value=httpx.Response(200, json=MOCK_SEARCH)
        )
        result = await search_publications(SearchInput(rubric="OB-BS"))

    assert route.calls[0].request.url.params.get("rubrics") == "OB-BS"
    assert "Trambeschaffung" in result
    assert "fbf0ff9e-3e28-4e09-8a1e-32a7aa4cea8f" in result
    # Every hit carries a resolvable source URL.
    assert "amtsblattportal.ch" in result
    assert "provenance: live_api" in result


@pytest.mark.asyncio
async def test_canton_filter_is_sent():
    _seed_rubrics()
    with respx.mock:
        route = respx.get(f"{GAZETTE_BASE}/publications").mock(
            return_value=httpx.Response(200, json=MOCK_SEARCH)
        )
        await search_publications(SearchInput(rubric="RP-ZH", canton="ZH"))

    params = route.calls[0].request.url.params
    assert params.get("cantons") == "ZH"
    assert params.get("rubrics") == "RP-ZH"
    # The mandatory upstream parameter is always injected.
    assert params.get("publicationStates") == "PUBLISHED"


@pytest.mark.asyncio
async def test_json_format_returns_structured_payload():
    _seed_rubrics()
    with respx.mock:
        respx.get(f"{GAZETTE_BASE}/publications").mock(
            return_value=httpx.Response(200, json=MOCK_SEARCH)
        )
        result = await search_publications(
            SearchInput(rubric="OB-BS", response_format="json")
        )
    data = json.loads(result)
    assert data["count"] == 2
    assert data["scope"] == "green_rubrics_only"
    assert data["attribution"].startswith("Data: amtsblattportal.ch")
    assert data["results"][0]["url"].startswith("https://www.amtsblattportal.ch")


@pytest.mark.asyncio
async def test_empty_result_is_not_an_error():
    _seed_rubrics()
    with respx.mock:
        respx.get(f"{GAZETTE_BASE}/publications").mock(
            return_value=httpx.Response(200, json=MOCK_SEARCH_EMPTY)
        )
        result = await search_publications(SearchInput(rubric="OB-BS"))
    assert "Keine Treffer" in result
    assert "Fehler" not in result


# ---------------------------------------------------------------------------
# Language deduplication
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_language_duplicates_in_result():
    """The same notice in de+it must be reported once, not twice."""
    _seed_rubrics()
    with respx.mock:
        respx.get(f"{GAZETTE_BASE}/publications").mock(
            return_value=httpx.Response(200, json=MOCK_SEARCH_MULTILANG)
        )
        result = await search_publications(
            SearchInput(rubric="OB-TI", response_format="json")
        )
    data = json.loads(result)
    assert data["count"] == 2, "the de/it pair should collapse to one entry"
    numbers = [r["publicationNumber"] for r in data["results"]]
    assert len(numbers) == len(set(numbers))
    # The requested language wins.
    assert data["results"][0]["language"] == "de"
    assert "Concorso" not in json.dumps(data["results"][0])


@pytest.mark.asyncio
async def test_dedup_prefers_the_requested_language():
    _seed_rubrics()
    with respx.mock:
        respx.get(f"{GAZETTE_BASE}/publications").mock(
            return_value=httpx.Response(200, json=MOCK_SEARCH_MULTILANG)
        )
        result = await search_publications(
            SearchInput(rubric="OB-TI", language="it", response_format="json")
        )
    data = json.loads(result)
    first = data["results"][0]
    assert first["language"] == "it"
    assert first["title"] == "Concorso servizi di pulizia"


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pagination_sends_page_and_size():
    _seed_rubrics()
    with respx.mock:
        route = respx.get(f"{GAZETTE_BASE}/publications").mock(
            return_value=httpx.Response(200, json=MOCK_SEARCH_PAGE_2)
        )
        await search_publications(SearchInput(rubric="OB-BS", limit=2, page=1))

    params = route.calls[0].request.url.params
    assert params.get("pageRequest.size") == "2"
    assert params.get("pageRequest.page") == "1"


@pytest.mark.asyncio
async def test_pagination_across_a_page_boundary():
    """Page 0 reports more available; page 1 returns the remainder."""
    _seed_rubrics()
    with respx.mock:
        respx.get(f"{GAZETTE_BASE}/publications").mock(
            return_value=httpx.Response(
                200, json={**MOCK_SEARCH, "total": 3}
            )
        )
        page0 = await search_publications(SearchInput(rubric="OB-BS", limit=2, page=0))
    assert "page=1" in page0, "must tell the caller how to fetch the rest"

    _seed_rubrics()
    with respx.mock:
        respx.get(f"{GAZETTE_BASE}/publications").mock(
            return_value=httpx.Response(200, json=MOCK_SEARCH_PAGE_2)
        )
        page1 = await search_publications(SearchInput(rubric="OB-BS", limit=2, page=1))
    assert "Schulmobiliar Basel" in page1
    # No overlap between the pages.
    assert "Trambeschaffung" not in page1


@pytest.mark.asyncio
async def test_limit_is_capped_client_side():
    """The upstream imposes no cap, so the client must."""
    _seed_rubrics()
    with respx.mock:
        route = respx.get(f"{GAZETTE_BASE}/publications").mock(
            return_value=httpx.Response(200, json=MOCK_SEARCH)
        )
        await search_publications(SearchInput(rubric="OB-BS", limit=100))
    assert route.calls[0].request.url.params.get("pageRequest.size") == "100"

    with pytest.raises(ValueError):
        SearchInput(rubric="OB-BS", limit=101)


# ---------------------------------------------------------------------------
# Boolean normalisation
# ---------------------------------------------------------------------------


def test_to_bool_normalises_inconsistent_encodings():
    for truthy in (True, 1, "true", "TRUE", " True ", "1", "yes", "ja"):
        assert _to_bool(truthy) is True, truthy
    for falsy in (False, 0, "false", "FALSE", "0", "no", "nein", ""):
        assert _to_bool(falsy) is False, falsy


def test_to_bool_string_false_is_not_truthy():
    """The bug this helper exists to prevent: bool('false') is True."""
    assert bool("false") is True
    assert _to_bool("false") is False


def test_to_bool_uses_the_default_for_null_and_junk():
    assert _to_bool(None) is False
    assert _to_bool(None, default=True) is True
    assert _to_bool(object(), default=True) is True


# ---------------------------------------------------------------------------
# Procurement
# ---------------------------------------------------------------------------


def test_procurement_scope_for_an_active_canton():
    rubrics, subs, warnings = _procurement_scope("BS", False)
    assert rubrics == ["OB-BS"]
    assert warnings == []


def test_procurement_scope_without_canton_covers_active_rubrics_only():
    rubrics, _, _ = _procurement_scope(None, False)
    assert set(rubrics) == {"OB-AR", "OB-BS", "OB-TI"}
    assert "OB-BL" not in rubrics
    # OB-ZG exists in the taxonomy but was never filled after the simap
    # switch — it is not an active procurement rubric.
    assert "OB-ZG" not in rubrics


def test_procurement_scope_include_inactive_adds_historical_rubrics():
    rubrics, _, _ = _procurement_scope(None, True)
    assert {"OB-BL", "OB-VS"} <= set(rubrics)


def test_procurement_scope_zg_is_inactive_not_active():
    """OB-ZG exists in the taxonomy but was never filled after the simap
    switch (0 publications). It must be treated as inactive, not active."""
    # Not part of the default (active-only) sweep.
    active, _, _ = _procurement_scope(None, False)
    assert "OB-ZG" not in active
    # A direct query without include_inactive explains instead of searching.
    rubrics, _, warnings = _procurement_scope("ZG", False)
    assert rubrics == []
    assert any("inaktiv" in w or "leer" in w for w in warnings)


@pytest.mark.asyncio
async def test_procurement_for_zurich_explains_simap_and_makes_no_call():
    """The canonical 'explanation instead of empty result' case."""
    _seed_rubrics()
    with respx.mock:
        route = respx.get(f"{GAZETTE_BASE}/publications").mock(
            return_value=httpx.Response(200, json=MOCK_SEARCH)
        )
        result = await search_procurement(ProcurementInput(canton="ZH"))

    assert route.call_count == 0
    assert "simap.ch" in result
    assert "ZH" in result
    assert "Keine Treffer" not in result


@pytest.mark.asyncio
async def test_procurement_inactive_canton_warns_before_searching():
    _seed_rubrics()
    with respx.mock:
        route = respx.get(f"{GAZETTE_BASE}/publications").mock(
            return_value=httpx.Response(200, json=MOCK_SEARCH)
        )
        result = await search_procurement(ProcurementInput(canton="BL"))
    assert route.call_count == 0
    assert "inaktiv" in result
    assert "include_inactive" in result


@pytest.mark.asyncio
async def test_procurement_multi_rubric_search_sends_all_active_codes():
    _seed_rubrics()
    with respx.mock:
        route = respx.get(f"{GAZETTE_BASE}/publications").mock(
            return_value=httpx.Response(200, json=MOCK_SEARCH)
        )
        await search_procurement(ProcurementInput(keyword="Informatik"))

    sent = set(route.calls[0].request.url.params.get_list("rubrics"))
    assert sent == {"OB-AR", "OB-BS", "OB-TI"}


@pytest.mark.asyncio
async def test_procurement_warns_when_keyword_looks_like_a_cpv_code():
    _seed_rubrics()
    with respx.mock:
        respx.get(f"{GAZETTE_BASE}/publications").mock(
            return_value=httpx.Response(200, json=MOCK_SEARCH)
        )
        result = await search_procurement(ProcurementInput(keyword="72000000"))
    assert "CPV" in result


# ---------------------------------------------------------------------------
# Graceful degradation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_api_unreachable_returns_explanation_not_empty_result():
    _seed_rubrics()
    with respx.mock:
        respx.get(f"{GAZETTE_BASE}/publications").mock(
            side_effect=httpx.ConnectError("connection refused")
        )
        result = await search_publications(SearchInput(rubric="OB-BS"))

    assert "nicht erreichbar" in result
    assert "KEIN leeres Ergebnis" in result
    assert "Keine Treffer" not in result
    assert "Traceback" not in result


@pytest.mark.asyncio
async def test_timeout_is_reported_as_a_timeout():
    _seed_rubrics()
    with respx.mock:
        respx.get(f"{GAZETTE_BASE}/publications").mock(
            side_effect=httpx.TimeoutException("timed out")
        )
        result = await search_publications(SearchInput(rubric="OB-BS"))
    assert "Timeout" in result


@pytest.mark.asyncio
async def test_transient_5xx_is_retried_then_succeeds():
    _seed_rubrics()
    server.GAZETTE_RETRY_BACKOFF = 0.0
    with respx.mock:
        route = respx.get(f"{GAZETTE_BASE}/publications").mock(
            side_effect=[
                httpx.Response(503),
                httpx.Response(200, json=MOCK_SEARCH),
            ]
        )
        result = await search_publications(SearchInput(rubric="OB-BS"))
    assert route.call_count == 2
    assert "Trambeschaffung" in result


@pytest.mark.asyncio
async def test_missing_publication_states_401_is_explained_as_a_param_problem():
    """A 401 here means 'you forgot publicationStates', not 'log in'."""
    _seed_rubrics()
    with respx.mock:
        respx.get(f"{GAZETTE_BASE}/publications").mock(
            return_value=httpx.Response(401, json={"error": "AccessDenied"})
        )
        result = await search_publications(SearchInput(rubric="OB-BS"))
    assert "publicationStates" in result
    assert "unauthentifiziert" in result


@pytest.mark.asyncio
async def test_silently_ignored_filter_is_detected_by_the_plausibility_guard():
    """A filtered request reporting the full corpus must not be trusted."""
    _seed_rubrics()
    with respx.mock:
        respx.get(f"{GAZETTE_BASE}/publications").mock(
            return_value=httpx.Response(200, json=MOCK_SEARCH_CORPUS)
        )
        result = await search_publications(SearchInput(rubric="OB-BS"))
    assert "ignoriert" in result
    assert "nicht vertrauenswürdig" in result


# ---------------------------------------------------------------------------
# Live tests (excluded from CI with -m "not live")
# ---------------------------------------------------------------------------


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_procurement_basel_stadt():
    _reset_rubrics_cache()
    result = await search_procurement(ProcurementInput(canton="BS", limit=5))
    assert "amtsblattportal.ch" in result
    assert "Fehler" not in result


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_blocked_rubric_still_refuses():
    _reset_rubrics_cache()
    result = await search_publications(SearchInput(rubric="KK", keyword="Muster"))
    assert "fail-closed" in result
