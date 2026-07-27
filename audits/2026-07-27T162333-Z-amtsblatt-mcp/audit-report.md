# MCP-Server Audit-Report — `amtsblatt-mcp`

**Audit-Datum:** 
**Skill-Version:** ?
**Catalog-Version:** ?

---

## 1. Executive Summary

Server `amtsblatt-mcp` wurde gegen 46 anwendbare Best-Practice-Checks geprüft. 36 bestanden, 10 Findings dokumentiert (2 critical, 2 high, 6 medium, 0 low). Production-Readiness: erreicht.

**Production-Readiness:** YES

---

## 2. Profil-Snapshot

| Feld | Wert |
|---|---|
| Server-Name | `amtsblatt-mcp` |
| Audit-Datum | ? |
| Skill-Version | ? |
| Catalog-Version | ? |

---

## 3. Applicability

### Status pro Kategorie

| Kategorie | Pass | Fail | Partial | Todo | N/A |
|---|---|---|---|---|---|
| ARCH | 7 | 0 | 4 | 0 | 0 |
| CH | 1 | 0 | 0 | 0 | 0 |
| OBS | 4 | 0 | 1 | 0 | 0 |
| OPS | 3 | 0 | 0 | 0 | 0 |
| SCALE | 5 | 0 | 0 | 0 | 0 |
| SDK | 2 | 0 | 2 | 0 | 0 |
| SEC | 14 | 0 | 3 | 0 | 0 |
| **Total** | **36** | **0** | **10** | **0** | **0** |

---

## 4. Findings-Übersicht

_Policy: `fail-or-partial`_

| ID | Category | Severity | Status |
|---|---|---|---|
| ARCH-005 | ARCH | critical | partial |
| SEC-019 | SEC | critical | partial |
| SEC-007 | SEC | high | partial |
| SEC-021 | SEC | high | partial |
| ARCH-007 | ARCH | medium | partial |
| ARCH-008 | ARCH | medium | partial |
| ARCH-012 | ARCH | medium | partial |
| OBS-003 | OBS | medium | partial |
| SDK-002 | SDK | medium | partial |
| SDK-003 | SDK | medium | partial |

**Gesamt:** 10 Findings

---

## 5. Detail-Findings

### ARCH-005

## Finding: ARCH-005 — Keine Hardcoded Secrets: Env-Vars / Secret Manager only

| Feld | Wert |
|---|---|
| **Severity** | critical |
| **Status** | open |
| **Server** | `amtsblatt-mcp` v0.4.0 |
| **Check-Reference** | `ARCH-005` |
| **PDF-Reference** | Sec 2.1 |
| **Audit-Datum** | 2026-07-27 |
| **Auditor** | mcp-audit v1.0.0 (catalog 091f446b…) |

### Observed Behavior

- No secrets in source; MCP_API_KEY read from the environment at startup
- .gitignore covers .env (.gitignore:12)

### Expected Behavior

See the Pass Criteria of `ARCH-005` in the check catalogue (catalog_hash 091f446b…).

### Evidence / Gaps

- No gitleaks/trufflehog CI workflow — .github/workflows/ holds only ci.yml and publish.yml. The companion swiss-procurement-mcp ships one (.github/workflows/security.yml); this repo does not.
- No .env.example with placeholders in the repo.
- API key held as a plain str, not SecretStr, so it can reach an f-string.

### Effort Estimate

S


### ARCH-007

## Finding: ARCH-007 — Capability-Aggregation: Composability intern, Atomarität extern

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `amtsblatt-mcp` v0.4.0 |
| **Check-Reference** | `ARCH-007` |
| **PDF-Reference** | Sec 2.3 |
| **Audit-Datum** | 2026-07-27 |
| **Auditor** | mcp-audit v1.0.0 (catalog 091f446b…) |

### Observed Behavior

- Tools are individually well-scoped and return composed markdown

### Expected Behavior

See the Pass Criteria of `ARCH-007` in the check catalogue (catalog_hash 091f446b…).

### Evidence / Gaps

- No aggregated tool: no asyncio.gather anywhere in src/. A caller wanting search plus detail still makes N+1 round trips. The companion server added search_procurements_detailed for exactly this.

### Effort Estimate

M


### ARCH-008

## Finding: ARCH-008 — Drei Primitive nutzen: Tools, Resources und Prompts

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `amtsblatt-mcp` v0.4.0 |
| **Check-Reference** | `ARCH-008` |
| **PDF-Reference** | Anhang A2 |
| **Audit-Datum** | 2026-07-27 |
| **Auditor** | mcp-audit v1.0.0 (catalog 091f446b…) |

### Observed Behavior

- Tools only; list_rubrics and gazette_source_status are Resource candidates

### Expected Behavior

See the Pass Criteria of `ARCH-008` in the check catalogue (catalog_hash 091f446b…).

### Evidence / Gaps

- No Resources, no Prompts, no documented tools-only rationale (unchanged since the last run)

### Effort Estimate

S


### ARCH-012

## Finding: ARCH-012 — protocolVersion-Pinning + CHANGELOG + SDK-Update-Disziplin

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `amtsblatt-mcp` v0.4.0 |
| **Check-Reference** | `ARCH-012` |
| **PDF-Reference** | Anhang A9 |
| **Audit-Datum** | 2026-07-27 |
| **Auditor** | mcp-audit v1.0.0 (catalog 091f446b…) |

### Observed Behavior

- CHANGELOG.md in Keep-a-Changelog format, three releases documented since the last audit
- Dependabot active

### Expected Behavior

See the Pass Criteria of `ARCH-012` in the check catalogue (catalog_hash 091f446b…).

### Evidence / Gaps

- protocolVersion still not pinned anywhere; FastMCP default in use (unchanged since the last run)

### Effort Estimate

S


### OBS-003

## Finding: OBS-003 — Structured Logging mit RFC 5424 Severity-Stufen

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `amtsblatt-mcp` v0.4.0 |
| **Check-Reference** | `OBS-003` |
| **PDF-Reference** | Sec 6.3 |
| **Audit-Datum** | 2026-07-27 |
| **Auditor** | mcp-audit v1.0.0 (catalog 091f446b…) |

### Observed Behavior

- Structured JSON to stderr (_log.py:28-41)
- Rich bound context per event: rubric, publication_id, params, host, status, attempt, total (server.py log_event call sites)
- Three severity levels in use: INFO, WARNING, ERROR
- No print() anywhere in src/
- OpenTelemetry tracing wired via _otel.py

### Expected Behavior

See the Pass Criteria of `OBS-003` in the check catalogue (catalog_hash 091f446b…).

### Evidence / Gaps

- No structured-logging dependency (structlog/loguru) in pyproject.toml; stdlib logging with a hand-rolled formatter.
- DEBUG is never emitted, so 3 of the 4 required severity levels are active.

### Effort Estimate

S


### SDK-002

## Finding: SDK-002 — Pydantic v2 / TypedDict / Dataclass als Tool-Returns

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `amtsblatt-mcp` v0.4.0 |
| **Check-Reference** | `SDK-002` |
| **PDF-Reference** | Sec 3.1 |
| **Audit-Datum** | 2026-07-27 |
| **Auditor** | mcp-audit v1.0.0 (catalog 091f446b…) |

### Observed Behavior

- Pydantic v2 input models with ConfigDict(extra='forbid') on every tool
- JSON output carries a consistent envelope with source, provenance, count, results and now language_mix

### Expected Behavior

See the Pass Criteria of `SDK-002` in the check catalogue (catalog_hash 091f446b…).

### Evidence / Gaps

- Tool return type is str (rendered Markdown or JSON), not a Pydantic model (unchanged since the last run)

### Effort Estimate

M


### SDK-003

## Finding: SDK-003 — Context Injection für Progress Reports und Logging

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `amtsblatt-mcp` v0.4.0 |
| **Check-Reference** | `SDK-003` |
| **PDF-Reference** | Sec 3.1 |
| **Audit-Datum** | 2026-07-27 |
| **Auditor** | mcp-audit v1.0.0 (catalog 091f446b…) |

### Observed Behavior

- Structured per-tool-call logging via the logged_tool decorator

### Expected Behavior

See the Pass Criteria of `SDK-003` in the check catalogue (catalog_hash 091f446b…).

### Evidence / Gaps

- Tools take no ctx: Context, so no progress reporting or ctx.warning (unchanged since the last run)

### Effort Estimate

M


### SEC-007

## Finding: SEC-007 — Container-Sandboxing: Docker / chroot mit minimalen Privilegien

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `amtsblatt-mcp` v0.4.0 |
| **Check-Reference** | `SEC-007` |
| **PDF-Reference** | Sec 4.5 |
| **Audit-Datum** | 2026-07-27 |
| **Auditor** | mcp-audit v1.0.0 (catalog 091f446b…) |

### Observed Behavior

- Multi-stage Dockerfile, non-root USER mcp (Dockerfile:28-33)
- compose: read_only, cap_drop [ALL], no-new-privileges, mem/cpu/pids limits
- Docker build job in CI

### Expected Behavior

See the Pass Criteria of `SEC-007` in the check catalogue (catalog_hash 091f446b…).

### Evidence / Gaps

- `useradd --system` yields a UID in the 100-999 system range; the criterion requires >= 10000 and no explicit --uid is set.
- No seccomp profile declared.

### Effort Estimate

S


### SEC-019

## Finding: SEC-019 — Lethal Trifecta vermeiden: Server-Separation Read vs Write/Send

| Feld | Wert |
|---|---|
| **Severity** | critical |
| **Status** | open |
| **Server** | `amtsblatt-mcp` v0.4.0 |
| **Check-Reference** | `SEC-019` |
| **PDF-Reference** | Anhang B1 |
| **Audit-Datum** | 2026-07-27 |
| **Auditor** | mcp-audit v1.0.0 (catalog 091f446b…) |

### Observed Behavior

- SECURITY.md exists and documents the data-protection model and egress scope

### Expected Behavior

See the Pass Criteria of `SEC-019` in the check catalogue (catalog_hash 091f446b…).

### Evidence / Gaps

- No lethal-trifecta assessment: SECURITY.md contains zero occurrences of 'trifecta'. The criterion wants the three legs (private data, untrusted content, external communication) assessed explicitly. The companion server carries a per-leg table; this one does not.

### Effort Estimate

S


### SEC-021

## Finding: SEC-021 — Egress-Allow-List: Code-Layer und Network-Layer

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `amtsblatt-mcp` v0.4.0 |
| **Check-Reference** | `SEC-021` |
| **PDF-Reference** | Anhang B5 + B12 |
| **Audit-Datum** | 2026-07-27 |
| **Auditor** | mcp-audit v1.0.0 (catalog 091f446b…) |

### Observed Behavior

- ALLOWED_HOSTS frozenset with a pre-request assertion (server.py:92-98)
- EgressDenied raised on a non-allow-listed host (server.py:302,337)
- MCP_ALLOWED_HOSTS override documented in-code

### Expected Behavior

See the Pass Criteria of `SEC-021` in the check catalogue (catalog_hash 091f446b…).

### Evidence / Gaps

- No docs/network-egress.md. The enforcement exists in code but the egress surface is not documented for an operator, which the criterion asks for.

### Effort Estimate

S


---

## 6. Remediation-Plan

### Empfohlene Reihenfolge

1. **ARCH-005** (critical, partial)
2. **SEC-019** (critical, partial)
3. **SEC-007** (high, partial)
4. **SEC-021** (high, partial)
5. **ARCH-007** (medium, partial)
6. **ARCH-008** (medium, partial)
7. **ARCH-012** (medium, partial)
8. **OBS-003** (medium, partial)
9. **SDK-002** (medium, partial)
10. **SDK-003** (medium, partial)

---

## 7. Audit-Metadata

| Feld | Wert |
|---|---|


_Generated by tools/build_report.py — do not edit by hand._

---

## Re-Audit-Delta gegenüber 2026-07-27T150925-Z

Gleicher `catalog_hash` (`091f446b…`), gleiche 46 anwendbare Checks, gleiches
Profil. Jede Differenz ist Code oder Evidenz — nicht Katalog.

| | Vorlauf (v0.3.0) | Dieser Lauf (v0.4.0) |
|---|---|---|
| pass | 41 | **36** |
| partial | 5 | **10** |
| fail | 0 | 0 |

`production_ready: TRUE` — keine offenen critical- oder high-Fails.

### Der eigentliche Befund: die Evidenzbasis des Vorlaufs

**36 der 46 Checks** trugen im Vorlauf als einzige Evidenz die Zeile
*«unchanged since the post-fix state of the 2026-07-20 run; re-verified against
v0.3.0»*. Der Katalog verlangt für viele dieser Checks `evidence_required: 3`.
Ein Einzeiler ohne Datei- oder Zeilenreferenz erfüllt das nicht — nach der
Skill-Regel *«Ein Finding ohne `path/to/file.py:42` ist eine Meinung, kein
Befund»* gilt das für ein Pass genauso.

Zum Vergleich: der parallele `swiss-procurement-mcp`-Lauf desselben Datums hatte
**0 von 32** derart durchgereichte Checks.

Dieser Lauf hat die 36 nachverifiziert. Fünf hielten der Prüfung nicht stand:

| Check | Vorlauf | Jetzt | Warum |
|---|---|---|---|
| ARCH-005 | pass | partial | Kein gitleaks/trufflehog-Workflow in `.github/workflows/` (nur `ci.yml`, `publish.yml`); kein `.env.example`; API-Key als `str` statt `SecretStr` |
| ARCH-007 | pass | partial | Kein aggregiertes Tool — `asyncio.gather` kommt in `src/` nicht vor |
| OBS-003 | pass | partial | Keine Structured-Logging-Abhängigkeit; DEBUG wird nie emittiert, also 3 der 4 geforderten Stufen |
| SEC-007 | pass | partial | `useradd --system` → UID 100–999, gefordert ≥ 10000; kein seccomp-Profil deklariert |
| SEC-019 | pass | partial | `SECURITY.md` enthält **null** Vorkommen von «trifecta»; keine Bewertung der drei Legs |
| SEC-021 | pass | partial | Egress-Guard im Code vorhanden, aber kein `docs/network-egress.md` |

Bemerkenswert: `ARCH-005`, `SEC-019` und `SEC-021` wurden im Schwesterserver
`swiss-procurement-mcp` in v0.4.0 nachweislich geschlossen — hier gelten sie
seit dem Erstlauf als bestanden, ohne dass die entsprechende Arbeit je gemacht
wurde.

### Geschlossen

**ARCH-001 `partial` → `pass`.** Alle fünf Tools tragen das `gazette_`-Präfix
führend, snake_case, ohne Sonderzeichen; `tests/test_tool_naming.py` sichert das
Schema gegen erneutes Auseinanderlaufen ab.

### Unverändert akzeptiert

ARCH-008 (nur Tools-Primitive), ARCH-012 (kein `protocolVersion`-Pin),
SDK-002 (`str`-Returns), SDK-003 (kein `ctx: Context`).

### Korrektur einer früheren Schätzung

Vor diesem Lauf war 42 pass / 4 partial / 0 fail *abgeleitet* worden. Gemessen
sind es **36 / 10 / 0**. Die Differenz stammt nicht aus neuem Code, sondern
daraus, dass der Vorlauf Checks bestanden hat, die bei echter Prüfung nicht
bestehen.
