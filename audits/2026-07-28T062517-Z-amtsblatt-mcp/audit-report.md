# MCP-Server Audit-Report — `<server>`

**Audit-Datum:** 
**Skill-Version:** ?
**Catalog-Version:** ?

---

## 1. Executive Summary

Server `<server>` wurde gegen 46 anwendbare Best-Practice-Checks geprüft. 20 bestanden, 26 Findings dokumentiert (3 critical, 12 high, 11 medium, 0 low). Production-Readiness: NICHT erreicht — blockierend: OPS-001, OPS-003, SCALE-002, SCALE-003, SDK-004, SEC-003, SEC-009.

**Production-Readiness:** NO

---

## 2. Profil-Snapshot

| Feld | Wert |
|---|---|
| Server-Name | `?` |
| Audit-Datum | ? |
| Skill-Version | ? |
| Catalog-Version | ? |

---

## 3. Applicability

### Status pro Kategorie

| Kategorie | Pass | Fail | Partial | Todo | N/A |
|---|---|---|---|---|---|
| ARCH | 8 | 0 | 3 | 0 | 0 |
| CH | 0 | 0 | 1 | 0 | 0 |
| OBS | 2 | 0 | 3 | 0 | 0 |
| OPS | 0 | 2 | 1 | 0 | 0 |
| SCALE | 1 | 2 | 2 | 0 | 0 |
| SDK | 1 | 1 | 2 | 0 | 0 |
| SEC | 8 | 3 | 6 | 0 | 0 |
| **Total** | **20** | **8** | **18** | **0** | **0** |

---

## 4. Findings-Übersicht

_Policy: `fail-or-partial`_

| ID | Category | Severity | Status |
|---|---|---|---|
| SEC-002 | SEC | critical | partial |
| SEC-004 | SEC | critical | partial |
| SEC-009 | SEC | critical | fail |
| ARCH-004 | ARCH | high | partial |
| OBS-001 | OBS | high | partial |
| OBS-002 | OBS | high | partial |
| OPS-001 | OPS | high | fail |
| OPS-003 | OPS | high | fail |
| SCALE-002 | SCALE | high | fail |
| SCALE-003 | SCALE | high | fail |
| SDK-004 | SDK | high | fail |
| SEC-003 | SEC | high | fail |
| SEC-005 | SEC | high | partial |
| SEC-013 | SEC | high | partial |
| SEC-021 | SEC | high | partial |
| ARCH-002 | ARCH | medium | partial |
| ARCH-011 | ARCH | medium | partial |
| CH-004 | CH | medium | partial |
| OBS-006 | OBS | medium | partial |
| OPS-002 | OPS | medium | partial |
| SCALE-004 | SCALE | medium | partial |
| SCALE-006 | SCALE | medium | partial |
| SDK-002 | SDK | medium | partial |
| SDK-003 | SDK | medium | partial |
| SEC-014 | SEC | medium | partial |
| SEC-015 | SEC | medium | fail |

**Gesamt:** 26 Findings

---

## 5. Detail-Findings

### ARCH-002

## Finding: ARCH-002 — Tool-Beschreibung mit Use-Case-Tags

**Severity:** medium
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** ARCH-002
**Category:** ARCH
**Audit-Run:** 2026-07-28T062517-Z-amtsblatt-mcp

### Observed Behavior

Check status: **partial** (3 evidence points collected).

- Median description length 1243 chars, far above the 100 floor
- Scope caveats stated in the tool descriptions
- gazette_search_publications vs gazette_search_detailed differentiated

### Expected Behavior

All pass criteria of ARCH-002 satisfied. See `checks/ARCH-002` in the mcp-audit catalogue
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- No <use_case> tag in any of 6 tools (0%, >=80% required)

### Evaluator Notes

(none)

### Effort Estimate

S


### ARCH-004

## Finding: ARCH-004 — Inversion of Control: Transport-agnostische Server-Logik

**Severity:** high
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** ARCH-004
**Category:** ARCH
**Audit-Run:** 2026-07-28T062517-Z-amtsblatt-mcp

### Observed Behavior

Check status: **partial** (3 evidence points collected).

- Transport selected by env var, stdio default
- Shared _lifespan across transports (server.py:934)
- Outputs transport-independent

### Expected Behavior

All pass criteria of ARCH-004 satisfied. See `checks/ARCH-004` in the mcp-audit catalogue
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- No tool uses ctx: Context
- Config read via os.environ at module scope, not a Settings object

### Evaluator Notes

(none)

### Effort Estimate

M


### ARCH-011

## Finding: ARCH-011 — Standardisierte Repo-Struktur (src-Layout, tests, README.de.md)

**Severity:** medium
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** ARCH-011
**Category:** ARCH
**Audit-Run:** 2026-07-28T062517-Z-amtsblatt-mcp

### Observed Behavior

Check status: **partial** (4 evidence points collected).

- All mandatory top-level files present
- src/ layout correct
- ci.yml + publish.yml present
- README.de.md parallel

### Expected Behavior

All pass criteria of ARCH-011 satisfied. See `checks/ARCH-011` in the mcp-audit catalogue
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- 6 tools (>5) but no tools/ directory split — server.py is ~2200 lines holding all handlers
- No README justification for the deviation

### Evaluator Notes

(none)

### Effort Estimate

S


### CH-004

## Finding: CH-004 — OGD-CH Lizenz-Compliance: CC BY 4.0 Attribution

**Severity:** medium
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** CH-004
**Category:** CH
**Audit-Run:** 2026-07-28T062517-Z-amtsblatt-mcp

### Observed Behavior

Check status: **partial** (2 evidence points collected).

- Per-record source URL in output (server.py:1287)
- README:461 documents the data source and its terms

### Expected Behavior

All pass criteria of CH-004 satisfied. See `checks/CH-004` in the mcp-audit catalogue
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- Tool responses carry no licence field alongside the source
- README states the MIT code licence but no explicit data licence

### Evaluator Notes

(none)

### Effort Estimate

S


### OBS-001

## Finding: OBS-001 — Protocol vs. Execution Errors: korrekte Trennung

**Severity:** high
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** OBS-001
**Category:** OBS
**Audit-Run:** 2026-07-28T062517-Z-amtsblatt-mcp

### Observed Behavior

Check status: **partial** (2 evidence points collected).

- Upstream failures return explanatory German tool results rather than crashing
- Egress denial produces a specific message (server.py:901)

### Expected Behavior

All pass criteria of OBS-001 satisfied. See `checks/OBS-001` in the mcp-audit catalogue
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- No explicit isError construction or documented -326xx/-320xx protocol codes
- No test distinguishes the protocol-error path from the execution-error path

### Evaluator Notes

(none)

### Effort Estimate

M


### OBS-002

## Finding: OBS-002 — Mask Error Details: keine Stacktraces / SQL ans LLM

**Severity:** high
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** OBS-002
**Category:** OBS
**Audit-Run:** 2026-07-28T062517-Z-amtsblatt-mcp

### Observed Behavior

Check status: **partial** (2 evidence points collected).

- No traceback.format_exc() or sys.exc_info() in src/
- Upstream bodies not echoed to the caller

### Expected Behavior

All pass criteria of OBS-002 satisfied. See `checks/OBS-002` in the mcp-audit catalogue
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- FastMCP constructed without mask_error_details=True (server.py:972)

### Evaluator Notes

(none)

### Effort Estimate

M


### OBS-006

## Finding: OBS-006 — OpenTelemetry Distributed Tracing pro Tool-Call

**Severity:** medium
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** OBS-006
**Category:** OBS
**Audit-Run:** 2026-07-28T062517-Z-amtsblatt-mcp

### Observed Behavior

Check status: **partial** (5 evidence points collected).

- OTel SDK in the otel extra (pyproject.toml:49)
- TracerProvider with OTLP HTTP exporter (_otel.py:27-33)
- HTTPXClientInstrumentor auto-instrumentation active
- OTLP endpoint via OTEL_EXPORTER_OTLP_ENDPOINT
- service.name set (_otel.py:40)

### Expected Behavior

All pass criteria of OBS-006 satisfied. See `checks/OBS-006` in the mcp-audit catalogue
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- No per-tool-call span — mcp.tool.name, mcp.user.id and mcp.tool.result.is_error are never set
- Only HTTP client spans are produced, so a tool call has no root span of its own

### Evaluator Notes

(none)

### Effort Estimate

S


### OPS-001

## Finding: OPS-001 — Test-Strategie: Unit-Tests mocked + Live-Tests gemarkert

**Severity:** high
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** OPS-001
**Category:** OPS
**Audit-Run:** 2026-07-28T062517-Z-amtsblatt-mcp

### Observed Behavior

Check status: **fail** (3 evidence points collected).

- respx used for HTTP mocking
- live marker registered (pyproject.toml:71)
- CI runs pytest -m 'not live' (ci.yml:31)

### Expected Behavior

All pass criteria of OPS-001 satisfied. See `checks/OPS-001` in the mcp-audit catalogue
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- gazette_list_rubrics has only 2 unit tests, below the 5 floor
- Only 3 of 6 tools have a live test — gazette_search_detailed, gazette_get_publication and gazette_list_rubrics have none
- No tests/test_live.py; live tests are scattered across test_search.py and test_publication.py
- No separate nightly or manual live-test workflow

### Evaluator Notes

The sister server closed this finding; the fix was never ported here.

### Effort Estimate

M


### OPS-002

## Finding: OPS-002 — Doku-Standard: bilingualer README, ASCII-Diagramm, Limits-Sektion

**Severity:** medium
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** OPS-002
**Category:** OPS
**Audit-Run:** 2026-07-28T062517-Z-amtsblatt-mcp

### Observed Behavior

Check status: **partial** (5 evidence points collected).

- All 8 mandatory sections present
- Anchor demo query concrete (README:30)
- Mermaid/ASCII diagram present
- Known limitations explicit (README:282)
- CONTRIBUTING bilingual

### Expected Behavior

All pass criteria of OPS-002 satisfied. See `checks/OPS-002` in the mcp-audit catalogue
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- README.de.md has 17 top-level sections against README.md's 19

### Evaluator Notes

(none)

### Effort Estimate

S


### OPS-003

## Finding: OPS-003 — Phasenarchitektur: Read-only First, dann Write, dann Multi-Agent

**Severity:** high
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** OPS-003
**Category:** OPS
**Audit-Run:** 2026-07-28T062517-Z-amtsblatt-mcp

### Observed Behavior

Check status: **fail** (1 evidence points collected).

- Tool annotations are consistently read-only

### Expected Behavior

All pass criteria of OPS-003 satisfied. See `checks/OPS-003` in the mcp-audit catalogue
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- No phase declared anywhere in README.md
- No roadmap file
- No phase-transition preconditions documented

### Evaluator Notes

swiss declares Phase 1; this server declares nothing.

### Effort Estimate

M


### SCALE-002

## Finding: SCALE-002 — Stateful Load Balancing für Streamable HTTP / SSE

**Severity:** high
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** SCALE-002
**Category:** SCALE
**Audit-Run:** 2026-07-28T062517-Z-amtsblatt-mcp

### Observed Behavior

Check status: **fail** (1 evidence points collected).

- No sticky-session or shared-state session manager

### Expected Behavior

All pass criteria of SCALE-002 satisfied. See `checks/SCALE-002` in the mcp-audit catalogue
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- Neither pattern implemented
- No session TTL
- No failover test

### Evaluator Notes

Documented as an accepted risk in SECURITY.md by explicit decision — recorded as fail because the control is absent.

### Effort Estimate

M


### SCALE-003

## Finding: SCALE-003 — Mcp-Session-Id Routing via Edge-LB (HAProxy Stick-Tables)

**Severity:** high
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** SCALE-003
**Category:** SCALE
**Audit-Run:** 2026-07-28T062517-Z-amtsblatt-mcp

### Observed Behavior

Check status: **fail** (1 evidence points collected).

- No edge load balancer configuration in the repo

### Expected Behavior

All pass criteria of SCALE-003 satisfied. See `checks/SCALE-003` in the mcp-audit catalogue
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- No Mcp-Session-Id-aware routing
- No stick-table or hash mechanism
- No failover test

### Evaluator Notes

Same root cause as SCALE-002.

### Effort Estimate

M


### SCALE-004

## Finding: SCALE-004 — Containerization mit Multi-Stage-Builds

**Severity:** medium
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** SCALE-004
**Category:** SCALE
**Audit-Run:** 2026-07-28T062517-Z-amtsblatt-mcp

### Observed Behavior

Check status: **partial** (5 evidence points collected).

- Two FROM statements — multi-stage (Dockerfile:3,19)
- Stages named AS builder / AS runtime
- python:3.14-slim base
- USER 10001:10001 non-root

### Expected Behavior

All pass criteria of SCALE-004 satisfied. See `checks/SCALE-004` in the mcp-audit catalogue
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- No HEALTHCHECK directive, which the check requires for LB integration
- Final image size not measured

### Evaluator Notes

(none)

### Effort Estimate

S


### SCALE-006

## Finding: SCALE-006 — Resource-Limits per Container (Memory, CPU, FDs)

**Severity:** medium
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** SCALE-006
**Category:** SCALE
**Audit-Run:** 2026-07-28T062517-Z-amtsblatt-mcp

### Observed Behavior

Check status: **partial** (4 evidence points collected).

- mem_limit: 256m in compose.yaml
- cpus: 0.5 set
- read_only root filesystem
- cap_drop ALL

### Expected Behavior

All pass criteria of SCALE-006 satisfied. See `checks/SCALE-006` in the mcp-audit catalogue
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- No requests/limits split — Compose sets a flat limit with no burst allowance
- FD limit not raised; no ulimit stanza
- OOM restart behaviour not tested

### Evaluator Notes

(none)

### Effort Estimate

S


### SDK-002

## Finding: SDK-002 — Pydantic v2 / TypedDict / Dataclass als Tool-Returns

**Severity:** medium
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** SDK-002
**Category:** SDK
**Audit-Run:** 2026-07-28T062517-Z-amtsblatt-mcp

### Observed Behavior

Check status: **partial** (2 evidence points collected).

- pydantic>=2.7 in use for all input models
- Field defaults used consistently

### Expected Behavior

All pass criteria of SDK-002 satisfied. See `checks/SDK-002` in the mcp-audit catalogue
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- All 6 tools return str (rendered Markdown), not a BaseModel/TypedDict/dataclass
- No structured response envelope with source/provenance/results/count

### Evaluator Notes

Explicitly accepted by the maintainer as a deliberate deviation; recorded as partial because the control is genuinely absent.

### Effort Estimate

S


### SDK-003

## Finding: SDK-003 — Context Injection für Progress Reports und Logging

**Severity:** medium
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** SDK-003
**Category:** SDK
**Audit-Run:** 2026-07-28T062517-Z-amtsblatt-mcp

### Observed Behavior

Check status: **partial** (2 evidence points collected).

- Most tools are a single upstream call, under the 2s threshold
- Errors surface as tool results rather than being swallowed

### Expected Behavior

All pass criteria of SDK-003 satisfied. See `checks/SDK-003` in the mcp-audit catalogue
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- No tool takes ctx: Context
- gazette_search_detailed fans out to 5 upstream calls with no progress reporting

### Evaluator Notes

(none)

### Effort Estimate

S


### SDK-004

## Finding: SDK-004 — CORS Mcp-Session-Id Exposure bei HTTP/SSE

**Severity:** high
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** SDK-004
**Category:** SDK
**Audit-Run:** 2026-07-28T062517-Z-amtsblatt-mcp

### Observed Behavior

Check status: **fail** (1 evidence points collected).

- Transport is dual and the server is cloud-deployed

### Expected Behavior

All pass criteria of SDK-004 satisfied. See `checks/SDK-004` in the mcp-audit catalogue
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- No CORS middleware — _middleware.py provides only BearerAuth and RateLimit
- expose_headers does not include Mcp-Session-Id
- allow_headers not configured
- allow_origins not configured

### Evaluator Notes

Cloud-deployed with HTTP transport, so this bites harder here than in the sister server.

### Effort Estimate

M


### SEC-002

## Finding: SEC-002 — Token Passthrough Prohibition (RFC 8707 Audience Validation)

**Severity:** critical
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** SEC-002
**Category:** SEC
**Audit-Run:** 2026-07-28T062517-Z-amtsblatt-mcp

### Observed Behavior

Check status: **partial** (2 evidence points collected).

- Upstream calls carry no client credential — the gazette API is public and the inbound key is never forwarded
- Inbound key compared in constant time (_middleware.py:42)

### Expected Behavior

All pass criteria of SEC-002 satisfied. See `checks/SEC-002` in the mcp-audit catalogue
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- Static shared bearer key, so there is no aud claim to validate
- No iss validation
- No user identity propagated for an audit trail

### Evaluator Notes

Criteria assume a JWT-issuing IdP. The passthrough risk itself is absent; the token-validation controls are not implementable with a static key.

### Effort Estimate

M


### SEC-003

## Finding: SEC-003 — Progressive Scope-Minimierung: Least-Privilege-Modell

**Severity:** high
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** SEC-003
**Category:** SEC
**Audit-Run:** 2026-07-28T062517-Z-amtsblatt-mcp

### Observed Behavior

Check status: **fail** (1 evidence points collected).

- Single all-or-nothing bearer key

### Expected Behavior

All pass criteria of SEC-003 satisfied. See `checks/SEC-003` in the mcp-audit catalogue
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- No scope hierarchy
- No per-tool scope documentation
- No per-call scope validation
- No 403 with WWW-Authenticate

### Evaluator Notes

Read-only public data limits the blast radius, but the control is absent.

### Effort Estimate

M


### SEC-004

## Finding: SEC-004 — SSRF-Prevention: HTTPS-Enforcement + IP-Blocklisting

**Severity:** critical
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** SEC-004
**Category:** SEC
**Audit-Run:** 2026-07-28T062517-Z-amtsblatt-mcp

### Observed Behavior

Check status: **partial** (2 evidence points collected).

- Egress event hook rejects non-allow-listed hosts before the request leaves (server.py:325-341)
- GAZETTE_BASE is a hardcoded https constant

### Expected Behavior

All pass criteria of SEC-004 satisfied. See `checks/SEC-004` in the mcp-audit catalogue
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- No explicit https scheme validation
- No resolved-IP blocklist — 169.254.169.254, private and link-local ranges unchecked
- No DNS pinning

### Evaluator Notes

(none)

### Effort Estimate

M


### SEC-005

## Finding: SEC-005 — DNS-Rebinding-Prevention: DNS-Pinning gegen TOCTOU

**Severity:** high
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** SEC-005
**Category:** SEC
**Audit-Run:** 2026-07-28T062517-Z-amtsblatt-mcp

### Observed Behavior

Check status: **partial** (1 evidence points collected).

- Single httpx request per attempt

### Expected Behavior

All pass criteria of SEC-005 satisfied. See `checks/SEC-005` in the mcp-audit catalogue
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- No DNS pinning
- No test asserting one DNS call per request

### Evaluator Notes

(none)

### Effort Estimate

M


### SEC-009

## Finding: SEC-009 — Session-ID Cryptographic Binding (user_id:session_id)

**Severity:** critical
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** SEC-009
**Category:** SEC
**Audit-Run:** 2026-07-28T062517-Z-amtsblatt-mcp

### Observed Behavior

Check status: **fail** (1 evidence points collected).

- No session layer of the server's own

### Expected Behavior

All pass criteria of SEC-009 satisfied. See `checks/SEC-009` in the mcp-audit catalogue
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- No session id generation, binding, TTL or invalidation

### Evaluator Notes

Documented as an accepted risk in SECURITY.md by explicit decision — recorded as fail because the control is absent.

### Effort Estimate

M


### SEC-013

## Finding: SEC-013 — API-Key-Storage: Secret Manager statt Plain-Text Env-Vars

**Severity:** high
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** SEC-013
**Category:** SEC
**Audit-Run:** 2026-07-28T062517-Z-amtsblatt-mcp

### Observed Behavior

Check status: **partial** (3 evidence points collected).

- MCP_API_KEY held as SecretStr, never logged
- Container image carries no secrets
- Public Open Data, so Stufe 1 env vars are acceptable

### Expected Behavior

All pass criteria of SEC-013 satisfied. See `checks/SEC-013` in the mcp-audit catalogue
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- docs/secret-management.md absent, which the check requires even at Stufe 1
- No rotation mechanism — the key is read once at startup

### Evaluator Notes

(none)

### Effort Estimate

M


### SEC-014

## Finding: SEC-014 — Tool-Allow-Listing via MCP-Gateway-Pattern

**Severity:** medium
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** SEC-014
**Category:** SEC
**Audit-Run:** 2026-07-28T062517-Z-amtsblatt-mcp

### Observed Behavior

Check status: **partial** (2 evidence points collected).

- Only 6 tools, all read-only, so the exposure surface is small
- Green rubric allow-list is default-deny at the data layer

### Expected Behavior

All pass criteria of SEC-014 satisfied. See `checks/SEC-014` in the mcp-audit catalogue
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- No per-team or per-role tool allow-list
- Denied-tool calls are not audited separately

### Evaluator Notes

(none)

### Effort Estimate

S


### SEC-015

## Finding: SEC-015 — Pre-Flight Tool-Poisoning Detection

**Severity:** medium
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** SEC-015
**Category:** SEC
**Audit-Run:** 2026-07-28T062517-Z-amtsblatt-mcp

### Observed Behavior

Check status: **fail** (1 evidence points collected).

- No gateway layer in front of the server

### Expected Behavior

All pass criteria of SEC-015 satisfied. See `checks/SEC-015` in the mcp-audit catalogue
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- No pre-flight tool-poisoning detection
- None of the four pattern classes covered
- No SIEM audit events

### Evaluator Notes

(none)

### Effort Estimate

S


### SEC-021

## Finding: SEC-021 — Egress-Allow-List: Code-Layer und Network-Layer

**Severity:** high
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** SEC-021
**Category:** SEC
**Audit-Run:** 2026-07-28T062517-Z-amtsblatt-mcp

### Observed Behavior

Check status: **partial** (4 evidence points collected).

- Pre-request egress hook on every outbound request (server.py:325)
- docs/network-egress.md documents hosts and update procedure
- Network-layer guidance documented (NetworkPolicy, egress proxy)
- DNS path addressed

### Expected Behavior

All pass criteria of SEC-021 satisfied. See `checks/SEC-021` in the mcp-audit catalogue
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- ALLOWED_HOSTS is overridable at runtime via the MCP_ALLOWED_HOSTS env var (server.py:92-99); the check requires the code-layer list be not config-mutable
- An override replaces the default set entirely, so a misconfigured deployment can redirect egress wholesale

### Evaluator Notes

The sister server's equivalent list is a hard frozenset with no override and passes.

### Effort Estimate

M


---

## 6. Remediation-Plan

### Empfohlene Reihenfolge

1. **SEC-002** (critical, partial)
2. **SEC-004** (critical, partial)
3. **SEC-009** (critical, fail)
4. **ARCH-004** (high, partial)
5. **OBS-001** (high, partial)
6. **OBS-002** (high, partial)
7. **OPS-001** (high, fail)
8. **OPS-003** (high, fail)
9. **SCALE-002** (high, fail)
10. **SCALE-003** (high, fail)
11. **SDK-004** (high, fail)
12. **SEC-003** (high, fail)
13. **SEC-005** (high, partial)
14. **SEC-013** (high, partial)
15. **SEC-021** (high, partial)
16. **ARCH-002** (medium, partial)
17. **ARCH-011** (medium, partial)
18. **CH-004** (medium, partial)
19. **OBS-006** (medium, partial)
20. **OPS-002** (medium, partial)
21. **SCALE-004** (medium, partial)
22. **SCALE-006** (medium, partial)
23. **SDK-002** (medium, partial)
24. **SDK-003** (medium, partial)
25. **SEC-014** (medium, partial)
26. **SEC-015** (medium, fail)

---

## 7. Audit-Metadata

| Feld | Wert |
|---|---|


_Generated by tools/build_report.py — do not edit by hand._
