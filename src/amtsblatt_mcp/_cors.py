"""CORS for the HTTP transports (SDK-004).

A browser-based client cannot *send* a non-safelisted request header unless the
server names it in `Access-Control-Allow-Headers`, and cannot *read* a response
header unless the server names it in `Access-Control-Expose-Headers`. Both lists
are therefore part of the protocol surface, not decoration: a header missing
here fails the preflight, before the first byte of MCP is exchanged.

Spec `2026-07-28` moved request *routing* into headers — `Mcp-Method`,
`Mcp-Name` and `Mcp-Protocol-Version` ride on every streamable-http request —
while abolishing protocol-level sessions. The allow-list had been written for
the older shape and named only `Mcp-Session-Id`, so a browser client on the
current spec was rejected at the preflight while stdio and Python clients, which
no preflight applies to, kept working. `Mcp-Session-Id` stays listed for as long
as `/sse` does; it is the deprecated transport's header, not the new one's.

Origins are fail-closed. `MCP_CORS_ORIGINS` is unset by default, meaning no
cross-origin browser access at all. An operator who wants browser clients names
the origins; nobody inherits a permissive default they did not ask for.

`*` is accepted but never silently: it logs a WARNING and forces
`allow_credentials=False`. Browsers reject `Access-Control-Allow-Origin: *`
together with credentials, so honouring both would ship a configuration that
fails at request time instead of at startup.

**Ordering matters here.** This server puts bearer auth in front of the HTTP app,
and a browser never sends `Authorization` on a preflight `OPTIONS`. If auth ran
before CORS, every preflight would 401 and browser clients would be locked out
entirely — with a symptom that points at the wrong layer. `apply_cors` must
therefore be the *last* middleware added, because Starlette runs the most
recently added one first.
"""

from __future__ import annotations

import logging
import os

from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware

from ._log import log_event

SESSION_HEADER = "Mcp-Session-Id"

# The headers spec 2026-07-28 routes a request by, in the SDK's own spelling
# (`mcp.shared.inbound`): the JSON-RPC method, the tool/prompt/resource the call
# names, and the protocol revision the request is written against.
# `test_cors_names_every_routing_header_the_sdk_reads` holds this list against
# those constants, so an SDK rename surfaces as a failing test rather than as a
# browser client that mysteriously stops connecting.
#
# `Mcp-Param-*` is deliberately absent. CORS allows no prefix wildcard, and this
# server annotates no input field with `x-mcp-header`, so no such header is ever
# sent. `test_no_tool_schema_declares_an_mcp_param_header` fails the day one is
# added — the reminder that it has to be named here too.
ROUTING_HEADERS = ["Mcp-Method", "Mcp-Name", "Mcp-Protocol-Version"]

# `Last-Event-ID` is how an SSE client resumes a dropped stream; omitting it
# would break reconnection only under packet loss — the worst kind of bug to
# discover in production.
ALLOW_HEADERS = [
    "Content-Type",
    "Authorization",
    *ROUTING_HEADERS,
    SESSION_HEADER,
    "Last-Event-ID",
]

# DELETE terminates a session. Without it a browser client can open sessions but
# never close them.
ALLOW_METHODS = ["GET", "POST", "DELETE", "OPTIONS"]

# Only the deprecated SSE transport ever emits this on a response. It stays
# until `/sse` goes; nothing on the streamable-http path sets it.
EXPOSE_HEADERS = [SESSION_HEADER]


def configured_origins() -> list[str]:
    """Parse `MCP_CORS_ORIGINS`. Empty by default — no cross-origin access."""
    raw = os.environ.get("MCP_CORS_ORIGINS", "")
    return [o.strip() for o in raw.split(",") if o.strip()]


def apply_cors(app: Starlette) -> Starlette:
    """Attach CORS to the HTTP app and return it. Must be added last."""
    origins = configured_origins()
    wildcard = "*" in origins

    if wildcard:
        log_event(
            logging.WARNING,
            "cors_wildcard_origin",
            hint=(
                "MCP_CORS_ORIGINS contains '*'; any site can call this server. "
                "Credentials are disabled as a result — browsers reject a "
                "wildcard origin together with credentials. Name explicit "
                "origins for a production deployment."
            ),
        )
    elif not origins:
        log_event(
            logging.INFO,
            "cors_no_origins",
            hint=(
                "MCP_CORS_ORIGINS is unset, so browser-based MCP clients are "
                "not permitted. Set it to a comma-separated origin list to "
                "enable them. stdio and non-browser clients are unaffected."
            ),
        )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=ALLOW_METHODS,
        allow_headers=ALLOW_HEADERS,
        expose_headers=EXPOSE_HEADERS,
        allow_credentials=bool(origins) and not wildcard,
    )
    return app
