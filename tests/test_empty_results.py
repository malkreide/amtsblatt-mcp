"""ARCH-003: an empty search suggests terms, and never searches for them.

**This file's premise was wrong once, and the correction is the point.** It used
to state that every search here queries "publications about named legal and
natural persons" — bankruptcies, debt collection, estate calls, building
applications — and that criterion 1 therefore did not apply. Every one of those
rubrics is **red** and unreachable: `KK`, `SB`, `SR`, `LS`, `NA`, `ES`, `TE-*`,
`GB-*`, `GE-*`, `BP-*` all sit outside `GREEN_RUBRICS`, which exists precisely to
exclude systematic natural-person data. The searchable set is the *non-sensitive*
one, so criterion 1 applied all along and the 2026-07-30 re-audit recorded
`ARCH-003` as still `partial`.

What survives from that reasoning is narrower and real: `HR` / `BH`
(Handelsregister) and `OB-*` (Beschaffungen) name legal persons, so silently
re-running a search with a broadened company name would return notices about
*different* companies and present them as the answer.

Both halves are now held at once. `suggest_terms` offers shorter forms of the
caller's own keyword and the server never queries them, so criterion 1 is met
while no result can be attributed to a term the caller did not choose. The two
load-bearing tests are therefore a pair:
`test_an_empty_result_suggests_shorter_terms` (the criterion) and
`test_suggestions_are_never_searched` (the safety property). Dropping either one
leaves the other meaningless.
"""

from __future__ import annotations

import json
import typing
from time import monotonic

import httpx
import pytest
import respx

from amtsblatt_mcp import _taxonomy
from amtsblatt_mcp._matching import (
    MIN_TERM_LENGTH,
    MatchType,
    describe_filters,
    suggest_terms,
    suggestion_sentence,
)
from amtsblatt_mcp._taxonomy import _reset_rubrics_cache
from amtsblatt_mcp.constants import GAZETTE_BASE, ResponseFormat
from amtsblatt_mcp.inputs import DetailedSearchInput, ProcurementInput, SearchInput
from amtsblatt_mcp.server import (
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
    _taxonomy._rubrics_cache = (monotonic(), MOCK_RUBRICS)


def _empty_route() -> respx.Route:
    return respx.get(f"{GAZETTE_BASE}/publications").mock(
        return_value=httpx.Response(200, json=MOCK_SEARCH_EMPTY)
    )


# --- the exact-only decision ----------------------------------------------


async def test_no_search_tool_widens_the_callers_term() -> None:
    """The server offers terms; it never queries them itself.

    Kept alongside `test_suggestions_are_never_searched` rather than merged into
    it, because the two guard different things. That one asserts a *suggestion* is
    not executed; this one asserts the search path does not widen at all, which is
    what a well-meaning "just retry with a shorter term" patch would break.

    Asserted on the outgoing request rather than the rendered text, because that
    is what such a patch would change: one request, carrying the caller's keyword
    unmodified, even though it returned nothing.
    """
    _seed_rubrics()
    with respx.mock:
        route = _empty_route()
        await gazette_search_publications(SearchInput(keyword="Muster AG", rubric="OB-BS"))

    assert route.call_count == 1, "an empty result must not trigger a second, broader search"
    assert route.calls[0].request.url.params.get("keyword") == "Muster AG"


async def test_the_match_type_has_no_fuzzy_member() -> None:
    """Still no `fuzzy`, and now for the right reason.

    The server never *performs* a widened search, so no response is ever a fuzzy
    match — suggestions ride in the note as candidate terms. Adding the member
    means switching from offering to executing, which means coming to `_matching`
    and reading that difference.
    """
    assert set(typing.get_args(MatchType)) == {"exact", "none"}


# --- criterion 1: suggestions, offered and never executed -------------------


async def test_an_empty_result_suggests_shorter_terms() -> None:
    """ARCH-003 criterion 1 — the half that was missing until 0.22.0.

    A caller whose compound is one segment too long gets a route to the right
    term instead of a dead end, which is the case the check was written for.
    """
    _seed_rubrics()
    with respx.mock:
        _empty_route()
        out = await gazette_search_publications(SearchInput(keyword="Schulhausneubau"))

    assert "Schulhaus" in out, "no shorter form of the caller's own term offered"
    assert "Schul" in out


async def test_suggestions_are_never_searched() -> None:
    """The safety property, and the reason suggesting is not widening.

    If the server queried its own suggestions it would be doing exactly what
    0.20.0 refused: returning notices about a different company under the
    caller's original question. Asserted on the request count and the outgoing
    keyword, because that is what executing a suggestion would change.
    """
    _seed_rubrics()
    with respx.mock:
        route = _empty_route()
        out = await gazette_search_publications(SearchInput(keyword="Muster AG", rubric="OB-BS"))

    assert route.call_count == 1, "a suggestion must be offered, never queried"
    assert route.calls[0].request.url.params.get("keyword") == "Muster AG"
    assert "Muster" in out, "the suggestion itself should still reach the caller"


async def test_suggestions_say_they_were_not_queried() -> None:
    """Otherwise a model reads the terms as searches that already happened.

    Which would turn a suggestion into a false claim about what was tried.
    """
    _seed_rubrics()
    with respx.mock:
        _empty_route()
        out = await gazette_search_publications(SearchInput(keyword="Schulhausneubau"))

    assert "nicht** automatisch abgefragt" in out


async def test_a_short_keyword_gets_no_suggestions() -> None:
    """Below the floor a prefix matches half the gazette.

    A suggestions clause that is always present trains the reader to skip it, so
    an empty one is omitted rather than padded.
    """
    assert suggest_terms("Bau") == []
    assert suggest_terms("") == []
    assert suggestion_sentence("Bau") == ""

    # The multi-word path needs its own assertion: the prefix schedule already
    # floors at MIN_TERM_LENGTH, so the length guard in `_add` is only reachable
    # via short *tokens*. Without this line, removing that guard survived every
    # test in this file while suggesting "AG" — a legal-form abbreviation — as a
    # search term across the whole gazette.
    assert "AG" not in suggest_terms("Muster AG")
    assert all(len(t) >= MIN_TERM_LENGTH for t in suggest_terms("Bau GmbH Zürich"))


async def test_suggestions_are_only_prefixes_of_the_callers_term() -> None:
    """No stemmer, no dictionary — those invent a term the caller never used.

    The multi-word case picks the longest token first: "mobile Metallbauten" is
    asking about Metallbauten, not about mobility.
    """
    for term in suggest_terms("Schulhausneubau"):
        assert "Schulhausneubau".lower().startswith(term.lower())
    assert suggest_terms("mobile Metallbauten")[0] == "Metallbauten"


async def test_the_broadest_suggestion_comes_last() -> None:
    """A fixed per-step ratio was measured wrong on the companion server.

    From "Betonsanierungsarbeiten" it stopped at seven characters, three short of
    the term that actually returns results. If the last suggestion is not the
    widest, the last resort is not a last resort.
    """
    terms = suggest_terms("Betonsanierungsarbeiten")
    assert len(terms[-1]) <= MIN_TERM_LENGTH + 1


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
