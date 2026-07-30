"""The fail-closed green allow-list — the data-protection core of this server.

These are the tests that must never be relaxed. Every one of them asserts that
a blocked rubric produces an explanation and NO network call, rather than a
silent empty result.
"""

from __future__ import annotations

from time import monotonic

import httpx
import pytest
import respx

from amtsblatt_mcp import _taxonomy, inputs
from amtsblatt_mcp._http import _assert_green_params, _search
from amtsblatt_mcp._taxonomy import _reset_rubrics_cache
from amtsblatt_mcp.constants import (
    ALLOWED_GAZETTE_PARAMS,
    FORBIDDEN_GAZETTE_PARAMS,
    GAZETTE_BASE,
    RubricBlocked,
)
from amtsblatt_mcp.inputs import PublicationInput, RubricsInput, SearchInput
from amtsblatt_mcp.rubrics import (
    GREEN_RUBRICS,
    GREEN_SUB_RUBRICS,
    RED_RUBRICS,
    YELLOW_RUBRICS,
    classify,
    explain_blocked,
    is_green,
)
from amtsblatt_mcp.server import (
    gazette_get_publication,
    gazette_list_rubrics,
    gazette_search_publications,
)

from .fixtures import MOCK_RUBRICS, MOCK_SEARCH, MOCK_XML_BLOCKED_RUBRIC


@pytest.fixture(autouse=True)
def _clear_caches():
    _reset_rubrics_cache()
    yield
    _reset_rubrics_cache()


def _seed_rubrics():
    """Populate the taxonomy cache so validation makes no HTTP call."""
    _taxonomy._rubrics_cache = (monotonic(), MOCK_RUBRICS)


# ---------------------------------------------------------------------------
# Structural properties of the allow-list itself
# ---------------------------------------------------------------------------


def test_green_and_red_sets_are_disjoint():
    """A code must never be both released and documented as blocked."""
    assert not (GREEN_RUBRICS & set(RED_RUBRICS))
    assert not (GREEN_RUBRICS & set(YELLOW_RUBRICS))
    assert not (GREEN_SUB_RUBRICS & set(RED_RUBRICS))


def test_green_set_is_literal_codes_not_globs():
    """The green set must contain no wildcards.

    The source proposal's table uses glob notation for readability, but a glob
    in code would auto-green any future upstream rubric matching the prefix —
    exactly what the fail-closed rule forbids.
    """
    for code in GREEN_RUBRICS | GREEN_SUB_RUBRICS:
        assert "*" not in code, f"{code} is a glob, not a literal rubric code"
        assert not code.endswith("-"), f"{code} looks like a prefix, not a code"


def test_every_live_rubric_is_explicitly_classified():
    """No live rubric may rely on the implicit default.

    Fail-closed already blocks an unclassified rubric, but it does so
    *silently* — the user gets a generic message instead of a reason. The
    taxonomy snapshot of 2026-07-20 has 152 top-level rubrics, and all of them
    carry an explicit classification. When the upstream adds a rubric this
    count drifts: the new code stays blocked (correct), and this test is the
    reminder to classify it deliberately.
    """
    classified = set(GREEN_RUBRICS) | set(RED_RUBRICS) | set(YELLOW_RUBRICS)
    assert len(classified) == 152, (
        f"{len(classified)} rubrics classified, expected 152 — "
        "re-run the taxonomy diff and classify any new codes"
    )


def test_unknown_rubric_defaults_to_blocked():
    """A rubric nobody has classified is closed, not open."""
    assert classify("ZZ-NEW") == "unclassified"
    assert is_green("ZZ-NEW") is False


def test_red_rubrics_are_blocked():
    for code in ("KK", "SB", "NA", "ES", "BP-ZH", "TE-ZH", "AA-GR", "GR-BS", "BU-NW"):
        assert is_green(code) is False, f"{code} must not be queryable"
        assert classify(code) == "red"


def test_known_green_rubrics_are_released():
    for code in ("HR", "BH", "OB-BS", "OB-TI", "KA-ZH", "KO-ZH", "PL-BL", "RP-ZH"):
        assert is_green(code) is True, f"{code} should be queryable"


def test_green_sub_rubrics_have_blocked_parents():
    """The non-simap procurement sub-rubrics sit under parents that stay closed."""
    for sub, parent in (
        ("AR-NW40", "AR-NW"),
        ("AR-OW40", "AR-OW"),
        ("AR-VS40", "AR-VS"),
        ("BA-SH40", "BA-SH"),
    ):
        assert is_green(sub) is True
        assert is_green(parent) is False, f"parent {parent} must stay blocked"


def test_person_parameters_are_not_allow_listed():
    """Fail-closed: person-profiling params can never reach the query string."""
    for param in FORBIDDEN_GAZETTE_PARAMS:
        assert param not in ALLOWED_GAZETTE_PARAMS
    # No name / birthdate / address entry point exists at all.
    for param in ("name", "birthDate", "address", "personName", "surname"):
        assert param not in ALLOWED_GAZETTE_PARAMS


def test_no_tool_exposes_a_person_search_field():
    """No input model may offer a name-like parameter."""
    for model in (inputs.SearchInput, inputs.ProcurementInput):
        for field in model.model_fields:
            assert field not in ("name", "person", "surname", "birth_date", "address")


def test_explain_blocked_names_the_reason_and_offers_no_workaround():
    msg = explain_blocked("KK")
    assert "KK" in msg
    assert "natürliche Personen" in msg
    assert "fail-closed" in msg
    # Points at the legitimate alternative (UID join), not a circumvention.
    assert "register-mcp" in msg
    for forbidden_hint in ("keyword=", "trotzdem", "umgehen", "workaround"):
        assert forbidden_hint not in msg.lower()


def test_explain_blocked_distinguishes_red_from_yellow_from_unknown():
    assert "bewusst nicht erschlossen" in explain_blocked("KK")
    assert "noch nicht freigegeben" in explain_blocked("SW-ZH")
    assert "nicht auf der Freigabe-Liste" in explain_blocked("ZZ-NEW")


# ---------------------------------------------------------------------------
# The structural gate: _assert_green_params
# ---------------------------------------------------------------------------


def test_green_gate_rejects_blocked_rubric_in_params():
    with pytest.raises(RubricBlocked):
        _assert_green_params({"rubrics": "KK"})


def test_green_gate_rejects_a_blocked_rubric_hidden_in_a_list():
    """One bad code among green ones still fails the whole request."""
    with pytest.raises(RubricBlocked):
        _assert_green_params({"rubrics": ["HR", "OB-BS", "KK"]})


def test_green_gate_allows_green_codes():
    _assert_green_params({"rubrics": ["HR", "OB-BS"], "subRubrics": "AR-NW40"})


@pytest.mark.asyncio
async def test_search_helper_cannot_be_tricked_into_a_blocked_rubric():
    """Even a direct call to the low-level helper is gated — defence in depth."""
    with respx.mock:
        route = respx.get(f"{GAZETTE_BASE}/publications").mock(
            return_value=httpx.Response(200, json=MOCK_SEARCH)
        )
        with pytest.raises(RubricBlocked):
            await _search({"rubrics": "SB"})
    assert route.call_count == 0, "a blocked rubric must never reach the network"


# ---------------------------------------------------------------------------
# THE key test: blocked rubric → explanation, no data, no call
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("blocked", ["KK", "SB", "NA", "ES", "BP-ZH", "AA-GR"])
async def test_blocked_rubric_returns_explanation_and_makes_no_call(blocked):
    _seed_rubrics()
    with respx.mock:
        route = respx.get(f"{GAZETTE_BASE}/publications").mock(
            return_value=httpx.Response(200, json=MOCK_SEARCH)
        )
        result = await gazette_search_publications(SearchInput(rubric=blocked, keyword="Muster"))

    # No data reached the user...
    assert route.call_count == 0
    assert "Trebold" not in result
    # ...and the message explains the scope decision.
    assert blocked in result
    assert "fail-closed" in result
    assert "Keine Treffer" not in result, "must not masquerade as an empty result"


@pytest.mark.asyncio
async def test_blocked_sub_rubric_is_also_refused():
    _seed_rubrics()
    with respx.mock:
        route = respx.get(f"{GAZETTE_BASE}/publications").mock(
            return_value=httpx.Response(200, json=MOCK_SEARCH)
        )
        result = await gazette_search_publications(SearchInput(sub_rubric="KK01"))
    assert route.call_count == 0
    assert "KK01" in result
    assert "Freigabe-Liste" in result or "nicht erschlossen" in result


@pytest.mark.asyncio
async def test_keyword_only_search_injects_green_rubrics_and_cannot_reach_red():
    """A keyword-only query must be scoped to the green set, not the corpus."""
    _seed_rubrics()
    with respx.mock:
        route = respx.get(f"{GAZETTE_BASE}/publications").mock(
            return_value=httpx.Response(200, json=MOCK_SEARCH)
        )
        await gazette_search_publications(SearchInput(keyword="Informatik"))

    sent = route.calls[0].request.url.params.get_list("rubrics")
    assert sent, "no rubric filter was sent — the query would hit the whole corpus"
    assert set(sent) == set(GREEN_RUBRICS)
    for red in RED_RUBRICS:
        assert red not in sent


@pytest.mark.asyncio
async def test_green_sub_rubric_search_does_not_inject_its_blocked_parent():
    """AR-NW40 is green; its parent AR-NW is not. The parent must not leak in."""
    _seed_rubrics()
    with respx.mock:
        route = respx.get(f"{GAZETTE_BASE}/publications").mock(
            return_value=httpx.Response(200, json=MOCK_SEARCH)
        )
        await gazette_search_publications(SearchInput(sub_rubric="AR-NW40"))

    params = route.calls[0].request.url.params
    assert params.get("subRubrics") == "AR-NW40"
    assert "AR-NW" not in params.get_list("rubrics")


@pytest.mark.asyncio
async def test_get_publication_refuses_content_from_a_blocked_rubric():
    """An opaque ID pointing into a blocked rubric is caught after the fetch."""
    pub_id = "abc12345-0000-0000-0000-000000000001"
    with respx.mock:
        respx.get(f"{GAZETTE_BASE}/publications/{pub_id}/xml").mock(
            return_value=httpx.Response(200, text=MOCK_XML_BLOCKED_RUBRIC)
        )
        result = await gazette_get_publication(PublicationInput(id=pub_id))

    # The body text was fetched but must NOT be rendered.
    assert "Konkurseröffnung über" not in result
    assert "Mustermann" not in result
    assert "KK" in result
    assert "bewusst nicht erschlossen" in result


# ---------------------------------------------------------------------------
# Taxonomy browser
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_rubrics_green_default_hides_blocked_rubrics():
    with respx.mock:
        respx.get(f"{GAZETTE_BASE}/rubrics").mock(
            return_value=httpx.Response(200, json=MOCK_RUBRICS)
        )
        result = await gazette_list_rubrics(RubricsInput())
    assert "HR" in result
    assert "OB-BS" in result
    assert "🔴" not in result
    assert "Konkurse" not in result


@pytest.mark.asyncio
async def test_list_rubrics_all_shows_blocked_with_reason_but_marks_them_closed():
    with respx.mock:
        respx.get(f"{GAZETTE_BASE}/rubrics").mock(
            return_value=httpx.Response(200, json=MOCK_RUBRICS)
        )
        result = await gazette_list_rubrics(RubricsInput(rubric_class="all"))
    assert "🔴" in result
    assert "KK" in result
    assert "Nicht durchsuchbar" in result


@pytest.mark.asyncio
async def test_invalid_code_suggestions_never_name_a_blocked_rubric():
    """A 'did you mean' must not advertise a rubric the user may not query."""
    _seed_rubrics()
    with respx.mock:
        respx.get(f"{GAZETTE_BASE}/publications").mock(
            return_value=httpx.Response(200, json=MOCK_SEARCH)
        )
        # `HRX` is green-ish looking but invalid — it passes the green gate only
        # if listed, so use a green-but-nonexistent code to reach validation.
        server_result = await gazette_search_publications(SearchInput(rubric="HR"))
    assert "Fehler" not in server_result  # sanity: HR is valid and green

    from amtsblatt_mcp._taxonomy import _validate_rubric_code
    from amtsblatt_mcp.constants import GazetteInvalidCode

    with pytest.raises(GazetteInvalidCode) as exc:
        await _validate_rubric_code("HRXX", "rubric")
    message = str(exc.value)
    for red in ("KK", "SB", "NA", "ES"):
        assert f" {red}," not in message and not message.endswith(f" {red}.")


# ---------------------------------------------------------------------------
# OPS-001: gazette_list_rubrics was at 2 unit tests against a floor of 5
# ---------------------------------------------------------------------------


class TestListRubricsCoverage:
    """The taxonomy tool is the one a caller reaches for *first*.

    It was the least-tested tool in the server, which is the wrong way round:
    a wrong answer here sends every subsequent query to the wrong rubric.

    Note the listing is built from the *upstream* rubric list intersected with
    the green set — it is not a static table. Two of these tests exist because
    that surprised the author: an empty upstream response yields an empty
    listing, and an unreachable upstream yields an error rather than a
    fallback.
    """

    @pytest.mark.asyncio
    async def test_green_listing_names_no_blocked_rubric(self):
        """Naming a red rubric here would tell a caller exactly what to try
        next, which is the opposite of what the allow-list is for."""
        _reset_rubrics_cache()
        with respx.mock:
            respx.get(f"{GAZETTE_BASE}/rubrics").mock(
                return_value=httpx.Response(200, json=MOCK_RUBRICS)
            )
            result = await gazette_list_rubrics(RubricsInput())
        for red in sorted(RED_RUBRICS):
            assert f"`{red}`" not in result, f"blocked rubric {red} named in the green listing"

    @pytest.mark.asyncio
    async def test_empty_upstream_yields_an_empty_listing_not_a_stale_one(self):
        """The listing mirrors the upstream taxonomy. If the upstream returns
        nothing, saying so is correct — inventing the green set from the static
        table would claim rubrics the source no longer publishes."""
        _reset_rubrics_cache()
        with respx.mock:
            respx.get(f"{GAZETTE_BASE}/rubrics").mock(return_value=httpx.Response(200, json=[]))
            result = await gazette_list_rubrics(RubricsInput())
        assert "Total: **0**" in result

    @pytest.mark.asyncio
    async def test_unreachable_upstream_is_an_error_not_an_empty_result(self):
        """The distinction this whole server is built around: "nothing found"
        and "could not look" must never render the same."""
        _reset_rubrics_cache()
        with respx.mock:
            respx.get(f"{GAZETTE_BASE}/rubrics").mock(side_effect=httpx.ConnectError("down"))
            result = await gazette_list_rubrics(RubricsInput())
        assert "KEIN leeres Ergebnis" in result

    @pytest.mark.asyncio
    async def test_json_format_is_machine_readable(self):
        _reset_rubrics_cache()
        with respx.mock:
            respx.get(f"{GAZETTE_BASE}/rubrics").mock(
                return_value=httpx.Response(200, json=MOCK_RUBRICS)
            )
            result = await gazette_list_rubrics(RubricsInput(response_format="json"))
        import json

        json.loads(result)

    @pytest.mark.asyncio
    async def test_every_green_rubric_the_upstream_offers_is_listed(self):
        """The general form: a listing that drops a green rubric the source
        does publish makes it undiscoverable even though the server serves it."""
        _reset_rubrics_cache()
        with respx.mock:
            respx.get(f"{GAZETTE_BASE}/rubrics").mock(
                return_value=httpx.Response(200, json=MOCK_RUBRICS)
            )
            result = await gazette_list_rubrics(RubricsInput())
        offered = {r["code"] for r in MOCK_RUBRICS if r.get("code")}
        missing = [r for r in offered & set(GREEN_RUBRICS) if r not in result]
        assert not missing, f"green rubrics missing from the listing: {missing}"
