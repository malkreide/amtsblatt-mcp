"""amtsblatt-mcp — the composition root.

Covers public procurement and official notices across the **green** rubrics of
the Swiss gazette portal. Rubrics carrying systematic natural-person data are
excluded by design — see :mod:`amtsblatt_mcp.rubrics` for the fail-closed
allow-list that governs every rubric code reaching the query string.

Architecture A (live-API-only): the upstream endpoints answer stably without
authentication, so no bulk dump is maintained. Publication content is passed
through and never persisted — official publications have statutory deletion
periods that a cache outliving them would actively undermine.

**`ARCH-011`: this module used to be all 2477 lines of that.** It is now the
composition root and nothing else: it imports `tools`, which registers the six
handlers against the `MCPServer` in `._app`, and owns transport selection and
the entrypoint. The domain code lives in `constants`, `_http`, `_taxonomy`,
`_normalise`, `_xml`, `_envelope`, `inputs` and `tools/`.

The re-exports below are deliberate rather than leftovers. `from
amtsblatt_mcp.server import mcp` is what a deployment does, and the tool
handlers are re-exported so a caller can reach one without knowing which module
under `tools/` it landed in. The split is real — the code moved — while the
import that operators and clients already use keeps working.
"""

from __future__ import annotations

import logging
import os

from pydantic import SecretStr

from . import __version__
from ._app import MCP_PROTOCOL_VERSION, bind_host, bind_port, mcp
from ._log import configure_logging, log_event
from .rubrics import GREEN_RUBRICS
from .tools import (
    gazette_get_publication,
    gazette_list_rubrics,
    gazette_search_detailed,
    gazette_search_procurement,
    gazette_search_publications,
    gazette_source_status,
)

configure_logging()

__all__ = [
    "MCP_PROTOCOL_VERSION",
    # Kept reachable as `server.__version__`. Removing it during the ARCH-011
    # split would have been an unannounced API change, and it is what
    # test_version.py checks against pyproject — the guard exists because three
    # hardcoded literals once drifted apart and OpenTelemetry reported a version
    # three releases behind.
    "__version__",
    "bind_host",
    "bind_port",
    "build_http_app",
    "build_transport_security",
    "gazette_get_publication",
    "gazette_list_rubrics",
    "gazette_search_detailed",
    "gazette_search_procurement",
    "gazette_search_publications",
    "gazette_source_status",
    "main",
    "mcp",
]

# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

# Read once at import, as it always has been: the transport is a deployment
# decision, not something that changes under a running process. Moved here from
# the module that holds the server instance, where it only ever sat because
# everything used to live in one file.
transport = os.environ.get("MCP_TRANSPORT", "stdio")

DEFAULT_RATE_LIMIT = int(os.environ.get("MCP_RATE_LIMIT", "60"))
DEFAULT_RATE_WINDOW = float(os.environ.get("MCP_RATE_WINDOW", "60"))


def build_transport_security(host: str, port: int, origins=()):
    """Host/Origin allow-list for the SSE transport (SEC-005, inbound half).

    Under mcp 2.x this is a per-app kwarg rather than a global setting. Left
    unset, the SDK auto-enables protection only for a loopback bind; a 0.0.0.0
    bind gets nothing, which is exactly how this server is shipped.

    Returns ``None`` when no allow-list can be derived: a non-loopback bind
    with no ``MCP_ALLOWED_HOSTS``. The server is then reached under a service
    or public DNS name this process does not know, and a guessed list would
    reject every real request with HTTP 421. The caller warns instead, and the
    SDK default (no protection on a non-local bind) applies unchanged.
    """
    from mcp.server.transport_security import TransportSecuritySettings

    allowed = [h.strip() for h in os.environ.get("MCP_ALLOWED_HOSTS", "").split(",") if h.strip()]
    loopback = {f"127.0.0.1:{port}", f"localhost:{port}", f"[::1]:{port}"}
    if allowed:
        # Loopback stays reachable for container health checks and debugging.
        hosts = set(allowed) | loopback
    elif host in ("127.0.0.1", "localhost", "::1"):
        hosts = loopback | {f"{host}:{port}"}
    else:
        return None

    # Configured CORS origins must also pass the transport check, or the server
    # rejects exactly the browser clients CORS permits. "*" is matched
    # literally by the SDK (only a trailing ":*" port wildcard exists), so it
    # is not copied across.
    allowed_origins = {o for o in origins if o != "*"}
    allowed_origins |= {f"http://{h}" for h in hosts}
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=sorted(hosts),
        allowed_origins=sorted(allowed_origins),
    )


HTTP_TRANSPORTS = {"streamable-http", "http", "sse"}


def _stateless_requested() -> bool:
    """SEC-009 / SCALE-002: opt into session-free operation.

    Only reachable since the move off SSE. With `stateless_http` the SDK builds
    a fresh transport per request and tracks no session at all, which removes
    both findings rather than solving them: there is no session id to bind to a
    user and none to route consistently to an instance.

    Opt-in rather than default, because it is not free — a stateless server
    cannot resume an interrupted stream or push server-initiated
    notifications. For this server, which keeps no cross-call state, it is
    usually the right trade; the operator decides.
    """
    return os.environ.get("MCP_STATELESS", "").strip().lower() in {"1", "true", "yes"}


def build_http_app(kind: str = "streamable-http"):
    """Build the HTTP Starlette app with auth + rate-limit middleware.

    `kind` is either `streamable-http` (default) or the deprecated `sse`.

    Requires `MCP_API_KEY`. Fails loud at startup otherwise — no implicit
    "auth disabled" mode is supported on any HTTP transport.

    Both transports get the identical middleware stack. That is the point of
    building them through one function: the bearer gate, the rate limit and the
    CORS layer are the controls SEC-002, SEC-008 and SDK-004 are scored on, and
    a transport that quietly skipped one of them would look enforced while not
    being. The only difference is which SDK app-builder is called.
    """
    from ._cors import apply_cors, configured_origins
    from ._middleware import BearerAuthMiddleware, RateLimitMiddleware

    # ARCH-005: held as SecretStr, so an accidental f-string, repr() or log of
    # the config renders "**********" instead of the key. The plaintext is only
    # unwrapped at the one place that needs it — the constant-time comparison.
    api_key = SecretStr(os.environ.get("MCP_API_KEY", "").strip())
    if not api_key.get_secret_value():
        raise SystemExit(
            f"MCP_API_KEY must be set when MCP_TRANSPORT={kind}. "
            "Generate a random key (e.g. `openssl rand -hex 32`) and pass it via env."
        )

    security = build_transport_security(bind_host(), bind_port(), configured_origins())
    if security is None:
        log_event(
            logging.WARNING,
            "dns_rebinding_protection_off",
            host=bind_host(),
            hint="Set MCP_ALLOWED_HOSTS to the hostnames this server is "
            "reachable under; on a non-loopback bind the SDK does not check "
            "the Host header at all.",
        )
    if kind == "sse":
        # Deprecated since spec 2026-07-28 (twelve-month removal window), and
        # the reason this server offers streamable-http at all. Kept working so
        # a deployed client is not broken by an upgrade; the warning is what
        # makes the deadline visible to whoever reads the logs.
        log_event(
            logging.WARNING,
            "sse_transport_deprecated",
            hint="MCP spec 2026-07-28 reclassifies HTTP+SSE as deprecated and "
            "removes protocol-level sessions. Move to "
            "MCP_TRANSPORT=streamable-http; the endpoint changes from "
            "/sse + /messages to /mcp.",
        )
        app = mcp.sse_app(transport_security=security, host=bind_host())
    else:
        stateless = _stateless_requested()
        app = mcp.streamable_http_app(
            transport_security=security, host=bind_host(), stateless_http=stateless
        )
    # Middleware added later runs first → add rate-limit first, then auth, so
    # the rate-limit bucket key is the authenticated token hash.
    app.add_middleware(RateLimitMiddleware, limit=DEFAULT_RATE_LIMIT, window=DEFAULT_RATE_WINDOW)
    app.add_middleware(BearerAuthMiddleware, expected_key=api_key)
    # SDK-004. Added last, therefore runs first: a browser never sends
    # `Authorization` on a preflight OPTIONS, so CORS has to answer the
    # preflight before BearerAuthMiddleware rejects it. Ordered the other way
    # round, every preflight would 401 and browser clients would be shut out
    # with a symptom pointing at the wrong layer.
    apply_cors(app)
    log_event(
        logging.INFO,
        "http_app_built",
        transport=kind,
        stateless=_stateless_requested() and kind != "sse",
        rate_limit=DEFAULT_RATE_LIMIT,
        rate_window=DEFAULT_RATE_WINDOW,
        cors_origins=len(configured_origins()),
    )
    return app


def main() -> None:
    from ._otel import init_otel

    init_otel()
    if transport == "stdio":
        log_event(
            logging.INFO,
            "starting",
            transport="stdio",
            green_rubrics=len(GREEN_RUBRICS),
        )
        mcp.run(transport="stdio")
        return
    if transport in HTTP_TRANSPORTS:
        import uvicorn

        kind = "sse" if transport == "sse" else "streamable-http"
        app = build_http_app(kind)
        log_event(
            logging.INFO,
            "starting",
            transport=kind,
            endpoint="/sse + /messages" if kind == "sse" else "/mcp",
            host=bind_host(),
            port=bind_port(),
        )
        uvicorn.run(
            app,
            host=bind_host(),
            port=bind_port(),
            log_level=mcp.settings.log_level.lower(),
        )
        return
    raise SystemExit(
        f"Unsupported MCP_TRANSPORT={transport!r} "
        "(expected 'stdio', 'streamable-http' or the deprecated 'sse')"
    )


if __name__ == "__main__":
    main()
