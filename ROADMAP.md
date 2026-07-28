# Roadmap (OPS-003)

Phase model from the portfolio standard: **read-only first, then write, then
multi-agent.** A phase is not a plan, it is a claim about what the server is
allowed to do — so the current phase is stated in `README.md` and every tool
annotation must agree with it.

## Current phase: 1 — read-only

All six tools are `readOnlyHint: True`, `destructiveHint: False`,
`openWorldHint: True`. The server wraps only read endpoints of
amtsblattportal.ch. There is no write path and none is planned.

The scope restriction that matters most here is not the phase but the **green
allow-list**: rubrics carrying systematic natural-person data (bankruptcies,
debt enforcement, inheritance calls, civil status, court summonses, building
applications) are not queryable, and no person-name parameter exists in any
tool. That is a data-protection decision enforced in code and re-checked after
every fetch — see `SECURITY.md`. It does not change with phase.

## Phase 1 — open work

Ordered by value, not severity. Audit ids refer to the `mcp-audit` catalogue;
the current run lives under `audits/`.

| Item | Check | State |
|---|---|---|
| Raise per-tool test coverage to the floor: `gazette_list_rubrics` (2 unit tests), `gazette_source_status` (3), and live tests for the three tools that have none | `OPS-001` | open — highest value item here |
| Separate nightly/manual live-test workflow, as the sister server has | `OPS-001` | open |
| Resolved-IP blocklist for private, loopback, link-local and `169.254.169.254` | `SEC-004` | open |
| DNS pinning so the resolved IP is the one connected to | `SEC-005` | open |
| Per-tool-call OTel span carrying `mcp.tool.name` and `mcp.tool.result.is_error` — today only httpx client spans exist, so a tool call has no root span | `OBS-006` | open |
| `<use_case>` tags on all tool descriptions | `ARCH-002` | open |
| Split `server.py` (~2200 lines) into a `tools/` package | `ARCH-011` | open — refactor with regression risk, low payoff |
| Structured tool returns instead of rendered Markdown | `SDK-002` | **not planned** — deliberate, see below |
| Progress reporting via `ctx: Context` | `SDK-003` | not planned while every tool returns in milliseconds |

**`SDK-002` is an accepted deviation, not a backlog item.** Tools return `str`
because the rendered output is composed for a reader and carries provenance,
the `green_rubrics_only` scope note, the dedup warning and the explanation of a
blocked rubric. That is prose, not fields. Machine-readable callers are served
by the `json` format. It stays `partial` in every audit by choice.

## Not roadmap items — blocked on infrastructure, not code

These are recorded as `fail` and will stay that way until the deployment model
changes. Writing them down here is the point: otherwise they read as neglect.

| Check | What it actually needs |
|---|---|
| `SEC-009` | A session layer bound to an authenticated identity. Accepted risk, see `SECURITY.md`. |
| `SCALE-002`, `SCALE-003` | Sticky sessions or shared session state at an edge load balancer. Accepted risk. |
| `SEC-002`, `SEC-003` | A real identity provider issuing scoped tokens. The server holds a single static bearer key; `aud`/`iss` validation and a scope hierarchy are not implementable against it. |
| `SEC-014`, `SEC-015` | An MCP gateway in front of the server for tool allow-listing and pre-flight poisoning detection. None is deployed. |

## What Phase 1 → 2 would require

Not planned; this server has no plausible write surface. Recorded so the bar is
written down:

- An audit run with no open `critical` or `high` findings that are not accepted
  risks
- ISDS and a DSG processing-activity record
- Re-evaluation of the lethal-trifecta assessment in `SECURITY.md` — a write or
  send capability turns the exfiltration leg on, and the current assessment
  depends on it being off
- Sign-off from the data protection officer, given the corpus this server
  deliberately does not index

## Phase 2 → 3

Out of scope.
