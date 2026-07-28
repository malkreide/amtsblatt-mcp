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
