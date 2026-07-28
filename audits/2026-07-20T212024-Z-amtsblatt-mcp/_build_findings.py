"""Emit finding docs (findings/<ID>.md) for the as-found fail/partial checks."""

import os
import sys

D = sys.argv[1]
os.makedirs(os.path.join(D, "findings"), exist_ok=True)

FINDINGS = {
    "SDK-001": dict(
        sev="high",
        title="FastMCP Lifespan + shared HTTP client",
        status="closed — remediated 2026-07-20",
        effort="M",
        observed="Each upstream request created a fresh `httpx.AsyncClient` via `_make_client()` inside `_get_json` / `_get_text` / `_probe_endpoint` (server.py:262,278,1478). No FastMCP lifespan existed; no client was shared across calls.",
        expected="A single AsyncClient reused across requests (connection + TLS pooling), owned by an `@asynccontextmanager` lifespan that closes it on shutdown.",
        risk="A new TCP connection and TLS handshake per tool call: added latency, wasted file descriptors, and no keep-alive under load. Not a security defect, but a resilience/efficiency gap the catalog rates `high`.",
        remediation="Added a lazily-created module-level shared client (`_get_client`), a `_close_client` shutdown hook, and a FastMCP `lifespan=_lifespan` that closes it. `_get_json`/`_get_text`/`_probe_endpoint` now reuse it. Regression tests `test_shared_client_is_reused_across_calls` / `test_reset_client_drops_the_shared_instance` added. Full suite green (77 passed).",
    ),
    "SEC-016": dict(
        sev="critical",
        title="0.0.0.0 binding prevention (NeighborJack)",
        status="closed — remediated 2026-07-20",
        effort="S",
        observed="SSE transport hardcoded `mcp.settings.host = '0.0.0.0'` (server.py:748) with no way to bind loopback.",
        expected="Default bind to 127.0.0.1; expose on all interfaces only via an explicit opt-in env var.",
        risk="Binding all interfaces can expose the server to the local network. Materially mitigated here because SSE fails loud without `MCP_API_KEY` and every request needs a constant-time-compared bearer token plus a rate limit — an unauthenticated neighbour gets 401. The residual gap was binding hygiene / defence-in-depth.",
        remediation="Default is now `MCP_HOST` env with fallback `127.0.0.1`; `compose.yaml` sets `MCP_HOST=0.0.0.0` explicitly (container networking is isolated). Docker smoke test unaffected.",
    ),
    "SCALE-006": dict(
        sev="medium",
        title="Per-container resource limits",
        status="closed — remediated 2026-07-20",
        effort="S",
        observed="`compose.yaml` set read_only / cap_drop ALL / no-new-privileges but no memory, CPU or PID limits.",
        expected="Explicit resource limits to bound blast radius and prevent noisy-neighbour exhaustion.",
        risk="Without limits a runaway or abused process could exhaust host memory/CPU/FDs.",
        remediation="Added `mem_limit: 256m`, `cpus: 0.5`, `pids_limit: 128` to `compose.yaml` (honoured by `docker compose up` v2).",
    ),
    "ARCH-008": dict(
        sev="medium",
        title="Three primitives: Tools, Resources, Prompts",
        status="accepted-risk",
        effort="M",
        observed="Only the Tools primitive is exposed; no Resources or Prompts, and no explicit rationale documented.",
        expected="At least one Resource/Prompt, or a documented rationale for a tools-only design.",
        risk="Read-only, addressable content (e.g. the rubric taxonomy) could be a Resource; agents lose a discovery affordance. Low impact for this server's search-oriented use.",
        remediation="Accepted for 0.1.x. Every tool is parameterised (language/format/class) and thus a poor fit for static Resource URIs; the fail-closed taxonomy is already exposed via `list_rubrics`. Candidate for a documented rationale or a `rubric://` Resource in a later minor.",
    ),
    "ARCH-012": dict(
        sev="medium",
        title="protocolVersion pinning",
        status="accepted-risk",
        effort="S",
        observed="No `protocolVersion` pin; the FastMCP default negotiation is used. CHANGELOG and Dependabot are present.",
        expected="An explicit, tested spec-version pin plus SDK-update discipline.",
        risk="A future SDK bump could silently change the negotiated protocol version. Low, given pinned deps + Dependabot + CI across 3.11–3.13.",
        remediation="Accepted for 0.1.x. FastMCP negotiates the version and does not expose a stable pin kwarg in the pinned SDK; revisit when the SDK exposes one.",
    ),
    "SDK-002": dict(
        sev="medium",
        title="Structured tool return types",
        status="accepted-risk",
        effort="M",
        observed="Tools return `str` (rendered Markdown), with `response_format='json'` offering a structured alternative.",
        expected="Pydantic/TypedDict/Dataclass return types for machine-consumable structure.",
        risk="Markdown-first returns are less directly machine-parseable. Deliberate: the primary consumer is an LLM reading official-gazette prose, and JSON output is available on request.",
        remediation="Accepted as a design choice. The dual Markdown/JSON envelope already carries `provenance`/attribution; a typed model could back the JSON branch in a later minor.",
    ),
    "SDK-003": dict(
        sev="medium",
        title="Context injection for progress/logging",
        status="accepted-risk",
        effort="M",
        observed="Tools do not take `ctx: Context`; per-call latency/status is emitted by the `logged_tool` decorator and structured logger instead.",
        expected="`ctx: Context` injection for progress reports and MCP-native logging.",
        risk="No client-visible progress events. Low impact: each tool is a single fast upstream call, not a long-running job.",
        remediation="Accepted for 0.1.x. Structured JSON logging already covers observability; `ctx` progress can be added if a long-running tool is introduced.",
    ),
}

TEMPLATE = """## Finding: {id} — {title}

**Severity:** {sev}
**Status:** {status}
**Server:** amtsblatt-mcp
**Check-Reference:** {id}

### Observed Behavior
{observed}

### Expected Behavior
{expected}

### Risk Description
{risk}

### Remediation
{remediation}

### Effort Estimate
{effort}
"""

for cid, f in FINDINGS.items():
    path = os.path.join(D, "findings", f"{cid}.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(TEMPLATE.format(id=cid, **f))
print(f"wrote {len(FINDINGS)} finding docs")
