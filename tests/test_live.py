"""Live tests against amtsblattportal.ch (OPS-001).

Deselected by default and gated to the nightly / manual workflow, so the
mainline build is never held hostage to gazette availability.

Every tool has at least one test here. That floor exists because a mocked suite
proves the server handles the *shape* it was told to expect — it cannot notice
when the upstream changes that shape. The two servers in this portfolio have
each shipped a bug of exactly that kind.

The green allow-list is exercised against the real API too
(`test_live_blocked_rubric_still_refuses`): the data-protection invariant has to
hold against the live upstream, not only against fixtures we wrote.
"""

from __future__ import annotations

import pytest

from amtsblatt_mcp._taxonomy import _reset_rubrics_cache as _reset
from amtsblatt_mcp.inputs import (
    DetailedSearchInput,
    ProcurementInput,
    PublicationInput,
    RubricsInput,
    SearchInput,
    StatusInput,
)
from amtsblatt_mcp.server import (
    gazette_get_publication,
    gazette_list_rubrics,
    gazette_search_detailed,
    gazette_search_procurement,
    gazette_search_publications,
    gazette_source_status,
)

pytestmark = [pytest.mark.live, pytest.mark.asyncio]


async def test_live_source_status() -> None:
    result = await gazette_source_status(StatusInput())
    assert "✅" in result


async def test_live_list_rubrics() -> None:
    _reset()
    result = await gazette_list_rubrics(RubricsInput())
    assert "Erschlossene Rubriken" in result
    assert "`HR`" in result, "the commercial-register rubric should be listed as green"


async def test_live_search_publications() -> None:
    _reset()
    # rubric + canton, not rubric alone: the upstream silently ignores a bare
    # `rubrics` filter and returns the whole 2.2M corpus, which the server's own
    # Silent-Ignore guard then refuses. Probed live, not assumed.
    result = await gazette_search_publications(SearchInput(rubric="HR", canton="ZH", limit=3))
    assert "amtsblattportal.ch" in result
    assert "Fehler" not in result
    assert "ignoriert" not in result, "upstream dropped the filter"


async def test_live_procurement_basel_stadt() -> None:
    _reset()
    result = await gazette_search_procurement(ProcurementInput(canton="BS", limit=5))
    assert "amtsblattportal.ch" in result
    assert "Fehler" not in result


async def test_live_search_detailed() -> None:
    """The aggregated tool fans out to real detail fetches — the path where a
    shape change upstream shows up first."""
    _reset()
    result = await gazette_search_detailed(
        DetailedSearchInput(rubric="HR", canton="ZH", limit=2, top_n=1)
    )
    assert "amtsblattportal.ch" in result
    assert "Fehler" not in result


async def test_live_get_publication_round_trip() -> None:
    """Search for a real id, then fetch it — the only way to exercise
    `gazette_get_publication` against ids we did not invent."""
    _reset()
    listing = await gazette_search_publications(SearchInput(rubric="HR", canton="ZH", limit=1))
    import re

    match = re.search(r"ID: `([^`]+)`", listing)
    assert match, f"no publication id in the listing:\n{listing[:400]}"

    result = await gazette_get_publication(PublicationInput(id=match.group(1)))
    assert "Fehler" not in result
    assert "fail-closed" not in result, "a green-rubric id must not be refused"


async def test_live_blocked_rubric_still_refuses() -> None:
    """The data-protection invariant, against the real upstream."""
    _reset()
    result = await gazette_search_publications(SearchInput(rubric="KK", keyword="Muster"))
    assert "fail-closed" in result


async def test_live_taxonomy_matches_the_coverage_snapshot() -> None:
    """`docs/coverage-matrix.md` is a measurement, and a measurement goes stale.

    The matrix says 84.2 % of the corpus is reachable and names three reasons
    for the rest. That statement is true of the taxonomy as it stood on the
    measuring day. A rubric added upstream is blocked automatically — the
    allow-list sees to that — but it is also *unclassified*, and nothing in the
    repository would say so: `rubrics.py` stays valid, every test stays green,
    and the document keeps claiming a share it no longer has.

    This test is the only place that notices. It compares the live axis against
    `docs/coverage-matrix.json` and fails on any code appearing or disappearing.
    Counts deliberately are not asserted: they grow daily and would make the
    test a nuisance, and a nuisance test gets deleted. The axis is what makes
    the document stale.

    On failure: run `scripts/measure_coverage_matrix.py --triage` for the new
    rubric, classify it in `rubrics.py`, then refresh both the snapshot
    (`--write-snapshot`) and the document in the same commit.
    """
    import json
    from pathlib import Path

    from amtsblatt_mcp._taxonomy import _fetch_rubrics

    snapshot_path = Path(__file__).resolve().parents[1] / "docs" / "coverage-matrix.json"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))["rubrics"]

    _reset()
    rubrics, _ = await _fetch_rubrics()
    live = {row["code"] for row in rubrics if row.get("code")}
    assert live, "empty taxonomy — a shape change, not an empty upstream"

    added = sorted(live - set(snapshot))
    removed = sorted(set(snapshot) - live)
    assert not added, (
        f"{len(added)} new upstream rubric(s) since {snapshot_path.name}: {added}. "
        "They are blocked fail-closed, but unclassified and uncounted — "
        "classify them and refresh the snapshot and docs/coverage-matrix.md."
    )
    assert not removed, (
        f"{len(removed)} rubric(s) gone from upstream: {removed}. "
        "The coverage figures include them; refresh the snapshot and the document."
    )
