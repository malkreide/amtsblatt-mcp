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
| Split `server.py` (~2200 lines) into a `tools/` package | `ARCH-011` | open — refactor with regression risk, low payoff |
| Remove the deprecated HTTP+SSE transport entirely | — | open — streamable-http shipped in 0.18.0, SSE kept for the deprecation window |
| Structured tool returns instead of rendered Markdown | `SDK-002` | **not planned** — deliberate, see below |
| Progress reporting via `ctx: Context` | `SDK-003` | not planned while every tool returns in milliseconds |

Closed since the last audit run, and therefore still listed as `fail`/`partial`
there: `OPS-001` (per-tool test floor plus the nightly live job in `ci.yml`),
`SEC-004` and `SEC-005` (`_net.py`, `tests/test_ssrf.py`), `OBS-006` (root span
per tool call in `_otel.py`) and `ARCH-002` (`<use_case>` on all six tools). The
audit under `audits/` is a measurement, not a status board — it will keep saying
so until it is re-run.

**`OBS-001` is closed as far as this repo reaches.** `tests/test_error_paths.py`
drives a real `ClientSession` and asserts the paths apart. Because every tool
returns `str` (see `SDK-002`), there is no typed field for a client to inspect,
so the outcome rides in the footer instead: `live_api`, `refused` (this server
declined by design — retrying changes nothing) or `degraded` (the source could
not be reached — the same call may work later). Refusals and outages used to
return a bare German sentence carrying neither provenance nor the attribution
the licence requires; now they wear the same envelope as a result.

**The blocked criterion cleared in 0.17.0.** Under `mcp` 1.x the lowlevel server
emitted error **code 0** rather than the `-32601` the check asks for, and two
tests pinned that so the day the SDK fixed it the suite would say so. The
migration to `mcp` 2.x made them fail; they are now assertions that a protocol
error carries `-32602` / `-32603`. What remains open is not a code change: an
unknown *tool* is still delivered as a tool result rather than a protocol error.

**Streamable-http shipped in 0.18.0; removing SSE is what is left.** Spec
`2026-07-28` reclassifies HTTP+SSE as Deprecated under a twelve-month removal
window and removes protocol-level sessions outright. This server now serves
`/mcp` by default and keeps `/sse` + `/messages` working behind
`MCP_TRANSPORT=sse`, which logs a warning naming the deadline.

Both transports carry the identical middleware stack — bearer gate, rate limit,
CORS — built through one function, because a control that holds on one transport
and not the other is worse than a missing one.

What remains is the removal itself, and it is a deployment question rather than a
code one: every client config pointing at `/sse` has to move to `/mcp` first.
The warning in the logs is what makes that visible; the deadline is the spec's,
not ours.

**`MCP_STATELESS` became reachable in the same release.** It was previously
recorded here as unavailable, correctly: SSE has no stateless mode. On
streamable-http it removes session hijacking and session affinity as questions
rather than answering them, which is the strongest available response to
`SEC-009` and `SCALE-002`. Neither check flips to `pass` — both ask for binding
and routing, not absence — but the exposure is gone when it is enabled.

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
