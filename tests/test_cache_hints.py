"""SEP-2549: `tools/list` must answer with a freshness hint, not with silence.

Spec `2026-07-28` gives every cacheable result a `ttlMs` and a `cacheScope`.
The SDK fills neither on its own — `CacheHint()` defaults to `ttl_ms=0`,
`scope="private"`, which is the wire encoding of "already stale, never share
it". A server that passes no `cache_hints` therefore does not stay neutral: it
tells every client to re-list on every connection, for a list that cannot change
while the process runs.

Asserted over a real `ClientSession` rather than by reading `CACHE_HINTS` back
out of the module. The constant is the input to the behaviour, not the
behaviour: `MCPServer` applies the hint per field and only to results whose
handler left it unset, so reading the dict would pass just as happily if the
argument were dropped at the constructor. `test_a_server_without_the_hints_says_nothing`
is the negative control for exactly that — it builds a hint-less server and
shows the defaults coming back.
"""

from __future__ import annotations

from mcp import Client
from mcp.server.caching import CACHEABLE_METHODS
from mcp.server.mcpserver import MCPServer

from amtsblatt_mcp._app import CACHE_HINTS, LIST_CACHE_TTL_MS
from amtsblatt_mcp.server import mcp

# No module-level `pytest.mark.asyncio`: two tests here are synchronous, and the
# mark would warn on them. `asyncio_mode = "auto"` in pyproject runs the async
# ones without it.


async def test_the_tool_list_carries_the_ttl() -> None:
    async with Client(mcp) as client:
        result = await client.list_tools()

    assert result.ttl_ms == LIST_CACHE_TTL_MS, (
        f"tools/list answered with ttlMs={result.ttl_ms}; clients re-list on every "
        "connection when this is 0"
    )


async def test_the_tool_list_is_shareable_across_authorization_contexts() -> None:
    """`public` is a claim about this server, so it is worth stating out loud.

    The six tools are registered at import and the list is identical for every
    caller — there is no per-caller filtering to leak. The green allow-list is
    enforced inside the tools on each request, not by hiding a tool from anyone,
    so a shared cache of the list discloses nothing.
    """
    async with Client(mcp) as client:
        result = await client.list_tools()

    assert result.cache_scope == "public"


async def test_the_hint_is_long_enough_to_be_worth_sending() -> None:
    """A hint of a few seconds is indistinguishable from none in practice.

    Guards the direction of a future edit rather than the exact number: dropping
    the TTL towards zero silently restores the behaviour this test exists to
    prevent.
    """
    assert LIST_CACHE_TTL_MS >= 60_000


async def test_a_server_without_the_hints_says_nothing() -> None:
    """The negative control: the assertions above are not passing vacuously.

    A bare `MCPServer` — same SDK, same client, no `cache_hints` — answers with
    the defaults. If this ever starts returning our TTL, the SDK grew a default
    of its own and the tests above stopped proving that we set it.
    """
    async with Client(MCPServer("control")) as client:
        result = await client.list_tools()

    assert result.ttl_ms == 0
    assert result.cache_scope == "private"


def test_every_hinted_method_is_one_the_spec_can_cache() -> None:
    """`MCPServer` validates this at construction, which is why it is worth a
    test: a typo'd key would raise at import and the failure would surface as a
    collection error somewhere unrelated. Named here instead."""
    unknown = sorted(set(CACHE_HINTS) - set(CACHEABLE_METHODS))
    assert not unknown, f"not cacheable per spec 2026-07-28: {unknown}"


def test_no_hint_describes_a_surface_this_server_does_not_have() -> None:
    """`prompts/list` and `resources/list` are cacheable methods, and hinting at
    them would be a lie about what is registered. The day either is registered,
    this test is the reminder to hint at it deliberately."""
    assert set(CACHE_HINTS) == {"tools/list", "server/discover"}
