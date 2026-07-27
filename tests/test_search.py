"""Search, procurement, pagination, deduplication and graceful degradation."""

from __future__ import annotations

import json
from time import monotonic

import httpx
import pytest
import respx

from amtsblatt_mcp import server
from amtsblatt_mcp.rubrics import is_green
from amtsblatt_mcp.server import (
    GAZETTE_BASE,
    ProcurementInput,
    SearchInput,
    _procurement_scope,
    _reset_rubrics_cache,
    _to_bool,
    gazette_search_procurement,
    gazette_search_publications,
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
        result = await gazette_search_publications(SearchInput(rubric="OB-BS"))

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
        await gazette_search_publications(SearchInput(rubric="RP-ZH", canton="ZH"))

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
        result = await gazette_search_publications(
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
        result = await gazette_search_publications(SearchInput(rubric="OB-BS"))
    assert "Keine Treffer" in result
    assert "Fehler" not in result


# ---------------------------------------------------------------------------
# Language deduplication
# ---------------------------------------------------------------------------


async def _multilang_search(**kwargs) -> dict:
    _seed_rubrics()
    with respx.mock:
        respx.get(f"{GAZETTE_BASE}/publications").mock(
            return_value=httpx.Response(200, json=MOCK_SEARCH_MULTILANG)
        )
        result = await gazette_search_publications(
            SearchInput(rubric="OB-TI", response_format="json", **kwargs)
        )
    return json.loads(result)


@pytest.mark.asyncio
async def test_identical_body_language_pair_collapses():
    """it/fr of the same tender differ only in the form prefix -> one entry.

    Regression guard: the two records carry DIFFERENT publicationNumbers
    (…2892 / …2893), so the old publicationNumber key never collapsed them.
    """
    data = await _multilang_search()
    titles = [r["title"] for r in data["results"]]
    assert sum("NUOVO CENTRO SPORTIVO" in t for t in titles) == 2, (
        "expected exactly the tender and its correction, not the fr duplicate"
    )
    assert not any(t.startswith("Appel d’offres - NUOVO") for t in titles)
    ids = [r["id"] for r in data["results"]]
    assert len(ids) == len(set(ids))


@pytest.mark.asyncio
async def test_correction_never_collapses_into_its_tender():
    """"Bando - X" and "Rettifica Bando - X" are different publications.

    Same rubric, same sub-rubric, same day, same body — only the form prefix
    separates them. Collapsing them would silently drop a correction.
    """
    data = await _multilang_search()
    titles = [r["title"] for r in data["results"]]
    assert any(t.startswith("Bando - NUOVO") for t in titles)
    assert any(t.startswith("Rettifica Bando - NUOVO") for t in titles)


@pytest.mark.asyncio
async def test_translated_bodies_survive_and_are_flagged():
    """AR publishes de/fr with translated titles — not collapsible, so reported."""
    data = await _multilang_search()
    titles = [r["title"] for r in data["results"]]
    assert any("Muldenmiete" in t for t in titles)
    assert any("Location et transport" in t for t in titles)
    assert data["language_mix"] == {"it": 2, "de": 1, "fr": 1}
    assert data["warnings"], "a multilingual result set must carry the caveat"
    assert "only_language" in data["warnings"][0]


@pytest.mark.asyncio
async def test_collapse_prefers_the_requested_language():
    data = await _multilang_search(language="fr")
    titles = [r["title"] for r in data["results"]]
    assert any(t.startswith("Appel d’offres - NUOVO") for t in titles)
    assert not any(t.startswith("Bando - NUOVO") for t in titles)


@pytest.mark.asyncio
async def test_only_language_returns_a_single_language_view():
    data = await _multilang_search(language="it", only_language=True)
    assert {r["language"] for r in data["results"]} == {"it"}
    assert data["language_mix"] == {"it": 2}
    # Single-language sets carry no multilingual caveat.
    assert not data["warnings"]


@pytest.mark.asyncio
async def test_unknown_form_prefix_is_never_collapsed():
    """Fail-closed: a prefix outside the literal map must not merge records."""
    from amtsblatt_mcp.server import _collapse_language_variants

    rows = [
        {"id": "1", "rubric": "OB-TI", "subRubric": "OB-TI10",
         "publicationDate": "2026-07-24", "language": "it",
         "title": "Comunicazione straordinaria - Progetto X"},
        {"id": "2", "rubric": "OB-TI", "subRubric": "OB-TI10",
         "publicationDate": "2026-07-24", "language": "fr",
         "title": "Communication extraordinaire - Progetto X"},
    ]
    assert len(_collapse_language_variants(rows, "de")) == 2


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
        await gazette_search_publications(SearchInput(rubric="OB-BS", limit=2, page=1))

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
        page0 = await gazette_search_publications(SearchInput(rubric="OB-BS", limit=2, page=0))
    assert "page=1" in page0, "must tell the caller how to fetch the rest"

    _seed_rubrics()
    with respx.mock:
        respx.get(f"{GAZETTE_BASE}/publications").mock(
            return_value=httpx.Response(200, json=MOCK_SEARCH_PAGE_2)
        )
        page1 = await gazette_search_publications(SearchInput(rubric="OB-BS", limit=2, page=1))
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
        await gazette_search_publications(SearchInput(rubric="OB-BS", limit=100))
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
    rubrics, subs, warnings = _procurement_scope("TI", False)
    assert rubrics == ["OB-TI"]
    assert warnings == []


def test_procurement_scope_without_canton_covers_active_rubrics_only():
    rubrics, _, _ = _procurement_scope(None, False)
    assert set(rubrics) == {"OB-AR", "OB-TI"}
    assert "OB-BL" not in rubrics
    # OB-ZG exists in the taxonomy but was never filled after the simap
    # switch — it is not an active procurement rubric.
    assert "OB-ZG" not in rubrics
    # OB-BS was phased out during 2024 (2 publications in 2026 YTD). Its rubric
    # label carries no inactive marker, unlike BL/VS/ZG — only the measured
    # volume reveals it, which is why `active` must never be read off the label.
    assert "OB-BS" not in rubrics


def test_procurement_scope_explains_a_phased_out_canton():
    rubrics, _, warnings = _procurement_scope("BS", False)
    assert rubrics == []
    assert warnings and "2024" in warnings[0]


def test_procurement_scope_include_inactive_adds_historical_rubrics():
    rubrics, _, _ = _procurement_scope(None, True)
    assert {"OB-BS", "OB-BL", "OB-VS"} <= set(rubrics)


# ---------------------------------------------------------------------------
# Gazette-native procurement sub-rubrics
# ---------------------------------------------------------------------------


def test_scope_without_canton_includes_the_native_sub_rubrics():
    """These are the only procurement records simap.ch does not also carry."""
    _rubrics, subs, _ = _procurement_scope(None, False)
    assert set(subs) == {"AR-VS40", "AR-OW40", "BA-SH40"}


def test_empty_sub_rubric_is_not_searched():
    """AR-NW40 holds 0 publications — green, but not worth a filter slot."""
    _rubrics, subs, _ = _procurement_scope(None, False)
    assert "AR-NW40" not in subs
    # Still green: emptiness is a coverage fact, not a data-protection one.
    assert is_green("AR-NW40")


def test_canton_without_an_ob_rubric_still_serves_its_sub_rubric():
    """Obwalden has no OB-OW, but AR-OW40 is live and simap-free."""
    rubrics, subs, warnings = _procurement_scope("OW", False)
    assert rubrics == []
    assert subs == ["AR-OW40"]
    assert warnings and "simap" in warnings[0]


def test_inactive_rubric_does_not_suppress_a_live_sub_rubric():
    """Valais: OB-VS is a dead simap import, AR-VS40 is live and native."""
    rubrics, subs, warnings = _procurement_scope("VS", False)
    assert rubrics == []
    assert subs == ["AR-VS40"]
    assert any("AR-VS40" in w for w in warnings)


@pytest.mark.asyncio
async def test_sub_rubric_search_never_sends_the_blocked_parent():
    """The invariant that makes releasing these sub-rubrics safe.

    AR-VS40's parent AR-VS is a collector rubric holding Arbeitsvergaben; if it
    were folded into `rubrics`, a procurement search would open a blocked
    rubric. They must travel as `subRubrics` only.
    """
    _seed_rubrics()
    with respx.mock:
        route = respx.get(f"{GAZETTE_BASE}/publications").mock(
            return_value=httpx.Response(200, json=MOCK_SEARCH)
        )
        await gazette_search_procurement(ProcurementInput(canton="VS"))

    params = route.calls[0].request.url.params
    assert set(params.get_list("subRubrics")) == {"AR-VS40"}
    assert params.get_list("rubrics") == [], "the blocked parent must never be sent"
    assert "AR-VS" not in str(route.calls[0].request.url).replace("AR-VS40", "")


@pytest.mark.asyncio
async def test_cantonless_search_sends_rubrics_and_sub_rubrics_together():
    _seed_rubrics()
    with respx.mock:
        route = respx.get(f"{GAZETTE_BASE}/publications").mock(
            return_value=httpx.Response(200, json=MOCK_SEARCH)
        )
        await gazette_search_procurement(ProcurementInput(keyword="Informatik"))

    params = route.calls[0].request.url.params
    assert set(params.get_list("rubrics")) == {"OB-AR", "OB-TI"}
    assert set(params.get_list("subRubrics")) == {"AR-VS40", "AR-OW40", "BA-SH40"}


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
        result = await gazette_search_procurement(ProcurementInput(canton="ZH"))

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
        result = await gazette_search_procurement(ProcurementInput(canton="BL"))
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
        await gazette_search_procurement(ProcurementInput(keyword="Informatik"))

    sent = set(route.calls[0].request.url.params.get_list("rubrics"))
    assert sent == {"OB-AR", "OB-TI"}


@pytest.mark.asyncio
async def test_procurement_warns_when_keyword_looks_like_a_cpv_code():
    _seed_rubrics()
    with respx.mock:
        respx.get(f"{GAZETTE_BASE}/publications").mock(
            return_value=httpx.Response(200, json=MOCK_SEARCH)
        )
        result = await gazette_search_procurement(ProcurementInput(keyword="72000000"))
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
        result = await gazette_search_publications(SearchInput(rubric="OB-BS"))

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
        result = await gazette_search_publications(SearchInput(rubric="OB-BS"))
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
        result = await gazette_search_publications(SearchInput(rubric="OB-BS"))
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
        result = await gazette_search_publications(SearchInput(rubric="OB-BS"))
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
        result = await gazette_search_publications(SearchInput(rubric="OB-BS"))
    assert "ignoriert" in result
    assert "nicht vertrauenswürdig" in result


# ---------------------------------------------------------------------------
# Live tests (excluded from CI with -m "not live")
# ---------------------------------------------------------------------------


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_procurement_basel_stadt():
    _reset_rubrics_cache()
    result = await gazette_search_procurement(ProcurementInput(canton="BS", limit=5))
    assert "amtsblattportal.ch" in result
    assert "Fehler" not in result


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_blocked_rubric_still_refuses():
    _reset_rubrics_cache()
    result = await gazette_search_publications(SearchInput(rubric="KK", keyword="Muster"))
    assert "fail-closed" in result
