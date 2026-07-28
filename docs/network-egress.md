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
_DEFAULT_ALLOWED_HOSTS = frozenset({"amtsblattportal.ch", "www.amtsblattportal.ch"})
ALLOWED_HOSTS: frozenset[str] = frozenset(...)   # MCP_ALLOWED_HOSTS override
```

Every outbound request passes the host check before it is sent. A request to a
host outside the list raises `EgressDenied` — a subclass of
`httpx.RequestError` — so it fails inside the process rather than leaving it.

This is second-layer defence, not the primary control: the base URL is
hardcoded and no user input reaches the host component of a URL. The guard
exists for the case the primary control fails — most plausibly a dependency
following a redirect to an unexpected host, or a future refactor introducing a
foreign base URL.

## Overriding the allow-list

`MCP_ALLOWED_HOSTS` takes a comma-separated list.

> **An override REPLACES the default entirely.** It is not additive. An
> override that omits `amtsblattportal.ch` disables the server — every request
> raises `EgressDenied`. This is deliberate: a partially-specified allow-list
> should fail loudly rather than silently widen.

```bash
MCP_ALLOWED_HOSTS=amtsblattportal.ch,www.amtsblattportal.ch,mirror.example.ch
```

To add a permanent upstream:

1. Add the host to `_DEFAULT_ALLOWED_HOSTS` in `server.py`.
2. Thread the new base URL through explicitly — never derive a host from user
   input.
3. Add a row to the table above and note it in `CHANGELOG.md`.
4. Re-check the lethal-trifecta assessment in `SECURITY.md`: a second upstream
   is exactly what turns the exfiltration leg on.

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
