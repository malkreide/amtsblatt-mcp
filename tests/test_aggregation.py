"""ARCH-007: the aggregated `gazette_search_detailed` tool.

The 2026-07-27 re-audit graded ARCH-007 `partial`: every tool returned pointers,
so "find notices and show me what they say" cost 1 + N calls and the model had
to do the chaining itself. `asyncio.gather` appeared nowhere in `src/`.

The load-bearing tests here are the green-gate ones. Aggregation adds a *second*
path to publication content, and a data-protection control that holds in one
path but not the other is worse than none — it looks enforced. So the gate is
asserted on the aggregated path directly, not inferred from the fact that both
call the same helper.
"""

from __future__ import annotations

import json
from time import monotonic

import httpx
import pytest
import respx
from pydantic import ValidationError

from amtsblatt_mcp import server
from amtsblatt_mcp.server import (
    GAZETTE_BASE,
    GAZETTE_MAX_DETAIL_N,
    DetailedSearchInput,
    _reset_rubrics_cache,
    gazette_search_detailed,
)

from .fixtures import (
    MOCK_RUBRICS,
    MOCK_SEARCH,
    MOCK_SEARCH_EMPTY,
    MOCK_XML_BLOCKED_RUBRIC,
    MOCK_XML_PROCUREMENT,
)

PUB_A = "fbf0ff9e-3e28-4e09-8a1e-32a7aa4cea8f"
PUB_B = "aa11bb22-3e28-4e09-8a1e-32a7aa4cea01"


@pytest.fixture(autouse=True)
def _clear_caches():
    _reset_rubrics_cache()
    yield
    _reset_rubrics_cache()


def _seed_rubrics():
    server._rubrics_cache = (monotonic(), MOCK_RUBRICS)


def _mock_search_and_xml(xml_by_id: dict[str, str]):
    """Mock the search endpoint plus one XML endpoint per publication id."""
    respx.get(f"{GAZETTE_BASE}/publications").mock(
        return_value=httpx.Response(200, json=MOCK_SEARCH)
    )
    routes = {}
    for pub_id, xml in xml_by_id.items():
        routes[pub_id] = respx.get(f"{GAZETTE_BASE}/publications/{pub_id}/xml").mock(
            return_value=httpx.Response(200, text=xml)
        )
    return routes


# --- aggregation ----------------------------------------------------------


@pytest.mark.asyncio
async def test_one_call_returns_list_and_full_text():
    """The whole point: no second round trip for the content.

    The body assertion below is deliberately a phrase that appears ONLY in the
    publication XML, never in the search summary. An earlier version of this
    test asserted a title instead — which comes from the result list — and so
    passed while the tool was rendering "Kein Volltext im XML" for every hit.
    """
    _seed_rubrics()
    with respx.mock:
        _mock_search_and_xml({PUB_A: MOCK_XML_PROCUREMENT, PUB_B: MOCK_XML_PROCUREMENT})
        result = await gazette_search_detailed(
            DetailedSearchInput(rubric="OB-BS", top_n=2)
        )

    assert "Trambeschaffung" in result  # from the result list
    assert "Vergabeverfahren gemäss Art. 43" in result  # only in the XML body
    assert "Kein Volltext im XML" not in result
    assert "Volltext: 2 von 2 angefordert" in result


@pytest.mark.asyncio
async def test_expands_exactly_top_n_hits():
    _seed_rubrics()
    with respx.mock:
        routes = _mock_search_and_xml(
            {PUB_A: MOCK_XML_PROCUREMENT, PUB_B: MOCK_XML_PROCUREMENT}
        )
        await gazette_search_detailed(DetailedSearchInput(rubric="OB-BS", top_n=1))

    assert routes[PUB_A].called, "the top hit was not expanded"
    assert not routes[PUB_B].called, "expanded more than top_n"


@pytest.mark.asyncio
async def test_detail_fetches_run_concurrently():
    """Sequential fetching would defeat the purpose of the aggregation.

    Asserted through the client rather than by timing: both XML requests must
    have been issued, and `asyncio.gather` is what issues them together.
    """
    _seed_rubrics()
    with respx.mock:
        routes = _mock_search_and_xml(
            {PUB_A: MOCK_XML_PROCUREMENT, PUB_B: MOCK_XML_PROCUREMENT}
        )
        await gazette_search_detailed(DetailedSearchInput(rubric="OB-BS", top_n=2))

    assert routes[PUB_A].called and routes[PUB_B].called


@pytest.mark.asyncio
async def test_empty_result_set_makes_no_detail_calls():
    _seed_rubrics()
    with respx.mock:
        respx.get(f"{GAZETTE_BASE}/publications").mock(
            return_value=httpx.Response(200, json=MOCK_SEARCH_EMPTY)
        )
        xml = respx.get(url__regex=rf"{GAZETTE_BASE}/publications/.*/xml").mock(
            return_value=httpx.Response(200, text=MOCK_XML_PROCUREMENT)
        )
        result = await gazette_search_detailed(DetailedSearchInput(rubric="OB-BS"))

    assert not xml.called
    assert "Volltext: 0 von 0 angefordert" in result


# --- the green gate on the aggregated path --------------------------------


@pytest.mark.asyncio
async def test_blocked_rubric_content_is_never_rendered():
    """A publication that turns out to be from a blocked rubric is discarded.

    This is the invariant the whole server rests on. The aggregated path must
    enforce it exactly as `gazette_get_publication` does.
    """
    _seed_rubrics()
    with respx.mock:
        _mock_search_and_xml(
            {PUB_A: MOCK_XML_BLOCKED_RUBRIC, PUB_B: MOCK_XML_PROCUREMENT}
        )
        result = await gazette_search_detailed(
            DetailedSearchInput(rubric="OB-BS", top_n=2)
        )

    # The person data from the blocked document must not appear anywhere.
    assert "Erika Mustermann" not in result
    assert "Konkurseröffnung" not in result
    assert "Musterstrasse" not in result
    # ...and its withholding is stated rather than silent.
    assert "gesperrten Rubrik" in result
    assert "Volltext: 1 von 2 angefordert" in result


@pytest.mark.asyncio
async def test_sole_hit_from_a_blocked_rubric_yields_no_body_at_all():
    """With the only expandable hit blocked, nothing of it may survive."""
    _seed_rubrics()
    with respx.mock:
        _mock_search_and_xml({PUB_A: MOCK_XML_BLOCKED_RUBRIC})
        result = await gazette_search_detailed(
            DetailedSearchInput(rubric="OB-BS", top_n=1)
        )

    assert "Erika Mustermann" not in result
    assert "Konkurseröffnung" not in result
    assert "Volltext: 0 von 1 angefordert" in result
    assert "gesperrten Rubrik" in result


@pytest.mark.asyncio
async def test_blocked_rubric_filter_is_refused_before_any_call():
    """Same fail-closed behaviour as the plain search: no network call at all."""
    with respx.mock:
        search = respx.get(f"{GAZETTE_BASE}/publications").mock(
            return_value=httpx.Response(200, json=MOCK_SEARCH)
        )
        result = await gazette_search_detailed(DetailedSearchInput(rubric="KK"))

    assert not search.called
    assert "KK" in result


@pytest.mark.asyncio
async def test_json_output_lists_withheld_ids_separately():
    _seed_rubrics()
    with respx.mock:
        _mock_search_and_xml(
            {PUB_A: MOCK_XML_BLOCKED_RUBRIC, PUB_B: MOCK_XML_PROCUREMENT}
        )
        raw = await gazette_search_detailed(
            DetailedSearchInput(rubric="OB-BS", top_n=2, response_format="json")
        )

    payload = json.loads(raw)
    assert payload["scope"] == "green_rubrics_only"
    assert PUB_A in payload["withheld_ids"]
    assert [d["id"] for d in payload["expanded"]] == [PUB_B]
    assert "Erika Mustermann" not in raw


# --- bounds and degradation -----------------------------------------------


@pytest.mark.asyncio
async def test_top_n_is_bounded():
    """Fan-out is capped so one call cannot become an unbounded burst."""
    with pytest.raises(ValidationError):
        DetailedSearchInput(rubric="OB-BS", top_n=0)
    with pytest.raises(ValidationError):
        DetailedSearchInput(rubric="OB-BS", top_n=GAZETTE_MAX_DETAIL_N + 1)


@pytest.mark.asyncio
async def test_one_failing_detail_does_not_sink_the_whole_call():
    """A partial answer beats no answer — the list still comes back."""
    _seed_rubrics()
    with respx.mock:
        respx.get(f"{GAZETTE_BASE}/publications").mock(
            return_value=httpx.Response(200, json=MOCK_SEARCH)
        )
        respx.get(f"{GAZETTE_BASE}/publications/{PUB_A}/xml").mock(
            return_value=httpx.Response(500, text="boom")
        )
        respx.get(f"{GAZETTE_BASE}/publications/{PUB_B}/xml").mock(
            return_value=httpx.Response(200, text=MOCK_XML_PROCUREMENT)
        )
        result = await gazette_search_detailed(
            DetailedSearchInput(rubric="OB-BS", top_n=2)
        )

    assert "Trambeschaffung" in result  # the list survived
    assert "Volltext: 1 von 2 angefordert" in result


@pytest.mark.asyncio
async def test_inherits_the_search_filter_surface():
    """Same query dialect as the plain search — not a second one to learn."""
    _seed_rubrics()
    with respx.mock:
        route = respx.get(f"{GAZETTE_BASE}/publications").mock(
            return_value=httpx.Response(200, json=MOCK_SEARCH_EMPTY)
        )
        await gazette_search_detailed(
            DetailedSearchInput(
                rubric="OB-BS", canton="BS", date_start="2026-07-01", limit=5
            )
        )

    params = route.calls[0].request.url.params
    assert params.get("rubrics") == "OB-BS"
    assert params.get("cantons") == "BS"
    assert params.get("publicationDate.start") == "2026-07-01"


@pytest.mark.asyncio
async def test_keyword_only_query_still_injects_the_green_set():
    """Fail-closed: without a rubric the full green list is injected."""
    _seed_rubrics()
    with respx.mock:
        route = respx.get(f"{GAZETTE_BASE}/publications").mock(
            return_value=httpx.Response(200, json=MOCK_SEARCH_EMPTY)
        )
        await gazette_search_detailed(DetailedSearchInput(keyword="Informatik"))

    rubrics = route.calls[0].request.url.params.get("rubrics")
    assert rubrics, "no rubric filter injected — a keyword query went corpus-wide"
