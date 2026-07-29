# MCP-Server Audit-Report — `<server>`

**Audit-Datum:** 
**Skill-Version:** ?
**Catalog-Version:** ?

---

## 1. Executive Summary

Server `<server>` wurde gegen 46 anwendbare Best-Practice-Checks geprüft. 32 bestanden, 14 Findings dokumentiert (2 critical, 6 high, 6 medium, 0 low). Production-Readiness: NICHT erreicht — blockierend: SCALE-002, SCALE-003, SEC-002, SEC-003, SEC-009.

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
| architecture | 9 | 0 | 2 | 0 | 0 |
| compliance | 1 | 0 | 0 | 0 | 0 |
| observability | 3 | 0 | 2 | 0 | 0 |
| operations | 3 | 0 | 0 | 0 | 0 |
| scalability | 3 | 2 | 0 | 0 | 0 |
| sdk | 2 | 0 | 2 | 0 | 0 |
| security | 11 | 4 | 2 | 0 | 0 |
| **Total** | **32** | **6** | **8** | **0** | **0** |

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
| ARCH-003 | architecture | medium | partial |
| ARCH-011 | architecture | medium | partial |
| SDK-002 | sdk | medium | partial |
| SDK-003 | sdk | medium | partial |
| SEC-014 | security | medium | partial |
| SEC-015 | security | medium | fail |

**Gesamt:** 14 Findings

---

## 5. Detail-Findings

### ARCH-003

## Finding: ARCH-003 — «Not Found» Anti-Pattern: Heuristiken statt leerer Antworten

**Severity:** medium
**Status:** partial
**Server:** amtsblatt-mcp
**Check-Reference:** ARCH-003
**Category:** ARCH
**Audit-Run:** 2026-07-29T095811-Z-amtsblatt-mcp

### Observed Behavior

Check status: **partial** (2 Evidenzpunkte).

- Leeres Ergebnis liefert eine erklaerende Zeile mit Anpassungshinweis (server.py:1360)
- gazette_list_rubrics existiert, um 'nichts gefunden' von 'nicht erschlossen' zu trennen

### Expected Behavior

Alle Pass-Kriterien von ARCH-003 erfuellt. Siehe den mcp-audit-Katalog
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- Kein Fuzzy-/Suggestion-Mechanismus und kein match_type-Feld

### Effort Estimate

M


### ARCH-011

## Finding: ARCH-011 — Standardisierte Repo-Struktur (src-Layout, tests, README.de.md)

**Severity:** medium
**Status:** partial
**Server:** amtsblatt-mcp
**Check-Reference:** ARCH-011
**Category:** ARCH
**Audit-Run:** 2026-07-29T095811-Z-amtsblatt-mcp

### Observed Behavior

Check status: **partial** (1 Evidenzpunkte).

- Module getrennt: _cors, _log, _middleware, _net, _otel, rubrics

### Expected Behavior

Alle Pass-Kriterien von ARCH-011 erfuellt. Siehe den mcp-audit-Katalog
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- server.py mit 2333 Zeilen, alle 6 Handler darin — kein tools/-Package

### Effort Estimate

L


### OBS-001

## Finding: OBS-001 — Protocol vs. Execution Errors: korrekte Trennung

**Severity:** high
**Status:** partial
**Server:** amtsblatt-mcp
**Check-Reference:** OBS-001
**Category:** OBS
**Audit-Run:** 2026-07-29T095811-Z-amtsblatt-mcp

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
**Audit-Run:** 2026-07-29T095811-Z-amtsblatt-mcp

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
**Audit-Run:** 2026-07-29T095811-Z-amtsblatt-mcp

### Observed Behavior

Check status: **fail** (1 Evidenzpunkte).

- docs/load-balancing.md mit nginx- und K8s-Ingress-Konfiguration auf Mcp-Session-Id

### Expected Behavior

Alle Pass-Kriterien von SCALE-002 erfuellt. Siehe den mcp-audit-Katalog
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- Kein Sticky-LB und kein Shared-State-Session-Manager deployed
- Kein expliziter Session-TTL setzbar (an mcp 2.0.0 erneut geprueft)
- MCP_STATELESS nicht verfuegbar: SSE hat keinen Stateless-Modus

### Effort Estimate

L


### SCALE-003

## Finding: SCALE-003 — Mcp-Session-Id Routing via Edge-LB (HAProxy Stick-Tables)

**Severity:** high
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** SCALE-003
**Category:** SCALE
**Audit-Run:** 2026-07-29T095811-Z-amtsblatt-mcp

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
**Audit-Run:** 2026-07-29T095811-Z-amtsblatt-mcp

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
**Audit-Run:** 2026-07-29T095811-Z-amtsblatt-mcp

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
**Audit-Run:** 2026-07-29T095811-Z-amtsblatt-mcp

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
**Audit-Run:** 2026-07-29T095811-Z-amtsblatt-mcp

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
**Audit-Run:** 2026-07-29T095811-Z-amtsblatt-mcp

### Observed Behavior

Check status: **fail** (1 Evidenzpunkte).

- Bearer-Gate vor jedem HTTP-Pfad

### Expected Behavior

Alle Pass-Kriterien von SEC-009 erfuellt. Siehe den mcp-audit-Katalog
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- Shared-Key identifiziert das Deployment, nicht einen Nutzer — kein sub-Claim zum Binden
- Kein Session-TTL setzbar
- SSE hat keinen DELETE-Endpunkt zur Session-Beendigung

### Effort Estimate

XL


### SEC-014

## Finding: SEC-014 — Tool-Allow-Listing via MCP-Gateway-Pattern

**Severity:** medium
**Status:** partial
**Server:** amtsblatt-mcp
**Check-Reference:** SEC-014
**Category:** SEC
**Audit-Run:** 2026-07-29T095811-Z-amtsblatt-mcp

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
**Audit-Run:** 2026-07-29T095811-Z-amtsblatt-mcp

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

## Finding: SEC-022 — Tool-Hash-Pinning + Namespace-Präfix gegen Rug Pull

**Severity:** high
**Status:** partial
**Server:** amtsblatt-mcp
**Check-Reference:** SEC-022
**Category:** SEC
**Audit-Run:** 2026-07-29T095811-Z-amtsblatt-mcp

### Observed Behavior

Check status: **partial** (1 Evidenzpunkte).

- Konsistentes gazette_-Praefix auf allen 6 Tools, per Test erzwungen

### Expected Behavior

Alle Pass-Kriterien von SEC-022 erfuellt. Siehe den mcp-audit-Katalog
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- Kein Tool-Hash-Pinning — Aenderungen an Beschreibungen sind fuer einen Client nicht erkennbar

### Effort Estimate

M


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
9. **ARCH-003** (medium, partial)
10. **ARCH-011** (medium, partial)
11. **SDK-002** (medium, partial)
12. **SDK-003** (medium, partial)
13. **SEC-014** (medium, partial)
14. **SEC-015** (medium, fail)

---

## 7. Audit-Metadata

| Feld | Wert |
|---|---|


_Generated by tools/build_report.py — do not edit by hand._
