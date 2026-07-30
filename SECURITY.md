# Security Policy

[🇩🇪 Deutsche Version](SECURITY.de.md)

## Audit posture

This server is audited against the internal MCP best-practice catalogue (the
portfolio `mcp-audit` methodology, 68 checks / 8 categories, catalogue hash
`091f446b…`). The latest measured run
(`audits/2026-07-30T105205-Z-amtsblatt-mcp/`) scored **33 pass / 7 partial /
6 fail** across 46 applicable checks — **not production-ready**.

Trend against the identical applicable set: 20/18/8 → 21/18/7 → 32/8/6 →
32/8/6 → **33/7/6**.

**One check moved across three releases, and the reason is the finding worth
reading.** `ARCH-011` closed in 0.21.0: `server.py` went from 2477 lines to 252,
the tool handlers live in `tools/`, and `tool-hashes.json` is byte-identical
afterwards — the surface a client approves provably did not move.

**`ARCH-003` — measured `partial` at 0.21.0, closed in 0.22.0, not yet
re-measured.** The re-audit found that the 0.20.0 decision to decline criterion 1
was justified with rubrics this server does not serve: it named bankruptcy
notices, debt-collection summonses, estate calls and construction objections,
and `KK`, `SB`, `SR`, `LS`, `NA`, `ES`, `TE-*`, `GB-*`, `GE-*` and `BP-*` are all
red and unreachable. The green allow-list exists to exclude exactly those, so the
searchable set is the *non-sensitive* one — the set criterion 1 applies to.

0.22.0 closes it without taking on the hazard the original decision was reaching
for. An empty result now offers shorter forms of the caller's own keyword and the
server never queries them, so the criterion is met while no notice can be
attributed to a term the caller did not choose. Details in the section below.

**`SEC-022` stays `partial` as expected**, on the namespace criterion alone: the
prefix is `gazette_`, not `amtsblatt_mcp__<tool>`. Five of six criteria pass, the
deviation is deliberate, and renaming six published tools is a breaking change.

**The 0.18.0 transport work moved no check, and that is the honest result.**
Serving streamable-http on `/mcp` improved the posture — `SEC-009` gained
server-side session invalidation (`DELETE /mcp` is handled; on `/sse` it was
405), and `MCP_STATELESS=1` became available at all — but neither is what the
two checks ask for. `SEC-009` wants a session *bound* to a validated user id and
`SCALE-002` wants sticky routing or shared session state; absence of sessions is
neither. One of six `SEC-009` criteria is now met, up from zero on the default
transport, which is not enough to leave `fail`.

Recorded this way on purpose: a release that improves security without improving
a score is the case where the temptation to re-grade is strongest.

That run closed a long gap between what was measured and what was true. The
previous measurement predated five releases; every number quoted in between was
a derivation, and the estimate recorded at the time — ~32 pass / 8 partial / 6
fail — turned out exact. The six remaining fails are unchanged in character:
none is a code change waiting to be written.

`SDK-004` closed in 0.8.0 and is confirmed by this run. The server is
cloud-deployed over HTTP and carried no CORS layer, so `Mcp-Session-Id` was
neither exposed nor accepted and a browser-based MCP client lost its session
immediately after initialize. `_cors.py` names the header in both directions and
is added *last*, so it runs *first* — a browser never sends `Authorization` on a
preflight, and with the bearer gate ahead of CORS every preflight would have
answered 401. CORS short-circuits preflights only; GET and POST without the key
still return 401, and a test asserts it. Origins are fail-closed:
`MCP_CORS_ORIGINS` is unset by default.

**Five checks block production, measured on 2026-07-30:** `SCALE-002`,
`SCALE-003`, `SEC-002`, `SEC-003` and `SEC-009`. `SCALE-002` and `SEC-009` are
accepted risks (see below) but stay recorded as `fail`, because an accepted risk
is a decision, not a passing check. `SEC-002` and `SEC-003` need an identity
provider; `SCALE-003` needs an edge load balancer.

`OPS-001` and `OPS-003` were in the blocking set two runs ago and are confirmed
closed. Everything below that this document described as "closed, not yet
re-measured" has been measured since the 2026-07-29 run.

`SEC-021` was the third at the time of the run and is **closed in 0.9.0, not
yet re-measured.** `ALLOWED_HOSTS` was overridable at runtime through
`MCP_ALLOWED_HOSTS`, and an override *replaced* the default set rather than
extending it. The check requires the code-layer allow-list to be
non-config-mutable precisely so a misconfigured deployment cannot redirect
egress wholesale. It is now a literal `frozenset` with no override, matching the
sister server.

Removing it cost nothing real: `GAZETTE_BASE` is a hardcoded constant, so
nothing here ever builds a URL for another host — adding one to the allow-list
could never have caused a request to go there. The override's only reachable
effects were widening what a followed redirect may reach, and disabling the
server outright if an override omitted the gazette host.

**Closed in 0.10.0, not yet re-measured.** `OPS-003` (Phase 1 declared in both
READMEs, `ROADMAP.md` written), `SEC-013` (`docs/secret-management.md`),
`CH-004` (attribution names the licence position, not just the operator),
`SCALE-004` (a `HEALTHCHECK` using a bare TCP connect, since every HTTP path is
behind the bearer gate and would answer 401) and `SCALE-006` (requests/limits
split plus a raised FD limit). `SEC-004` improved but stays `partial`: HTTPS is
now enforced before egress, while the resolved-IP blocklist and DNS pinning
remain open.

**`OPS-001` — closed in 0.12.0, not yet re-measured.** Every tool now has 6+ unit
tests and at least one live test, all live tests are consolidated in
`tests/test_live.py`, and a nightly CI job runs them. The live suite immediately
surfaced a real bug the mocked suite could not see: the pooled client outlived
the per-test event loop.

**`OBS-006` — closed in 0.13.0** (a root span per tool call) and **`ARCH-002` —
closed in 0.14.0** (use-case tags on every tool), likewise not re-measured.

**`OBS-001` — as closed in 0.16.0 as this repo can close it.** The gap was that
nothing tested the protocol-error path against the execution-error path; every
existing test awaited the tool functions directly, where `isError` is not
observable. `tests/test_error_paths.py` drives a real `ClientSession` instead.

It also fixed a real hole rather than only measuring one. Every tool returns
`str` (`SDK-002`), so a client has no typed field to read — and the failure
paths returned a bare German sentence with no footer at all, while every
successful answer ended in `_provenance: live_api_`. The only way to tell "the
source is down" from "nothing matched" was to parse prose. All three outcomes
now carry the marker: `live_api`, `refused` (declined by design; retrying
changes nothing) and `degraded` (the source could not be reached; the same call
may work later). The attribution rides along, which the licence wanted anyway.

At the time that was written the check still could not pass: the lowlevel SDK
emitted protocol-error **code 0**, not the `-32601` the check asks for, though
`mcp.types` defined the constant. Two tests asserted that gap so an SDK fix would
arrive as a failing test rather than as a surprise. **It did — see 0.17.0.**

**`OBS-001` criterion 3 met in 0.17.0, not yet re-measured.** The migration to
`mcp` 2.x made the two pinned tests fail, exactly as they were written to. Under
2.0 a protocol error carries a real JSON-RPC code: `resources/read` on a missing
resource answers `-32602` (INVALID_PARAMS), `prompts/get` answers `-32603`. The
spec made the same correction from the other side — `2026-07-28` moved
resource-not-found from `-32002` to `-32602` and reserved `-32020`…`-32099` for
MCP.

One deviation stays pinned, unchanged by the migration: an unknown **tool** is
still delivered as a tool result with `is_error` rather than as a protocol error.
`OBS-002` is unchanged too — `mask_error_details` does not exist in 2.0 either.
One detail improved: `prompts/get` used to echo the raw `ValueError` and now
answers "Internal server error", keeping the detail server-side.

**What the `2026-07-28` spec does to `SEC-009`, `SCALE-002` and `SCALE-003`.**
All three are about sessions, and the spec **removes protocol-level sessions
entirely** — no `initialize` handshake, no `Mcp-Session-Id`, no SSE stream
resumability. Servers needing cross-call state are told to mint explicit handles
and pass them as tool arguments. This server keeps no cross-call state.

That does not make the findings pass, and the reason is worth stating plainly:
the audit catalogue still scores them against a protocol that had sessions. What
changes is their *character* — from "controls this server has not implemented"
toward "controls the protocol no longer defines". They stay `fail` until the
catalogue catches up, because reclassifying a finding on our own authority is
exactly the drift these documents exist to prevent.

**That exposure was larger here than for the sister server, and 0.18.0 reduced
it.** SSE was this server's only HTTP transport, and spec `2026-07-28`
reclassifies HTTP+SSE as Deprecated with a twelve-month removal window. The
server now serves **streamable-http on `/mcp`** by default; `MCP_TRANSPORT=sse`
still works, still carries the full middleware stack, and logs a warning naming
the deadline.

Both transports are built through one function, so the bearer gate, the rate
limit and the CORS layer are identical on each — a control that held on one and
not the other would look enforced while not being. `tests/test_cors.py` is
parametrised over both for the same reason. `_cors.py` was re-verified against
the `starlette` 1.3.1 that `mcp` 2.0 pulls in (preflight 200, `Mcp-Session-Id`
allowed and exposed, `DELETE` allowed).

What is left is removing SSE, and that is a deployment question rather than a
code one: every client config pointing at `/sse` has to move to `/mcp` first.
`ROADMAP.md` tracks it.

None of the five blocking checks is a code change waiting to be written — see
below and `ROADMAP.md`. The remaining seven `partial` findings are led by
`SDK-002` (deliberate, `str` returns) and `SEC-022` (namespace wording only).
`ARCH-011` closed in 0.21.0; `ARCH-003` closed in 0.22.0, so the next run should
measure 34/6/6 — recorded as an expectation, not as a result.

**`ARCH-011` — closed in 0.21.0, not yet re-measured.** `server.py` was 2477
lines holding the HTTP plumbing, XML parsing, taxonomy cache, input models and
all six tool handlers. It is now 252 lines and does one thing: import `tools` so
the handlers register, then own transport selection and the entrypoint. The
domain code lives in `constants`, `_http`, `_taxonomy`, `_normalise`, `_xml`,
`_envelope`, `inputs` and `tools/`.

The refactor is claimed to be behaviour-preserving and there is real evidence
for that rather than an assurance: **`tool-hashes.json` did not change.** All six
tool fingerprints are byte-identical afterwards, so the surface a client approves
— names, descriptions, schemas, annotations — provably did not move. That is the
`SEC-022` guard from 0.19.0 doing work it was not built for.

It did introduce one bug, worth recording because of how it hid. `tools/status.py`
was extracted with `from .._taxonomy import _rubrics_cache`, which binds the
value once at import, so the status tool would have reported the taxonomy cache
as never loaded regardless of state. The entire suite stayed green: every test
that seeds that cache seeds it for the *search* path, which reads the global
through its own module. It was found by reading the extracted code, not by a
failing test. The cache is now reached through a function, and a test asserts a
seeded cache renders an age — restoring the value-import fails exactly that test.

**`SEC-022` — the substantive half closed in 0.19.0, not yet re-measured.**
`tool-hashes.json` publishes a SHA-256 fingerprint of every tool's name,
description, schemas and annotations, plus a `surface_sha256` over the whole set
so adding or removing a tool is visible even when no surviving tool changed.

The threat is a rug pull: harmless descriptions at approval time, rewritten
afterwards to carry instructions the model follows. The host-side half of the
defence is not ours to build; publishing a fingerprint a host or reviewer can
compare against is. `tests/test_tool_hashes.py` fails until the committed
snapshot matches the live server, so refreshing it is something CI requires
rather than something a maintainer is meant to remember — a snapshot on the
honour system drifts, and a stale fingerprint is worse than none because it
asserts the surface has not moved while it has.

`title`, `icons` and `meta` are excluded deliberately: a fingerprint that churns
on cosmetic edits trains people to regenerate without reading the diff. There is
a negative-control test for that, and another asserting that a `read_only_hint`
flip *does* move the hash — that is a rug pull with no description edit at all.

The namespace criterion asks literally for `<server>__<tool>`; this server uses
`gazette_`, which is consistent, frozen in code and enforced by
`test_tool_naming.py`. It already serves the intent — it is what keeps
`source_status` from colliding with the sister server. Renaming six published
tools a second time, which the check notes is a breaking change requiring a
major bump, buys the literal form of a criterion whose purpose is met. Recorded
as a deliberate deviation rather than done, so the check will stay `partial`.

Full report and per-finding documents: `audits/`.

## Accepted risks, stated precisely

### Session-to-user binding (SEC-009)

**Status:** unreachable as specified. Severity in the catalogue: `critical`.

The check asks that a session id be cryptographically bound to a **user id taken
from a validated OAuth token's `sub` claim**. This server authenticates with a
single shared bearer key, which identifies the *deployment*, not a user. There is
no `sub` claim, so there is nothing to bind a session to. This is not an effort
question — the input the control needs does not exist.

| Criterion | State |
|---|---|
| Session id entropy ≥128 bit | `uuid4().hex` from the SDK — 122 random bits, marginally short, and not ours to set |
| User id from a validated token | Impossible — a shared key carries no identity |
| Session bound to user id | Impossible — same reason |
| 401/403 on mismatch | Not applicable — no user to mismatch |
| Explicit TTL | Not settable: `session_idle_timeout` exists on `StreamableHTTPSessionManager` but `MCPServer` passes it through neither `Settings` nor `streamable_http_app()` (re-verified against `mcp` 2.0.0 — the major version did not change this) |
| Server-side invalidation | Partial — the legacy SSE transport this server serves has no `DELETE` session-termination endpoint |

**Closing it properly** means an OAuth/OIDC provider, which would also unblock
`SEC-002` and `SEC-003`. That is a product decision about whether this server
should have users, not a remediation task. What bounds the exposure meanwhile:
the server is read-only, serves only public gazette data, and the green
allow-list means no session can reach person-data rubrics regardless of who
holds it.

### Stateful load balancing (SCALE-002, SCALE-003)

**Status:** documented, not implemented. Severity in the catalogue: `high`.

The SDK keeps sessions in process memory, so two instances behind a round-robin
balancer break clients: `initialize` lands on one instance and the next call on
another that has never heard of the session.

[`docs/load-balancing.md`](docs/load-balancing.md) now carries tested nginx and
Kubernetes Ingress configurations keyed on the `Mcp-Session-Id` header, with the
buffering and timeout settings the long-lived SSE transport needs, and an honest
failover statement: **affinity prevents misrouting, not loss.** If the instance
holding a session dies, the session dies with it.

Two criteria remain unmet, which is why this is not recorded as passing:

- **No explicit session TTL** — not settable through `MCPServer`, see above.
- **No shared-state session manager** — that needs replacing the SDK's in-process
  manager, which the server object does not expose as an extension point, plus a Redis
  dependency this server does not have.

**`MCP_STATELESS=1` is available since 0.18.0**, and this paragraph used to say
the opposite. It was accurate when written: SSE was the only HTTP transport here
and has no stateless mode, so gaining the option meant migrating to
streamable-http — a deliberate change to a cloud-deployed service rather than a
remediation step. That migration has now happened.

With `MCP_TRANSPORT=streamable-http MCP_STATELESS=1` the server tracks no session
at all. Session hijacking and session affinity stop being risks to mitigate and
become states that cannot occur. Neither check flips to `pass`: `SEC-009` asks
for *binding* and `SCALE-002` for *routing*, and absence is neither. But the
exposure each describes is gone while it is enabled, which is worth more than the
score.

It is opt-in rather than the default, because it is not free — a stateless server
cannot resume an interrupted stream or deliver server-initiated notifications.
This server keeps no cross-call state, so the trade is usually right; the
operator decides. On `MCP_TRANSPORT=sse` the flag is ignored, deliberately:
leaving it apparently in effect would tell an operator they run session-free when
they do not.

### Suggestions, not silent widening (ARCH-003)

`ARCH-003` asks that empty search results trigger a fuzzy **or suggestion**
mechanism on the non-sensitive search tools, and that any tool which stays
exact-only says so.

**This section was wrong until 0.22.0 and the correction matters.** It claimed
this server has no non-sensitive search tool, because all three searches query
"bankruptcy notices, debt-collection summonses, estate calls, construction
objections". Every rubric in that list is **red** and unreachable through any
tool: `KK`, `SB`, `SR`, `LS`, `NA` (Konkurse, Schuldbetreibungen), `ES` / `TE-*`
(Erbschaft), `GB-*` / `GE-*` (gerichtliche Vorladungen) and `BP-*` (Baugesuche)
all sit outside `GREEN_RUBRICS` — an allow-list that exists precisely to exclude
systematic natural-person data. The searchable set is therefore the
*non-sensitive* one, and the exemption being claimed covered rubrics this server
refuses to serve. The 2026-07-30 re-audit recorded `ARCH-003` as still `partial`
on exactly that basis.

**What survives from the original reasoning is narrower and real.** `HR` / `BH`
(Handelsregister) and `OB-*` (Beschaffungen) name legal persons, so silently
re-running a search with a broadened company name would return notices about
*different* companies and present them as the answer to the original question.

Both are now held at once. On `match_type == "none"` the response offers shorter
forms of the caller's *own* keyword — `Schulhausneubau` → `Schulhaus`, `Schul` —
and the server **never queries them**. The model chooses. No request is issued
for a suggestion, so no notice can be attributed to a term the caller did not
pick, and `MatchType` still has no `fuzzy` member because no response is ever a
fuzzy match. Suggestions below four characters are dropped: a prefix that short
matches half the gazette, and `AG` is not a search term.

Two tests hold the pair — one that suggestions appear, one that they are never
searched. Dropping either leaves the other meaningless.

The companion server (`swiss-procurement-mcp`) goes further and actually widens
its *taxonomy* lookups, because a CPV code is a closed set with no person
attached; its tender searches stay exact-only.

What replaces widening is an empty result that explains itself. Beyond naming
the filters that were applied, it points at two things a caller cannot see from
outside:

- **The scope gate.** Searches run against the green rubrics only, so a keyword
  that genuinely appears in the gazette can come back empty because its rubric
  is deliberately not served. The note points at
  `gazette_list_rubrics(rubric_class='all')`, which distinguishes "no such
  publication" from "not served here" — different claims, and only the second
  one is this server's own doing.
- **Upstream health.** A degraded source and an empty result are
  indistinguishable at this layer, so the note points at
  `gazette_source_status`.

Every response carries `match_type` (`exact` or `none`) — in the JSON payload
and in the rendered Markdown meta line, since these tools return text and
anything not in the text does not reach the model.

## Supported Versions

| Version | Supported |
|---|---|
| `main` | ✅ |
| `0.1.x` | ✅ |
| `< 0.1` | ❌ |

## Reporting a Vulnerability

Please report privately via a
[GitHub Security Advisory](https://github.com/malkreide/amtsblatt-mcp/security/advisories/new)
rather than a public issue.

Include if possible: affected version, reproduction steps, the tool call or
request involved, and the impact you observed.

## Response Targets

- Acknowledgement: 5 working days
- Initial triage: 10 working days

## Scope

**In scope:** the published package, the Docker image, the GitHub workflows,
the green allow-list enforcement, the egress allow-list, and the SSE auth and
rate-limit middleware.

**Out of scope:** the behaviour of amtsblattportal.ch itself; forks with the
allow-list or authentication removed; findings in dependencies without a
demonstrated impact on this server.

## Data-protection findings are security findings

A defect that lets a blocked rubric be queried — or that leaks content from a
blocked rubric into a response — is a **vulnerability**, not a bug report.
Please use the private advisory channel for it. Concretely, report any of:

- A rubric outside `GREEN_RUBRICS` reaching the upstream query string.
- `gazette_get_publication` rendering content from a rubric that is not green.
- A tool signature accepting a person-identifying parameter.
- A refusal message that discloses a circumvention.

## Hardening Notes for Operators

1. **Put a gateway in front of whichever HTTP transport you serve.** This
   applies to streamable-http on `/mcp` (the default since 0.18.0) exactly as
   much as to the legacy `/sse` path: the built-in bearer auth and rate limit
   are single-instance only on both, and the rate-limit buckets are held in
   process memory and are not shared or garbage-collected across instances. The
   advice used to name only SSE, which read as though it did not apply to
   operators on the default transport.
2. **Restrict egress at the network layer too.** `ALLOWED_HOSTS` is a
   defence-in-depth measure inside the process, not a substitute for an egress
   firewall. It is a literal `frozenset` in `server.py` with no environment
   override (SEC-021) — changing it is a code change, deliberately.
3. **Rotate `MCP_API_KEY`** and never bake it into an image.
4. **Ship the JSON logs to your SIEM** and alert on `auth_failed`,
   `rate_limited`, `egress_denied`, `green_gate_violation` and
   `blocked_publication_requested`. The last two mean something tried to reach a
   rubric the server does not serve.
5. **Do not persist responses.** Publications carry statutory deletion periods;
   the server deliberately keeps no content cache, and downstream storage would
   undo that.

---

## Lethal-trifecta assessment (SEC-019)

The "lethal trifecta" is the dangerous combination of (1) access to private
data, (2) exposure to untrusted content, and (3) the ability to exfiltrate. A
server holding all three can be steered by injected content into reading
something sensitive and sending it somewhere. This server is assessed leg by
leg rather than declared safe.

| Leg | Present? | Why |
|---|---|---|
| Access to private / sensitive data | **No, by construction** | The gazette *corpus* contains personal data — bankruptcies, debt enforcement, inheritance, civil status, court summonses, building applications. None of it is reachable: those rubrics are not indexed, and a request for one returns an explanation instead of data. The green allow-list is enforced before the request and re-checked after the fetch. |
| Exposure to untrusted content | **Partial** | Tool results contain upstream publication text, which the model ingests. It is official gazette text published by Swiss authorities, not attacker-chosen private content — but it is not authored by us, so it is treated as untrusted input. |
| Ability to exfiltrate | **No** | Egress is restricted to `amtsblattportal.ch` by a `frozenset` allow-list checked before every request (`EgressDenied`). No write endpoints are wrapped, no filesystem tool exists, and no user-controlled value reaches the host component of a URL. |

**At most one leg is present, and it is the weakest one.** Injected text in a
publication could at worst influence the model's summary of that publication;
it has nowhere to send anything and nothing sensitive to read.

### What would change this assessment

Each of these would need a fresh assessment before shipping:

- Indexing any red rubric, or relaxing the post-fetch green gate — that turns
  leg 1 on.
- Adding a second upstream host, or letting any user input reach a URL host —
  that turns leg 3 on.
- Adding a write, filesystem or email tool — leg 3 outright.
- Adding sampling (`ctx.sample`), which would let upstream text steer a
  model call rather than only be summarised by one.

### Relationship to the companion server

`swiss-procurement-mcp` carries the same assessment with one difference: it has
no personal-data rubrics to exclude in the first place, so its leg 1 is absent
by nature rather than by an enforced allow-list. Here the allow-list *is* the
control, which is why `tests/test_allowlist.py` runs as its own CI job.
