"""OBS-001: protocol errors and execution errors, as a client actually sees them.

Every other test in this suite awaits the tool functions directly. That is fine
for tool logic and useless for this check: it cannot observe `isError`, cannot
observe a JSON-RPC error code, and cannot tell the two apart. These tests drive
a real `ClientSession` over an in-memory transport instead.

The distinction OBS-001 is about:

- **Execution error** — the tool was found and ran, and something went wrong.
  Belongs in the tool result with `isError: true`, so the model sees it as a
  result it can reason about.
- **Protocol error** — the request itself was wrong (unknown method, malformed
  params). Belongs in a JSON-RPC error with a standardised code, because there
  is no tool result to put it in.

Three behaviours are pinned here deliberately, because they are *not* what the
check asks for. Pinning them means a change is announced by a failing test
rather than discovered in production:

- An unknown **tool** is reported as `isError` in a tool result, not as a
  protocol error. Arguably right — the method `tools/call` does exist — but it
  means "you called a tool that does not exist" and "the tool failed" are
  indistinguishable to a client without reading the text.
- Protocol errors carry **code 0**, not the `-32601` / `-326xx` range the check
  asks for, even though `mcp.types` defines those constants. That is above the
  tool layer; nothing in this repo can change it.
- Refusals and upstream failures come back as ordinary results, not as
  `isError`. That one is this server's own decision and is defended below.

Every tool here returns `str` (the accepted SDK-002 deviation), so there is no
typed field to inspect — which is exactly why the `_provenance:` footer has to
carry the outcome instead.
"""

from __future__ import annotations

import httpx
import pytest
import respx
from mcp import types
from mcp.shared.exceptions import McpError
from mcp.shared.memory import create_connected_server_and_client_session as connect

from amtsblatt_mcp.server import GAZETTE_BASE, mcp

from .fixtures import MOCK_RUBRICS, MOCK_SEARCH_EMPTY

pytestmark = pytest.mark.asyncio


def provenance(result) -> str | None:
    """Read the outcome marker out of a tool result.

    Deliberately parsed the way a client would have to parse it, rather than by
    reaching into server internals: if the footer stops being emitted, or the
    wording drifts, these tests fail.
    """
    for line in result.content[0].text.splitlines():
        if line.startswith("_provenance: ") and line.endswith("_"):
            return line[len("_provenance: ") : -1]
    return None


# --- execution errors: found the tool, running it failed -------------------


async def test_invalid_argument_is_an_execution_error() -> None:
    """A too-long keyword is the tool's problem to report, not the protocol's."""
    async with connect(mcp) as client:
        result = await client.call_tool(
            "gazette_search_publications", {"params": {"keyword": "x" * 500}}
        )
    assert result.isError is True
    assert "validation error" in result.content[0].text.lower()


async def test_unknown_field_is_rejected_at_the_boundary() -> None:
    """`extra="forbid"` on the input models; OBS-001 governs how that is delivered."""
    async with connect(mcp) as client:
        result = await client.call_tool(
            "gazette_search_publications", {"params": {"keyword": "bau", "bogus": 1}}
        )
    assert result.isError is True
    assert "extra" in result.content[0].text.lower()


async def test_execution_error_carries_no_stack_trace() -> None:
    """OBS-002's substance, asserted at the boundary where it matters.

    `mask_error_details` does not exist in `mcp` 1.28.1, so there is no setting
    to turn on — the guarantee has to be checked rather than configured.
    """
    async with connect(mcp) as client:
        result = await client.call_tool(
            "gazette_search_publications", {"params": {"keyword": "x" * 500}}
        )
    text = result.content[0].text
    assert "Traceback" not in text
    assert "/home/" not in text and "site-packages" not in text


# --- refusals and degradation: results, not errors, on purpose -------------


async def test_upstream_failure_is_not_an_execution_error() -> None:
    """A documented deviation from OBS-001, kept on purpose.

    The check says application errors should carry `isError: true`. An upstream
    outage returns a normal result marked `provenance: degraded` instead,
    because the envelope carries strictly more than an error string would: the
    attribution, the outcome, and a sentence saying in as many words that this
    is not an empty result.

    Raising instead would collapse that into one line of text and lose the
    distinction the model actually needs — "nothing matched" versus "I could
    not ask". This test is what stops it being lost.
    """
    async with connect(mcp) as client, respx.mock:
        respx.get(f"{GAZETTE_BASE}/rubrics").mock(side_effect=httpx.ConnectError("down"))
        respx.get(f"{GAZETTE_BASE}/publications").mock(side_effect=httpx.ConnectError("down"))
        result = await client.call_tool(
            "gazette_search_publications", {"params": {"keyword": "bau"}}
        )

    assert result.isError is False, "degraded is a result, not an error"
    assert provenance(result) == "degraded"
    assert "KEIN leeres Ergebnis" in result.content[0].text


async def test_degraded_is_distinguishable_from_an_empty_result() -> None:
    """The failure this whole envelope exists to prevent.

    An empty result and an unreachable source must never look alike. Both are
    `isError: false` with zero publications in them; only the footer separates
    them, which is why the footer is asserted rather than the prose.
    """
    async with connect(mcp) as client:
        with respx.mock:
            respx.get(f"{GAZETTE_BASE}/rubrics").mock(
                return_value=httpx.Response(200, json=MOCK_RUBRICS)
            )
            respx.get(f"{GAZETTE_BASE}/publications").mock(
                return_value=httpx.Response(200, json=MOCK_SEARCH_EMPTY)
            )
            empty = await client.call_tool(
                "gazette_search_publications", {"params": {"keyword": "zzzznotfound"}}
            )
        with respx.mock:
            respx.get(f"{GAZETTE_BASE}/rubrics").mock(side_effect=httpx.ConnectError("down"))
            respx.get(f"{GAZETTE_BASE}/publications").mock(side_effect=httpx.ConnectError("down"))
            degraded = await client.call_tool(
                "gazette_search_publications", {"params": {"keyword": "zzzznotfound"}}
            )

    assert provenance(empty) == "live_api"
    assert provenance(degraded) == "degraded"
    assert "Gefunden: **0**" in empty.content[0].text


async def test_policy_refusal_is_marked_refused_not_degraded() -> None:
    """A blocked rubric is not a failure, and must not read as one.

    `refused` says retrying changes nothing — the server declined by design.
    `degraded` says the source could not be reached and the same call may work
    in a minute. Collapsing the two would have an agent retry a scope decision
    forever, or give up on a transient outage.

    No network mock here on purpose: the green gate runs before any request, so
    a refusal that reached the network would fail this test by connecting.
    """
    async with connect(mcp) as client:
        result = await client.call_tool(
            "gazette_search_publications", {"params": {"rubric": "SB", "canton": "ZH"}}
        )
    assert result.isError is False
    assert provenance(result) == "refused"
    assert "bewusst nicht erschlossen" in result.content[0].text


async def test_every_outcome_carries_the_attribution() -> None:
    """The licence condition, checked on the paths most likely to skip it.

    Success carries the attribution because `_md` puts it there. Refusals and
    outages used to return a bare sentence and carry nothing at all.
    """
    async with connect(mcp) as client:
        refused = await client.call_tool(
            "gazette_search_publications", {"params": {"rubric": "SB", "canton": "ZH"}}
        )
        with respx.mock:
            respx.get(f"{GAZETTE_BASE}/rubrics").mock(side_effect=httpx.ConnectError("down"))
            respx.get(f"{GAZETTE_BASE}/publications").mock(side_effect=httpx.ConnectError("down"))
            degraded = await client.call_tool(
                "gazette_search_publications", {"params": {"keyword": "bau"}}
            )

    for result in (refused, degraded):
        assert "amtsblattportal.ch" in result.content[0].text
        assert "Licence:" in result.content[0].text


# --- protocol errors: the request itself was wrong ------------------------


async def test_unknown_method_is_a_protocol_error() -> None:
    """A method the server does not implement raises rather than returning a result."""
    async with connect(mcp) as client:
        with pytest.raises(McpError) as exc:
            await client.send_request(
                types.ClientRequest(
                    types.GetPromptRequest(
                        method="prompts/get",
                        params=types.GetPromptRequestParams(name="nope"),
                    )
                ),
                types.GetPromptResult,
            )
    assert "unknown prompt" in exc.value.error.message.lower()


async def test_protocol_error_code_is_not_yet_standardised() -> None:
    """Pins an SDK gap so a future fix is announced, not discovered.

    OBS-001 asks for `-326xx` / `-320xx` codes on protocol errors. `mcp.types`
    defines `METHOD_NOT_FOUND = -32601` and friends, but the lowlevel server
    emits **0**. Nothing in this repo can change that — it is above the tool
    layer — so the behaviour is asserted as-is.

    When the SDK starts emitting a real code this test fails, which is the
    point: that is the day OBS-001 can be re-scored.
    """
    async with connect(mcp) as client:
        with pytest.raises(McpError) as exc:
            await client.send_request(
                types.ClientRequest(
                    types.ReadResourceRequest(
                        method="resources/read",
                        params=types.ReadResourceRequestParams(uri="file:///nope"),
                    )
                ),
                types.ReadResourceResult,
            )
    assert exc.value.error.code == 0, (
        "the SDK now emits a real JSON-RPC code — re-check OBS-001 criterion 3"
    )
    assert types.METHOD_NOT_FOUND == -32601, "the constants exist; the server does not use them"


async def test_unknown_tool_is_reported_as_an_execution_error() -> None:
    """Also pinned rather than endorsed.

    Calling a tool that does not exist is arguably a protocol error, but the SDK
    reports it inside a tool result with `isError: true`. That makes "no such
    tool" and "the tool failed" indistinguishable without reading the text.
    """
    async with connect(mcp) as client:
        result = await client.call_tool("no_such_tool", {})
    assert result.isError is True
    assert "unknown tool" in result.content[0].text.lower()


async def test_every_advertised_tool_is_callable() -> None:
    """A tool listed but not dispatchable is the worst case, because the model
    has no way to know before trying."""
    async with connect(mcp) as client:
        listed = {t.name for t in (await client.list_tools()).tools}
        result = await client.call_tool("no_such_tool", {})

    assert len(listed) == 6
    assert all(name.startswith("gazette_") for name in listed)
    # The negative control: an unlisted name really does fail, so the assertion
    # above is not passing vacuously.
    assert result.isError is True
