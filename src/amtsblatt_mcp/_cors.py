"""CORS for the SSE transport (SDK-004).

MCP over SSE carries the session in the `Mcp-Session-Id` header. A browser-based
client cannot *read* a response header unless the server names it in
`Access-Control-Expose-Headers`, and cannot *send* it on the next request unless
the server names it in `Access-Control-Allow-Headers`. Without both, a browser
client completes the initialize handshake and then loses the session on the very
next call — which looks like a broken server rather than a missing header.

Origins are fail-closed. `MCP_CORS_ORIGINS` is unset by default, meaning no
cross-origin browser access at all. An operator who wants browser clients names
the origins; nobody inherits a permissive default they did not ask for.

`*` is accepted but never silently: it logs a WARNING and forces
`allow_credentials=False`. Browsers reject `Access-Control-Allow-Origin: *`
together with credentials, so honouring both would ship a configuration that
fails at request time instead of at startup.

**Ordering matters here.** This server puts bearer auth in front of the SSE app,
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

# `Last-Event-ID` is how an SSE client resumes a dropped stream; omitting it
# would break reconnection only under packet loss — the worst kind of bug to
# discover in production.
ALLOW_HEADERS = ["Content-Type", "Authorization", SESSION_HEADER, "Last-Event-ID"]

# DELETE terminates a session. Without it a browser client can open sessions but
# never close them.
ALLOW_METHODS = ["GET", "POST", "DELETE", "OPTIONS"]

EXPOSE_HEADERS = [SESSION_HEADER]


def configured_origins() -> list[str]:
    """Parse `MCP_CORS_ORIGINS`. Empty by default — no cross-origin access."""
    raw = os.environ.get("MCP_CORS_ORIGINS", "")
    return [o.strip() for o in raw.split(",") if o.strip()]


def apply_cors(app: Starlette) -> Starlette:
    """Attach CORS to the SSE app and return it. Must be added last."""
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
