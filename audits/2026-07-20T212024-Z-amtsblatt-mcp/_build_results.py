"""Assemble verification-results.json from the audit status map + catalog metadata."""

import json
import sys

catalog = json.load(open(sys.argv[1]))  # parse_catalog --format json (dict keyed by id)
out_path = sys.argv[2]

# status, evidence, gaps per applicable check (as-found, pre-remediation)
STATUS = {
    "ARCH-001": (
        "pass",
        [
            "5 snake_case tools: search_publications, search_procurement, get_publication, list_rubrics, source_status (server.py:983,1128,1252,1366,1505)"
        ],
        [],
    ),
    "ARCH-002": (
        "pass",
        [
            "Rich multi-paragraph German docstrings per tool + FastMCP instructions block (server.py:727)"
        ],
        [],
    ),
    "ARCH-003": (
        "pass",
        [
            "Blocked rubric -> explanation; unreachable -> explicit error not empty; procurement no-canton -> simap explainer (server.py:964,1101,1559)"
        ],
        [],
    ),
    "ARCH-004": (
        "pass",
        ["Tools take Pydantic input models only; no request/websocket/stdin access in handlers"],
        [],
    ),
    "ARCH-005": (
        "pass",
        ["MCP_API_KEY read from env (server.py:1584); no hardcoded secrets (grep clean)"],
        [],
    ),
    "ARCH-006": ("pass", ["5 tools, well under the 8-tool heuristic"], []),
    "ARCH-007": (
        "pass",
        ["get_publication aggregates fetch+parse+gate; external calls stay atomic"],
        [],
    ),
    "ARCH-008": (
        "partial",
        ["Only the Tools primitive is exposed"],
        [
            "No Resources or Prompts; read-only list_rubrics/source_status could be Resources; no documented rationale for tools-only"
        ],
    ),
    "ARCH-009": (
        "pass",
        [
            "All 5 tools set readOnlyHint/destructiveHint/idempotentHint/openWorldHint (server.py:985,1130,1254,1368,1507)"
        ],
        [],
    ),
    "ARCH-011": (
        "pass",
        [
            "README.md, README.de.md, CHANGELOG.md, LICENSE, pyproject.toml present; src/ tests/ .github/workflows/ present; ci.yml + publish.yml"
        ],
        [],
    ),
    "ARCH-012": (
        "partial",
        ["CHANGELOG present; Dependabot configured (.github/dependabot.yml)"],
        [
            "No protocolVersion pin anywhere (FastMCP default used); grep for protocolVersion returns nothing"
        ],
    ),
    "CH-004": (
        "pass",
        ["ATTRIBUTION footer on every response (server.py:56,672,681); source credited in README"],
        [],
    ),
    "OBS-001": (
        "pass",
        [
            "Tools return explanatory strings; _handle_error translates exceptions; tools never raise protocol errors (server.py:685)"
        ],
        [],
    ),
    "OBS-002": (
        "pass",
        ["_handle_error returns clean messages; no stacktraces/SQL leaked to the model"],
        [],
    ),
    "OBS-003": (
        "pass",
        ["Custom _JsonFormatter structured JSON logging with levels + event fields (_log.py:17)"],
        [],
    ),
    "OBS-004": (
        "pass",
        ["logging.StreamHandler(sys.stderr) -> stdout reserved for stdio protocol (_log.py:37)"],
        [],
    ),
    "OBS-006": (
        "pass",
        ["Optional OpenTelemetry via [otel] extra + OTEL_EXPORTER_OTLP_ENDPOINT (_otel.py:18)"],
        [],
    ),
    "OPS-001": (
        "pass",
        [
            "73 unit tests (respx-mocked) + @pytest.mark.live tests; live marker registered in pyproject"
        ],
        [],
    ),
    "OPS-002": (
        "pass",
        ["README.md + README.de.md, ASCII architecture diagram, Known Limitations section"],
        [],
    ),
    "OPS-003": (
        "pass",
        ["All tools readOnlyHint=True; read-only-first scope documented; no write tools"],
        [],
    ),
    "SCALE-001": (
        "pass",
        ["SSE transport for cloud via MCP_TRANSPORT=sse; documented in README"],
        [],
    ),
    "SCALE-002": (
        "pass",
        [
            "In-memory rate limit documented as single-instance; gateway recommended for multi-instance (SECURITY.md)"
        ],
        [],
    ),
    "SCALE-003": (
        "pass",
        ["Multi-instance/session routing documented as a gateway concern (SECURITY.md)"],
        [],
    ),
    "SCALE-004": (
        "pass",
        ["Multi-stage Dockerfile (builder + runtime), non-root USER mcp (Dockerfile:3,19,33)"],
        [],
    ),
    "SCALE-006": (
        "partial",
        ["compose.yaml sets read_only, cap_drop ALL, no-new-privileges"],
        ["No explicit memory/CPU/pids resource limits in compose.yaml"],
    ),
    "SDK-001": (
        "fail",
        [
            "No FastMCP lifespan; a fresh httpx.AsyncClient is created per request via _make_client() in _get_json/_get_text/_probe_endpoint (server.py:247,262,278,1478)"
        ],
        [
            "No connection pooling reuse across calls; new TLS handshake each request; no @asynccontextmanager lifespan"
        ],
    ),
    "SDK-002": (
        "partial",
        ["Pydantic v2 input models; response_format=json provides structured output"],
        ["Tool return type is `str` (rendered Markdown/JSON), not a Pydantic/TypedDict model"],
    ),
    "SDK-003": (
        "partial",
        ["Custom structured logging via logged_tool decorator emits per-call latency/status"],
        ["Tools do not take ctx: Context; no ctx.info/progress reporting"],
    ),
    "SDK-004": (
        "pass",
        [
            "Stateless SSE (mcp.sse_app()); no CORS middleware => no cross-origin Mcp-Session-Id exposure"
        ],
        [],
    ),
    "SEC-002": (
        "pass",
        [
            "Upstream read API is unauthenticated; no client token is forwarded to the upstream (no token passthrough)"
        ],
        [],
    ),
    "SEC-003": ("pass", ["Read-only server, single bearer key, no OAuth scopes to minimise"], []),
    "SEC-004": (
        "pass",
        [
            "Egress allow-list (host-based) + HTTPS base URL; no user-controlled host reaches the client; paths built from validated IDs (server.py:93,226)"
        ],
        [],
    ),
    "SEC-005": (
        "pass",
        ["Egress hook re-checks request.url.host on every hop incl. redirects (server.py:226,255)"],
        [],
    ),
    "SEC-006": (
        "pass",
        ["stdio default for local; SSE only when explicitly configured; documented in README"],
        [],
    ),
    "SEC-007": (
        "pass",
        ["Dockerfile non-root; compose read_only + cap_drop ALL + no-new-privileges"],
        [],
    ),
    "SEC-008": (
        "pass",
        ["PyPI publish via Trusted Publishing (OIDC), no stored token (publish.yml)"],
        [],
    ),
    "SEC-009": (
        "pass",
        ["Stateless server; no app-managed session IDs; bearer token is the auth boundary"],
        [],
    ),
    "SEC-013": (
        "pass",
        [
            "MCP_API_KEY via env (Stufe 1), documented with rotation + no-bake-into-image hardening (SECURITY.md)"
        ],
        [],
    ),
    "SEC-014": (
        "pass",
        ["5 read-only tools; gateway allow-listing documented as a deployment concern"],
        [],
    ),
    "SEC-015": (
        "pass",
        ["Static tool descriptions; no dynamic/remote tool definitions to poison"],
        [],
    ),
    "SEC-018": (
        "pass",
        [
            "Pydantic v2 ConfigDict(extra='forbid'), field validators, regex patterns, min/max bounds on every input model (server.py:757)"
        ],
        [],
    ),
    "SEC-019": (
        "pass",
        ["Read-only by design; no write/send tools => no lethal trifecta; scope documented"],
        [],
    ),
    "SEC-020": ("pass", ["No os.system/subprocess/shell=True/eval/exec anywhere (grep clean)"], []),
    "SEC-021": (
        "pass",
        [
            "ALLOWED_HOSTS frozenset code-layer allow-list enforced on every request + redirect; network-layer restriction documented (server.py:93; SECURITY.md)"
        ],
        [],
    ),
    "SEC-022": (
        "pass",
        ["FastMCP auto-namespace ('amtsblatt_mcp' server); tools namespaced under the server"],
        [],
    ),
    "SEC-016": (
        "partial",
        [
            "SSE binds mcp.settings.host = '0.0.0.0' hardcoded (server.py:748)",
            "Mitigated: SSE fails loud without MCP_API_KEY; every request requires a constant-time-compared bearer token + sliding-window rate limit",
        ],
        [
            "No default 127.0.0.1 bind and no MCP_HOST override; NeighborJack surface reduced but not eliminated by binding hygiene"
        ],
    ),
}

results = {}
for cid, (status, evidence, gaps) in STATUS.items():
    meta = catalog.get(cid, {})
    results[cid] = {
        "status": status,
        "category": meta.get("category", cid.split("-")[0]),
        "severity": meta.get("severity", "medium"),
        "evidence": evidence,
        "gaps": gaps,
    }

doc = {
    "audit_meta": {"server_name": "amtsblatt-mcp", "run_id": "2026-07-20T212024-Z-amtsblatt-mcp"},
    "policy": "fail-or-partial",
    "results": results,
}
json.dump(doc, open(out_path, "w"), indent=2, ensure_ascii=False)
print(f"wrote {len(results)} results to {out_path}")
