"""Tool-naming scheme: every exposed tool carries the `gazette_` prefix.

ARCH-001 regressed to `partial` in the 2026-07-27 audit because v0.2.0 prefixed
only the two tools that collided with `swiss-procurement-mcp` and left the other
three bare. A mixed scheme neither disambiguates reliably nor stays predictable,
so the rule is now "all of them", and this test is what keeps it that way — a
tool added without the prefix fails here rather than in a client's tool list.

Dropping the prefix instead was the other option and is not available: the
sister server also exposes `source_status`, so an unprefixed name collides the
moment both servers are mounted in one client.
"""

from __future__ import annotations

import pytest

from amtsblatt_mcp.server import mcp

TOOL_PREFIX = "gazette_"

# Kept in sync deliberately: a rename has to be a conscious edit here too.
EXPECTED_TOOLS = {
    "gazette_search_publications",
    "gazette_search_detailed",
    "gazette_search_procurement",
    "gazette_get_publication",
    "gazette_list_rubrics",
    "gazette_source_status",
}


async def _tool_names() -> set[str]:
    return {t.name for t in await mcp.list_tools()}


@pytest.mark.asyncio
async def test_every_tool_carries_the_prefix() -> None:
    unprefixed = sorted(n for n in await _tool_names() if not n.startswith(TOOL_PREFIX))
    assert not unprefixed, (
        f"tools without the '{TOOL_PREFIX}' prefix: {unprefixed}. "
        "The naming scheme is all-or-nothing — see ARCH-001."
    )


@pytest.mark.asyncio
async def test_tool_surface_is_exactly_the_expected_set() -> None:
    assert await _tool_names() == EXPECTED_TOOLS


@pytest.mark.asyncio
async def test_prefix_is_leading_not_infix() -> None:
    """`search_gazette_procurement` was the old infix form — it is not predictable."""
    for name in await _tool_names():
        rest = name[len(TOOL_PREFIX) :]
        assert TOOL_PREFIX.rstrip("_") not in rest, (
            f"{name!r} repeats 'gazette' after the prefix; the prefix leads, once."
        )


# ---------------------------------------------------------------------------
# OPS-001: a coverage floor, so a new tool cannot arrive under-tested
# ---------------------------------------------------------------------------

UNIT_FLOOR = 5
LIVE_FLOOR = 1


def _coverage() -> dict[str, dict[str, int]]:
    """Count unit and live tests mentioning each tool.

    Live tests are counted by *file* rather than by scanning for a decorator.
    An earlier version of this counting logic split on decorators and
    mis-attributed per-function `@pytest.mark.live` markers, reporting zero live
    coverage for every tool — trusted in the other direction it would have
    reported full coverage and let the finding close on a scripting bug. All
    live tests now live in `tests/test_live.py`, which makes the count a file
    membership question rather than a parsing one.
    """
    import pathlib
    import re

    root = pathlib.Path(__file__).resolve().parent
    counts = {t: {"unit": 0, "live": 0} for t in EXPECTED_TOOLS}
    for path in root.glob("test_*.py"):
        kind = "live" if path.name == "test_live.py" else "unit"
        blocks = re.split(r"\n(?=(?:@[^\n]*\n)*\s*(?:async )?def test_)", path.read_text(encoding="utf-8"))
        for block in blocks:
            if not re.search(r"(?:async )?def test_", block):
                continue
            for tool in EXPECTED_TOOLS:
                if tool in block:
                    counts[tool][kind] += 1
    return counts


def test_every_tool_meets_the_unit_test_floor() -> None:
    short = {t: c["unit"] for t, c in _coverage().items() if c["unit"] < UNIT_FLOOR}
    assert not short, f"tools below the {UNIT_FLOOR}-unit-test floor: {short}"


def test_every_tool_has_a_live_test() -> None:
    """A mocked suite proves the server handles the shape it was told to
    expect. It cannot notice when the upstream changes that shape."""
    short = [t for t, c in _coverage().items() if c["live"] < LIVE_FLOOR]
    assert not short, f"tools with no live test: {short}"


def test_live_tests_are_all_in_one_file() -> None:
    """Scattered live tests are how this finding stayed open: the live suite
    looked complete because nobody could count it in one place."""
    import pathlib
    import re

    # Matched at line start so prose mentioning the marker (as the docstring in
    # `_coverage` does) is not itself a violation.
    decorator = re.compile(r"^\s*@pytest\.mark\.live", re.M)
    root = pathlib.Path(__file__).resolve().parent
    stray = [
        p.name
        for p in root.glob("test_*.py")
        if p.name != "test_live.py" and decorator.search(p.read_text(encoding="utf-8"))
    ]
    assert not stray, f"live markers outside tests/test_live.py: {stray}"


def test_otel_tests_are_not_silently_skipped() -> None:
    """OBS-006's tests use `importorskip`.

    Without opentelemetry in the dev extra they skip in CI, and a test that
    always skips is not a test — it is a green tick with nothing behind it.
    """
    import pathlib

    pyproject = (pathlib.Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(
        encoding="utf-8"
    )
    dev = pyproject.split("dev = [", 1)[1].split("]", 1)[0]
    assert "opentelemetry-sdk" in dev, (
        "tests/test_otel.py would skip in CI: add opentelemetry-sdk to the dev extra"
    )
