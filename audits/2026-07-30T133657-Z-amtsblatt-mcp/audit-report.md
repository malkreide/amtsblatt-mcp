# MCP-Server Audit-Report — `amtsblatt-mcp`

**Audit-Datum:** 
**Skill-Version:** 1.0.0
**Catalog-Version:** ?

---

## 1. Executive Summary

Server `amtsblatt-mcp` wurde gegen 46 anwendbare Best-Practice-Checks geprüft. 34 bestanden, 12 Findings dokumentiert (2 critical, 6 high, 4 medium, 0 low). Production-Readiness: NICHT erreicht — blockierend: SCALE-002, SCALE-003, SEC-002, SEC-003, SEC-009.

**Production-Readiness:** NO

---

## 2. Profil-Snapshot

| Feld | Wert |
|---|---|
| Server-Name | `amtsblatt-mcp` |
| Audit-Datum | ? |
| Skill-Version | 1.0.0 |
| Catalog-Version | ? |

---

## 3. Applicability

### Status pro Kategorie

| Kategorie | Pass | Fail | Partial | Todo | N/A |
|---|---|---|---|---|---|
| architecture | 11 | 0 | 0 | 0 | 0 |
| compliance | 1 | 0 | 0 | 0 | 0 |
| observability | 3 | 0 | 2 | 0 | 0 |
| operations | 3 | 0 | 0 | 0 | 0 |
| scalability | 3 | 2 | 0 | 0 | 0 |
| sdk | 2 | 0 | 2 | 0 | 0 |
| security | 11 | 4 | 2 | 0 | 0 |
| **Total** | **34** | **6** | **6** | **0** | **0** |

---

## 4. Findings-Übersicht

_Policy: `fail-or-partial`_

| ID | Category | Severity | Status |
|---|---|---|---|
| SEC-002 | security | critical | fail |
| SEC-009 | security | critical | fail |
| OBS-001 | observability | high | partial |
| OBS-002 | observability | high | partial |
| SCALE-002 | scalability | high | fail |
| SCALE-003 | scalability | high | fail |
| SEC-003 | security | high | fail |
| SEC-022 | security | high | partial |
| SDK-002 | sdk | medium | partial |
| SDK-003 | sdk | medium | partial |
| SEC-014 | security | medium | partial |
| SEC-015 | security | medium | fail |

**Gesamt:** 12 Findings

---

## 5. Detail-Findings

### OBS-001

## Finding: OBS-001 — Protocol vs. Execution Errors: korrekte Trennung

**Severity:** high
**Status:** partial
**Server:** amtsblatt-mcp
**Check-Reference:** OBS-001
**Category:** OBS
**Audit-Run:** 2026-07-29T135616-Z-amtsblatt-mcp

### Observed Behavior

Check status: **partial** (3 Evidenzpunkte).

- Protokollfehler tragen echte JSON-RPC-Codes: -32602 / -32603, an mcp 2.0.0 gemessen
- tests/test_error_paths.py deckt beide Pfade ueber einen echten Client ab (13 Tests)
- Alle drei Ausgaenge tragen provenance: live_api / refused / degraded

### Expected Behavior

Alle Pass-Kriterien von OBS-001 erfuellt. Siehe den mcp-audit-Katalog
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- Upstream-Ausfall und Policy-Ablehnung kommen als normales Ergebnis statt is_error=true — dokumentierte Abweichung
- Unbekanntes Tool wird als tool-result geliefert (SDK-Verhalten)

### Effort Estimate

M


### OBS-002

## Finding: OBS-002 — Mask Error Details: keine Stacktraces / SQL ans LLM

**Severity:** high
**Status:** partial
**Server:** amtsblatt-mcp
**Check-Reference:** OBS-002
**Category:** OBS
**Audit-Run:** 2026-07-29T135616-Z-amtsblatt-mcp

### Observed Behavior

Check status: **partial** (2 Evidenzpunkte).

- Keine Tracebacks/Pfade in Tool-Results, per Test abgesichert
- _handle_error liefert kuratierte Meldungen statt roher Exceptions

### Expected Behavior

Alle Pass-Kriterien von OBS-002 erfuellt. Siehe den mcp-audit-Katalog
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- mask_error_details existiert in mcp 2.0.0 nicht — an 2.0.0 erneut geprueft

### Effort Estimate

S


### SCALE-002

## Finding: SCALE-002 — Stateful Load Balancing für Streamable HTTP / SSE

**Severity:** high
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** SCALE-002
**Category:** SCALE
**Audit-Run:** 2026-07-29T135616-Z-amtsblatt-mcp

### Observed Behavior

Check status: **fail** (2 Evidenzpunkte).

- docs/load-balancing.md mit nginx- und K8s-Ingress-Konfiguration, seit 0.18.0 auf /mcp
- MCP_STATELESS=1 ist seit 0.18.0 hier verfuegbar und nimmt Session-Affinitaet als Frage heraus

### Expected Behavior

Alle Pass-Kriterien von SCALE-002 erfuellt. Siehe den mcp-audit-Katalog
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- Der Check verlangt Sticky-LB ODER Shared-State-Session-Manager — Stateless ist keins von beidem
- Kein expliziter Session-TTL setzbar
- Kein Edge-LB deployed

### Effort Estimate

L


### SCALE-003

## Finding: SCALE-003 — Mcp-Session-Id Routing via Edge-LB (HAProxy Stick-Tables)

**Severity:** high
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** SCALE-003
**Category:** SCALE
**Audit-Run:** 2026-07-29T135616-Z-amtsblatt-mcp

### Observed Behavior

Check status: **fail** (1 Evidenzpunkte).

- Konfigurationsvorlage in docs/load-balancing.md vorhanden

### Expected Behavior

Alle Pass-Kriterien von SCALE-003 erfuellt. Siehe den mcp-audit-Katalog
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- Kein Edge-LB deployed, keine Stick-Table, kein TTL

### Effort Estimate

L


### SDK-002

## Finding: SDK-002 — Pydantic v2 / TypedDict / Dataclass als Tool-Returns

**Severity:** medium
**Status:** partial
**Server:** amtsblatt-mcp
**Check-Reference:** SDK-002
**Category:** SDK
**Audit-Run:** 2026-07-29T135616-Z-amtsblatt-mcp

### Observed Behavior

Check status: **partial** (2 Evidenzpunkte).

- pydantic>=2.0, strikte Inputmodelle mit extra='forbid'
- Envelope mit attribution und provenance in jeder Antwort

### Expected Behavior

Alle Pass-Kriterien von SDK-002 erfuellt. Siehe den mcp-audit-Katalog
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- Alle 6 Tools geben str zurueck statt Pydantic-Modelle — bewusste, in ROADMAP.md begruendete Abweichung; JSON-Format deckt maschinenlesbare Aufrufer ab

### Effort Estimate

L


### SDK-003

## Finding: SDK-003 — Context Injection für Progress Reports und Logging

**Severity:** medium
**Status:** partial
**Server:** amtsblatt-mcp
**Check-Reference:** SDK-003
**Category:** SDK
**Audit-Run:** 2026-07-29T135616-Z-amtsblatt-mcp

### Observed Behavior

Check status: **partial** (1 Evidenzpunkte).

- Kein Tool laeuft laenger als Millisekunden

### Expected Behavior

Alle Pass-Kriterien von SDK-003 erfuellt. Siehe den mcp-audit-Katalog
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- Kein ctx: Context-Parameter — bewusst nicht geplant

### Effort Estimate

M


### SEC-002

## Finding: SEC-002 — Token Passthrough Prohibition (RFC 8707 Audience Validation)

**Severity:** critical
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** SEC-002
**Category:** SEC
**Audit-Run:** 2026-07-29T135616-Z-amtsblatt-mcp

### Observed Behavior

Check status: **fail** (1 Evidenzpunkte).

- Bearer-Gate in _middleware.py schuetzt den SSE-Transport

### Expected Behavior

Alle Pass-Kriterien von SEC-002 erfuellt. Siehe den mcp-audit-Katalog
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- Ein einziger statischer Shared-Key, kein OAuth-Token — aud-Claim existiert nicht und kann nicht validiert werden

### Effort Estimate

XL


### SEC-003

## Finding: SEC-003 — Progressive Scope-Minimierung: Least-Privilege-Modell

**Severity:** high
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** SEC-003
**Category:** SEC
**Audit-Run:** 2026-07-29T135616-Z-amtsblatt-mcp

### Observed Behavior

Check status: **fail** (1 Evidenzpunkte).

- Alle Tools sind read-only, der Schaden eines zu weiten Scopes ist begrenzt

### Expected Behavior

Alle Pass-Kriterien von SEC-003 erfuellt. Siehe den mcp-audit-Katalog
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- Keine Scope-Hierarchie; ein Shared-Key laesst keine Per-Tool-Scopes zu

### Effort Estimate

L


### SEC-009

## Finding: SEC-009 — Session-ID Cryptographic Binding (user_id:session_id)

**Severity:** critical
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** SEC-009
**Category:** SEC
**Audit-Run:** 2026-07-29T135616-Z-amtsblatt-mcp

### Observed Behavior

Check status: **fail** (3 Evidenzpunkte).

- Bearer-Gate vor jedem HTTP-Pfad, auf beiden Transporten identisch gebaut
- Serverseitige Invalidierung ist seit 0.18.0 vorhanden: DELETE /mcp wird vom streamable-http-Transport behandelt (gemessen: 400 'Missing session ID' statt 405). Auf /sse weiterhin 405 bei nur GET/HEAD — das war die Luecke im Vorlauf
- MCP_STATELESS=1 entfernt Session-Tracking vollstaendig und macht Hijacking strukturell unmoeglich

### Expected Behavior

Alle Pass-Kriterien von SEC-009 erfuellt. Siehe den mcp-audit-Katalog
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- Shared-Key identifiziert das Deployment, nicht einen Nutzer — kein sub-Claim zum Binden
- Kein Session-TTL setzbar: session_idle_timeout wird von MCPServer nicht durchgereicht
- SDK-Session-IDs tragen 122 statt der geforderten 128 Zufallsbits
- Von sechs Kriterien ist eines erfuellt — Abwesenheit von Sessions ist keine Bindung

### Effort Estimate

XL


### SEC-014

## Finding: SEC-014 — Tool-Allow-Listing via MCP-Gateway-Pattern

**Severity:** medium
**Status:** partial
**Server:** amtsblatt-mcp
**Check-Reference:** SEC-014
**Category:** SEC
**Audit-Run:** 2026-07-29T135616-Z-amtsblatt-mcp

### Observed Behavior

Check status: **partial** (1 Evidenzpunkte).

- Alle 6 Tools sind read-only und tragen ein konsistentes Praefix

### Expected Behavior

Alle Pass-Kriterien von SEC-014 erfuellt. Siehe den mcp-audit-Katalog
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- Kein Gateway mit Tool-Allow-Listing deployed

### Effort Estimate

L


### SEC-015

## Finding: SEC-015 — Pre-Flight Tool-Poisoning Detection

**Severity:** medium
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** SEC-015
**Category:** SEC
**Audit-Run:** 2026-07-29T135616-Z-amtsblatt-mcp

### Observed Behavior

Check status: **fail** (0 Evidenzpunkte).

- (keine)

### Expected Behavior

Alle Pass-Kriterien von SEC-015 erfuellt. Siehe den mcp-audit-Katalog
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- Kein Pre-Flight-Poisoning-Detection-Layer — setzt ein Gateway voraus, das nicht existiert

### Effort Estimate

L


### SEC-022

## Finding: SEC-022 — Tool-Namespace und Definition-Hash-Pinning

**Severity:** medium
**Status:** accepted-risk
**Server:** amtsblatt-mcp
**Check-Reference:** SEC-022
**PDF-Reference:** Anhang B

### Observed Behavior

Five of six criteria are met as of 0.19.0. `tool-hashes.json` publishes a
per-tool SHA-256 over name, description, input/output schema and annotations plus
a `surface_sha256` over the whole set; `tests/test_tool_hashes.py` turns CI red on
drift; the CHANGELOG carries a "Tool Definition Changes" section and the stated
re-approval policy; no breaking tool change has occurred.

The namespace criterion is not met literally: the prefix is `gazette_`, not
`amtsblatt_mcp__<tool>`.

### Expected Behavior

"Alle Tools haben Namespace-Präfix mit Server-Identität (`<server>__<tool>`)."

### Evidence

- `tool-hashes.json` — 6 tools, `snapshot_version: 2`, `surface_sha256` present.
- `tests/test_tool_hashes.py` — 9 tests including the drift assertion and a
  presentation-only negative control.
- `tests/test_tool_naming.py` — enforces the `gazette_` prefix across all tools.
- Tool names: `gazette_search_publications`, `gazette_search_detailed`,
  `gazette_search_procurement`, `gazette_get_publication`,
  `gazette_list_rubrics`, `gazette_source_status`.

### Risk Description

Low, and the intent is met. The purpose of the namespace criterion is collision
avoidance between servers in one client; `gazette_` achieves that — it is what
keeps `source_status` from colliding with the companion server's tool of the same
role. The prefix is frozen in code and test-enforced, so it is not
config-mutable.

Renaming six published tools a second time is a breaking change requiring a major
bump, which the check itself notes. That cost buys the literal form of a criterion
whose intent is already satisfied.

### Remediation

Recorded as a deliberate deviation. If the literal form is ever required:

1. Rename all six tools to `amtsblatt_mcp__<tool>`.
2. Major version bump, `Tool Definition Changes` entry naming every old and new
   hash prefix, explicit re-approval notice.
3. Regenerate `tool-hashes.json` — all six per-tool hashes and the surface digest
   move, which is correct and the point.

### Effort Estimate

S (< 1d) mechanically; the cost is the breaking change, not the work.


---

## 6. Remediation-Plan

### Empfohlene Reihenfolge

1. **SEC-002** (critical, fail)
2. **SEC-009** (critical, fail)
3. **OBS-001** (high, partial)
4. **OBS-002** (high, partial)
5. **SCALE-002** (high, fail)
6. **SCALE-003** (high, fail)
7. **SEC-003** (high, fail)
8. **SEC-022** (high, partial)
9. **SDK-002** (medium, partial)
10. **SDK-003** (medium, partial)
11. **SEC-014** (medium, partial)
12. **SEC-015** (medium, fail)

---

## 7. Audit-Metadata

| Feld | Wert |
|---|---|
| skill_version | `1.0.0` |


_Generated by tools/build_report.py — do not edit by hand._
