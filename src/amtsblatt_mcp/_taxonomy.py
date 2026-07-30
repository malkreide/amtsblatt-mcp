"""The rubric taxonomy cache, and code validation against it.

Extracted from `server.py` for `ARCH-011`.

Two distinct checks are deliberately kept together here, because they answer
different questions and confusing them is how a scope gate leaks. `is_green`
(in `rubrics`) answers *may this server serve the rubric*; `_validate_rubric_code`
answers *does the rubric exist upstream at all*. A caller asking for a code that
is real but blocked must get the scope explanation, not "no such rubric" — the
two are different claims and only one of them is this server's own doing.

The taxonomy itself is cached because it is large and effectively static;
publication content never is, and never will be — official publications carry
statutory deletion periods a cache outliving them would undermine.
"""

from __future__ import annotations

import difflib
from time import monotonic

from ._http import _get_json
from .constants import RUBRICS_TTL_SECONDS, GazetteInvalidCode
from .rubrics import is_green

# ---------------------------------------------------------------------------
# Taxonomy cache
# ---------------------------------------------------------------------------

_rubrics_cache: tuple[float, list[dict]] | None = None


async def _fetch_rubrics(ttl: float | None = None) -> tuple[list[dict], bool]:
    """Fetch the rubric/subRubric taxonomy with a TTL cache (default 24 h).

    Returns (data, from_cache). This is *taxonomy*, not publication content —
    caching it does not conflict with the no-persistence rule.
    """
    global _rubrics_cache
    effective_ttl = RUBRICS_TTL_SECONDS if ttl is None else ttl
    now = monotonic()
    if _rubrics_cache and now - _rubrics_cache[0] < effective_ttl:
        return _rubrics_cache[1], True
    data = await _get_json("/rubrics")
    if not isinstance(data, list):
        data = []
    _rubrics_cache = (now, data)
    return data, False


def rubrics_cache_state() -> tuple[float, list[dict]] | None:
    """The cache entry, read live, for whoever reports source health.

    An accessor rather than a module global other modules reach into, because
    the refactor that split this file out got that wrong first:
    `tools/status.py` did `from .._taxonomy import _rubrics_cache`, which binds
    the value `None` at import time. Seeding or resetting the cache afterwards
    was invisible to it, so the status tool would have reported the taxonomy as
    never cached no matter what — quietly, with no test failing, because every
    test that seeds the cache seeds it for the *search* path.

    A function cannot be captured that way.
    """
    return _rubrics_cache


def _reset_rubrics_cache() -> None:
    """Test helper: clear the rubrics cache between tests."""
    global _rubrics_cache
    _rubrics_cache = None


def _extract_rubric_codes(rubrics_data: list[dict]) -> tuple[set[str], set[str]]:
    """Return (rubric_codes, subRubric_codes) from the taxonomy, defensively."""
    rubric_codes: set[str] = set()
    sub_codes: set[str] = set()
    for r in rubrics_data:
        if not isinstance(r, dict):
            continue
        if r.get("code"):
            rubric_codes.add(r["code"])
        for s in r.get("subRubrics", []) or []:
            if isinstance(s, dict) and s.get("code"):
                sub_codes.add(s["code"])
    return rubric_codes, sub_codes


async def _validate_rubric_code(code: str, kind: str) -> None:
    """Validate a code against the live taxonomy (Silent Empty guard).

    An invalid code returns HTTP 200 with an empty result, indistinguishable
    from a legitimate no-hit. Validation therefore happens BEFORE any
    /publications call, and fails with the closest valid codes.

    Only *green* codes are ever suggested — proposing a blocked rubric as a
    "did you mean" would be a circumvention hint.
    """
    rubrics_data, _ = await _fetch_rubrics()
    rubric_codes, sub_codes = _extract_rubric_codes(rubrics_data)
    valid = rubric_codes if kind == "rubric" else sub_codes
    if code in valid:
        return
    green_valid = sorted(c for c in valid if is_green(c))
    suggestions = difflib.get_close_matches(code, green_valid, n=5, cutoff=0.0)
    hint = ", ".join(suggestions) if suggestions else "— (Taxonomie via gazette_list_rubrics)"
    raise GazetteInvalidCode(
        f"Ungültiger {kind}-Code «{code}». Nächstliegende erschlossene Codes: {hint}."
    )


# ---------------------------------------------------------------------------
