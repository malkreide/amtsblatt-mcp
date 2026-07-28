# Running more than one instance (SCALE-002, SCALE-003, SEC-009)

This document exists because three audit checks point at the same thing from
different angles: what happens to a client's session when the server is not a
single process.

## The short version

MCP over Streamable HTTP or SSE gives each client a session, identified by the
`Mcp-Session-Id` header. The SDK keeps that session **in process memory**. Two
instances behind a round-robin load balancer therefore break clients: the
`initialize` lands on instance A, the next call lands on instance B, and B has
never heard of that session.

There are exactly two ways out, and a third that removes the question.

## Option 1 — run stateless (simplest, and usually right here)

**Not available here yet.** This server serves the legacy SSE transport
(`mcp.sse_app()`), which has no stateless mode; using it would mean migrating to
streamable-http, which is a deliberate change to a cloud-deployed service rather
than a remediation step. The sister server offers `MCP_STATELESS=1` with
`MCP_TRANSPORT=streamable-http`, and the reasoning below applies there.

When it does apply: The SDK then builds
a fresh transport per request and tracks no session at all. Any instance can
serve any request; no affinity is needed and no session state exists to lose.

This is opt-in rather than the default because it is not free:

- **No SSE stream resumption.** `Last-Event-ID` needs a session to resume into.
- **No server-initiated notifications.** They need a session to be delivered to.

For a read-only server with no per-user state, neither matters much. For a
single-instance local run, stateless buys nothing.

Both servers keep the bearer gate in front of the transport either way; see
`SECURITY.md` for the operator notes on running the SSE transport exposed.

## Option 2 — sticky sessions at the edge

Keep sessions, and make the load balancer route a given `Mcp-Session-Id` to the
same instance every time.

### nginx

```nginx
upstream mcp_backend {
    # Route by the MCP session header. `consistent` keeps the mapping stable
    # when an instance is added or removed, so only 1/N sessions move instead
    # of all of them.
    hash $http_mcp_session_id consistent;

    server mcp-1:8000 max_fails=3 fail_timeout=30s;
    server mcp-2:8000 max_fails=3 fail_timeout=30s;
}

server {
    location /sse {
        proxy_pass http://mcp_backend;
        proxy_http_version 1.1;

        # SSE and streamable-http are long-lived; buffering breaks them.
        proxy_buffering off;
        proxy_read_timeout 3600s;

        proxy_set_header Host              $host;
        proxy_set_header Mcp-Session-Id    $http_mcp_session_id;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Kubernetes Ingress (ingress-nginx)

```yaml
metadata:
  annotations:
    nginx.ingress.kubernetes.io/upstream-hash-by: "$http_mcp_session_id"
    nginx.ingress.kubernetes.io/proxy-buffering: "off"
    nginx.ingress.kubernetes.io/proxy-read-timeout: "3600"
```

`upstream-hash-by` on the header is preferable to cookie affinity: an MCP client
is not a browser and may not keep cookies at all, whereas it is required to send
`Mcp-Session-Id`.

### What to expect on failover

Affinity is not durability. If the instance holding a session dies, the session
dies with it — the hash simply picks a new instance, which returns
`404 Not Found` for the unknown session id. A correct MCP client re-initializes
and continues; a client that does not will surface an error.

**That is the honest failover behaviour, and it is why Option 1 or 3 is better
if you actually need resilience.** Sticky sessions prevent *misrouting*; they do
not prevent *loss*.

## Option 3 — shared session state

Back the session manager with Redis or equivalent so any instance can serve any
session and an instance dying loses nothing.

**Not implemented here.** It requires replacing the SDK's in-process
`StreamableHTTPSessionManager`, which is not an extension point FastMCP exposes,
plus a Redis dependency neither server currently has. If you need this, Option 1
gets you the same availability for a read-only server at none of the cost.

## Session lifetime

`StreamableHTTPSessionManager` accepts a `session_idle_timeout`, but **FastMCP
does not pass it through** — it is not in `Settings` and there is no constructor
argument for it (verified against `mcp` 1.28.1). Setting an explicit server-side
TTL therefore means constructing the session manager directly and bypassing
`FastMCP.streamable_http_app()`.

Until that changes, bound session lifetime at the edge instead: the
`proxy_read_timeout` above caps how long an idle stream is held open, and a
`fail_timeout` bounds how long a dead instance keeps receiving traffic.

This is a real gap rather than an oversight, and it is why `SCALE-002` is not
recorded as passing: the check asks for an explicitly set TTL, and the supported
API does not offer one.

## Why `SEC-009` cannot pass regardless

`SEC-009` asks that the session id be cryptographically bound to a **user id
taken from a validated OAuth token's `sub` claim**.

Neither server in this portfolio has an identity provider. This server has a single shared bearer key that identifies the *deployment*,
not a user; the sister server `swiss-procurement-mcp` has no authentication at
all. There is no `sub` claim, so there is nothing to bind a session to.

This is not an effort question — the input does not exist. What *is* true today:

| Criterion | State |
|---|---|
| Session id entropy | `uuid4().hex` from the SDK — 122 random bits, marginally under the 128 the check asks for, and not ours to change |
| User id from a validated token | **Impossible** — no identity provider |
| Session bound to user id | **Impossible** — same reason |
| 401/403 on mismatch | Not applicable — no user to mismatch |
| Explicit TTL | Not settable through FastMCP (see above) |
| Server-side invalidation | **Yes** — `DELETE` on the streamable-http endpoint terminates a session |

Running stateless (Option 1) is the strongest available answer: with no sessions,
session hijacking and cross-session access are structurally impossible rather
than merely unlikely. That still does not make the check *pass* — it asks for
binding, not for absence — but it is a better security position than a bound
session would give a server that has no users to bind to.

Closing `SEC-009` properly means adding an OAuth/OIDC provider, which would also
unblock `SEC-002` and `SEC-003` in the sister server. That is a deliberate
product decision, not a remediation task.
