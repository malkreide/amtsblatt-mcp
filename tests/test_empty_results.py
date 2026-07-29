"""ARCH-003: what an empty search says, and the promise that it never widens.

The check has four criteria. Three of them — a `match_type` on every response,
an actionable hint when it is `none`, and a documented decision for tools that
stay exact-only — apply straightforwardly here. The fourth asks for a fuzzy or
suggestion mechanism on the non-sensitive search tools, and this server has no
non-sensitive search tool: every one of them queries official gazette
publications about named legal and natural persons.

That makes `test_no_search_tool_widens_the_callers_term` the load-bearing test
in this file. A keyword search broadened from `Muster AG` to `Muster` returns
notices about *different* companies, and a model that cannot see the term was
changed under it will present them as the answer. The failure mode is naming
the wrong company as bankrupt. If any test here is ever dropped, it is not
that one.

The rest of the file guards the thing that replaces widening: an empty result
that explains itself. That matters more here than a fuzzy match would, because
this server searches only the green rubrics — so a keyword that genuinely
appears in the gazette can come back empty purely because its rubric is
deliberately not served, and an empty result that does not say so reads as "no
such publication exists".
"""

from __future__ import annotations

import json
import typing
from time import monotonic

import httpx
import pytest
import respx

from amtsblatt_mcp import server
from amtsblatt_mcp._matching import MatchType, describe_filters
from amtsblatt_mcp.server import (
    GAZETTE_BASE,
    DetailedSearchInput,
    ProcurementInput,
    ResponseFormat,
    SearchInput,
    _reset_rubrics_cache,
    gazette_search_detailed,
    gazette_search_procurement,
    gazette_search_publications,
)

from .fixtures import MOCK_RUBRICS, MOCK_SEARCH, MOCK_SEARCH_EMPTY

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _clear_caches():
    _reset_rubrics_cache()
    yield
    _reset_rubrics_cache()


def _seed_rubrics() -> None:
    server._rubrics_cache = (monotonic(), MOCK_RUBRICS)


def _empty_route() -> respx.Route:
    return respx.get(f"{GAZETTE_BASE}/publications").mock(
        return_value=httpx.Response(200, json=MOCK_SEARCH_EMPTY)
    )


# --- the exact-only decision ----------------------------------------------


async def test_no_search_tool_widens_the_callers_term() -> None:
    """Criterion 4, and the reason this server has no fuzzy matching at all.

    Asserted on the outgoing request rather than on the rendered text, because
    that is what a widening implementation would change: one request, carrying
    the caller's keyword unmodified, even though it returned nothing.
    """
    _seed_rubrics()
    with respx.mock:
        route = _empty_route()
        await gazette_search_publications(SearchInput(keyword="Muster AG", rubric="OB-BS"))

    assert route.call_count == 1, "an empty result must not trigger a second, broader search"
    assert route.calls[0].request.url.params.get("keyword") == "Muster AG"


async def test_the_match_type_has_no_fuzzy_member() -> None:
    """The exact-only decision, pinned in the type rather than only in prose.

    Adding widening means adding the member, which means coming to `_matching`
    and reading why it is absent. A comment alone would not survive that.
    """
    assert set(typing.get_args(MatchType)) == {"exact", "none"}


# --- an empty result explains itself ---------------------------------------


async def test_an_empty_result_names_the_filters_that_produced_it() -> None:
    """Otherwise the obvious retry is the identical search in a different shape."""
    _seed_rubrics()
    with respx.mock:
        _empty_route()
        out = await gazette_search_publications(
            SearchInput(keyword="Zzzunfindbar", rubric="OB-BS", date_start="2026-01-01")
        )

    assert "Zzzunfindbar" in out
    assert "OB-BS" in out
    assert "2026-01-01" in out


async def test_an_empty_result_points_at_the_scope_gate() -> None:
    """The distinction only this server can draw, and the one that misleads.

    "No hits" and "that rubric is deliberately not served" are different
    claims, and nothing outside this process can tell them apart.
    """
    _seed_rubrics()
    with respx.mock:
        _empty_route()
        out = await gazette_search_publications(SearchInput(keyword="Zzzunfindbar"))

    assert "gazette_list_rubrics" in out
    assert "rubric_class='all'" in out


async def test_an_empty_result_points_at_source_status() -> None:
    """A degraded upstream and an empty result are indistinguishable here."""
    _seed_rubrics()
    with respx.mock:
        _empty_route()
        out = await gazette_search_publications(SearchInput(keyword="Zzzunfindbar"))

    assert "gazette_source_status" in out


async def test_an_empty_result_says_it_did_not_widen() -> None:
    """Without this the absence of fuzzy matching reads as a missing feature.

    Which is how it gets "fixed" by the next person to touch the search path.
    """
    _seed_rubrics()
    with respx.mock:
        _empty_route()
        out = await gazette_search_publications(SearchInput(keyword="Zzzunfindbar"))

    assert "nicht** automatisch erweitert" in out


@pytest.mark.parametrize(
    ("tool", "payload"),
    [
        (gazette_search_publications, SearchInput(keyword="Zzzunfindbar")),
        (gazette_search_detailed, DetailedSearchInput(keyword="Zzzunfindbar")),
        (gazette_search_procurement, ProcurementInput(keyword="Zzzunfindbar", canton="TI")),
    ],
)
async def test_every_search_tool_explains_an_empty_result(tool, payload) -> None:
    """The rendering is shared, so this is really a test that nobody bypassed it.

    A fourth search tool added with its own empty branch is exactly the
    regression worth catching, and `_render_results` takes the note without a
    default so that omission is a TypeError rather than a weaker message.
    """
    _seed_rubrics()
    with respx.mock:
        _empty_route()
        out = await tool(payload)

    assert "gazette_source_status" in out
    assert "Treffertyp: `none`" in out


# --- match_type reaches the caller -----------------------------------------


async def test_the_markdown_output_carries_the_match_type() -> None:
    """These tools return Markdown, so anything not in the text does not exist."""
    _seed_rubrics()
    with respx.mock:
        respx.get(f"{GAZETTE_BASE}/publications").mock(
            return_value=httpx.Response(200, json=MOCK_SEARCH)
        )
        hit = await gazette_search_publications(SearchInput(rubric="OB-BS"))

    assert "Treffertyp: `exact`" in hit


async def test_a_hit_is_labelled_exact_and_carries_no_note() -> None:
    """The negative control. Without it every result could carry the empty hint."""
    _seed_rubrics()
    with respx.mock:
        respx.get(f"{GAZETTE_BASE}/publications").mock(
            return_value=httpx.Response(200, json=MOCK_SEARCH)
        )
        out = await gazette_search_publications(
            SearchInput(rubric="OB-BS", response_format=ResponseFormat.JSON)
        )

    payload = json.loads(out)
    assert payload["match_type"] == "exact"
    assert payload["note"] is None
    assert payload["count"] > 0


async def test_the_json_output_carries_match_type_and_note() -> None:
    """JSON callers get the same two facts as Markdown callers, not fewer."""
    _seed_rubrics()
    with respx.mock:
        _empty_route()
        out = await gazette_search_publications(
            SearchInput(keyword="Zzzunfindbar", response_format=ResponseFormat.JSON)
        )

    payload = json.loads(out)
    assert payload["match_type"] == "none"
    assert payload["note"] and "gazette_list_rubrics" in payload["note"]


# --- the filter description ------------------------------------------------


async def test_unset_filters_are_not_described_as_set() -> None:
    """Listing `Kanton: «None»` back at a caller is worse than saying nothing."""
    assert describe_filters(keyword="Bau", canton=None, rubric=None) == "Stichwort: «Bau»"
    assert "None" not in describe_filters(keyword=None, canton=None)
