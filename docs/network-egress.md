# Network egress

`amtsblatt-mcp` makes outbound HTTPS requests to exactly **one** upstream.

| Host | Purpose |
|---|---|
| `amtsblattportal.ch` | The public gazette portal API — search, publication XML, rubric taxonomy |
| `www.amtsblattportal.ch` | Same service; both spellings are allow-listed because the upstream redirects between them |

Nothing else. No telemetry endpoint, no package index, no analytics. The
OpenTelemetry exporter in `_otel.py` is **off unless an OTLP endpoint is
configured**, and when configured that endpoint is the operator's own — see
[Telemetry](#telemetry-opt-in) below.

## Code-layer enforcement (SEC-021)

The allow-list lives in [`server.py`](../src/amtsblatt_mcp/server.py):

```python
ALLOWED_HOSTS: frozenset[str] = frozenset({"amtsblattportal.ch", "www.amtsblattportal.ch"})
```

Every outbound request passes the host check before it is sent. A request to a
host outside the list raises `EgressDenied` — a subclass of
`httpx.RequestError` — so it fails inside the process rather than leaving it.

This is second-layer defence, not the primary control: the base URL is
hardcoded and no user input reaches the host component of a URL. The guard
exists for the case the primary control fails — most plausibly a dependency
following a redirect to an unexpected host, or a future refactor introducing a
foreign base URL.

## The list is not configurable, deliberately

There is no environment override. `MCP_ALLOWED_HOSTS` was removed in 0.9.0.

SEC-021 requires the code-layer allow-list to be non-config-mutable, and the
reasoning holds up: a guard that anything able to set an environment variable
can widen is not a guard. An override also let a misconfigured deployment
replace the set wholesale — it was not additive — which either disabled the
server or silently widened what a followed redirect could reach.

Removing it cost nothing real. `GAZETTE_BASE` is a hardcoded constant, so
nothing in this server ever builds a URL for another host: adding one to the
allow-list could never have caused a request to go there. The old example in
this document suggesting a `mirror.example.ch` entry was misleading for exactly
that reason — nothing would ever have requested it.

To add a genuine second upstream:

1. Add the host to `ALLOWED_HOSTS` in `server.py`.
2. Thread the new base URL through explicitly — never derive a host from user
   input.
3. Add a row to the table above and note it in `CHANGELOG.md`.
4. Re-check the lethal-trifecta assessment in `SECURITY.md`: a second upstream
   is exactly what turns the exfiltration leg on.

Both steps happen in code, where they are reviewed. That is the point.

## Network-layer enforcement

None is shipped. The primary deployment is a local stdio process, where there
is no container network to police.

For the SSE transport or a container deployment, the in-process allow-list is
**not** a substitute for an egress firewall — a compromised dependency runs
with the same privileges as the guard. Add one of:

- Kubernetes: an egress `NetworkPolicy` limited to the gazette host
- Docker: a user-defined network with an egress proxy
- Cloud: a security group / firewall rule on the outbound path

## Telemetry (opt-in)

`_otel.py` configures an OTLP span exporter **only** when an endpoint is set in
the environment. Unset, no tracing traffic is generated and the module is inert.
When set, that endpoint is an additional egress destination the allow-list does
not cover — it goes through the OTLP exporter, not through the gazette client —
so include it in your firewall rules deliberately.

## Verifying

```bash
# The allow-list as the process actually sees it
python -c "from amtsblatt_mcp.server import ALLOWED_HOSTS; print(sorted(ALLOWED_HOSTS))"

# The guard rejects a foreign host
PYTHONPATH=src pytest tests/test_publication.py -k allowlist -q
```
