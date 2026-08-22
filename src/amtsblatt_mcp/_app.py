"""The `MCPServer` instance, alone in its own module.

Extracted from `server.py` for `ARCH-011`, and it is the piece that makes the
split possible at all. The tool modules need `@mcp.tool` at import time while
`server.py` needs to import those modules so the tools get registered — pointing
both at this module is what keeps that from being a cycle.

`server.py` stays the composition root: it imports `tools`, which registers
everything against the instance defined here.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from mcp.server.caching import CacheHint
from mcp.server.mcpserver import MCPServer
from mcp.types import LATEST_PROTOCOL_VERSION

from ._http import _close_client
from ._log import log_event

# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------


@asynccontextmanager
async def _lifespan(_server: MCPServer):
    """Server lifespan: guarantee the shared HTTP client is closed on shutdown.

    The client itself is created lazily on first request (see `_get_client`),
    so nothing needs to be opened here — this exists to release pooled
    connections cleanly when the server stops.
    """
    try:
        yield {}
    finally:
        await _close_client()


# ARCH-012: the MCP protocol version this server is written and tested against,
# pinned explicitly rather than inherited from whatever the SDK happens to
# default to.
#
# The SDK negotiates the version in the session layer and offers no constructor
# parameter for it, so the pin cannot be enforced by configuration. It is
# enforced by detection instead: a mismatch logs at WARNING on startup, and
# tests/test_protocol_version.py fails in CI. That splits the two audiences
# correctly — an SDK bump breaks the build for us, not the runtime for someone
# who upgraded `mcp` downstream.
MCP_PROTOCOL_VERSION = "2026-07-28"

if LATEST_PROTOCOL_VERSION != MCP_PROTOCOL_VERSION:
    log_event(
        logging.WARNING,
        "protocol_version_drift",
        pinned=MCP_PROTOCOL_VERSION,
        sdk_latest=LATEST_PROTOCOL_VERSION,
        hint="the installed mcp SDK negotiates a different protocol version than "
        "this server was tested against; see the README's MCP Protocol Version section",
    )


# SEP-2549, spec 2026-07-28: every cacheable list result carries `ttlMs` and
# `cacheScope`. The SDK defaults both to "immediately stale, never shared", so
# a server that says nothing makes each client re-list on every connection —
# and this list cannot change while the process runs. The six tools are
# registered at import by `tools/`; there is no dynamic registration, no
# per-caller filtering and no capability that would vary the list.
#
# `public` follows from that same fact rather than from convenience: the answer
# is identical for every authorization context, so sharing a cached copy across
# them discloses nothing. It would be wrong the moment a tool list became
# caller-dependent — the green allow-list is enforced per request inside the
# tools, not by hiding tools from anyone.
#
# Five minutes, not a day: the ceiling worth accepting is how long a client may
# keep calling a tool list from before a deployment. `server/discover` carries
# the same hint because it answers from the same static registration.
#
# `prompts/list` and `resources/list` are left unset on purpose. This server
# registers neither, so hinting at them would describe a surface that does not
# exist.
LIST_CACHE_TTL_MS = 300_000

CACHE_HINTS = {
    "tools/list": CacheHint(ttl_ms=LIST_CACHE_TTL_MS, scope="public"),
    "server/discover": CacheHint(ttl_ms=LIST_CACHE_TTL_MS, scope="public"),
}


mcp = MCPServer(
    "amtsblatt_mcp",
    lifespan=_lifespan,
    cache_hints=CACHE_HINTS,
    instructions=(
        "Read-only access to amtsblattportal.ch — the Swiss official gazette portal "
        "(SHAB plus 27 cantonal gazettes). Covers public procurement (Submissionen), "
        "cantonal and communal notices, enactments, spatial planning and the "
        "commercial register.\n\n"
        "IMPORTANT — scope: this server deliberately exposes ONLY rubrics without "
        "systematic natural-person data. Bankruptcies, debt collection, inheritance "
        "calls, civil status, court summons and building applications are NOT "
        "queryable, and no person-name search parameter exists in any tool. This is "
        "a data-protection decision, not a limitation to work around; do not attempt "
        "to reach those rubrics by other means. For publications about a specific "
        "COMPANY (a legal person, including its bankruptcy) use the UID join in the "
        "companion server `register-mcp`.\n\n"
        "Start with `gazette_list_rubrics` to see what is queryable, then "
        "`gazette_search_publications` or `gazette_search_procurement`, then `gazette_get_publication(id=…)` "
        "for the official full text — the list endpoint returns metadata only."
    ),
)


def bind_host() -> str:
    """Bind loopback by default; exposing on all interfaces requires an explicit
    MCP_HOST=0.0.0.0. This prevents accidental NeighborJack exposure on shared
    networks, on top of the mandatory bearer auth + rate limit enforced below.
    Containers set MCP_HOST=0.0.0.0 deliberately (see compose.yaml).

    Read on demand rather than stored on the server object: `mcp` 2.0 dropped
    the `host` and `port` settings, and they were only ever a detour — the
    values come from the environment and go to uvicorn.
    """
    return os.environ.get("MCP_HOST", "127.0.0.1")


def bind_port() -> int:
    return int(os.environ.get("PORT", "8000"))


# ---------------------------------------------------------------------------
