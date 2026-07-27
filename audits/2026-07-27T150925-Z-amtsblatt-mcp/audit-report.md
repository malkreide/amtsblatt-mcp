# MCP-Server Audit-Report — `amtsblatt-mcp`

**Audit-Datum:** 
**Skill-Version:** ?
**Catalog-Version:** ?

---

## 1. Executive Summary

Server `amtsblatt-mcp` wurde gegen 46 anwendbare Best-Practice-Checks geprüft. 41 bestanden, 5 Findings dokumentiert (0 critical, 0 high, 5 medium, 0 low). Production-Readiness: erreicht.

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
| ARCH | 8 | 0 | 3 | 0 | 0 |
| CH | 1 | 0 | 0 | 0 | 0 |
| OBS | 5 | 0 | 0 | 0 | 0 |
| OPS | 3 | 0 | 0 | 0 | 0 |
| SCALE | 5 | 0 | 0 | 0 | 0 |
| SDK | 2 | 0 | 2 | 0 | 0 |
| SEC | 17 | 0 | 0 | 0 | 0 |
| **Total** | **41** | **0** | **5** | **0** | **0** |

---

## 4. Findings-Übersicht

_Policy: `fail-or-partial`_

| ID | Category | Severity | Status |
|---|---|---|---|
| ARCH-001 | ARCH | medium | partial |
| ARCH-008 | ARCH | medium | partial |
| ARCH-012 | ARCH | medium | partial |
| SDK-002 | SDK | medium | partial |
| SDK-003 | SDK | medium | partial |

**Gesamt:** 5 Findings

---

## 5. Detail-Findings

### ARCH-001

## Finding: ARCH-001 — Tool Naming Convention

**Severity:** medium
**Status:** open
**Server:** amtsblatt-mcp v0.3.0
**Check-Reference:** ARCH-001
**PDF-Reference:** Sec 2.2

### Observed Behavior

- All 5 tools snake_case, no special characters
- Descriptions carry use case and scope

### Expected Behavior

See the Pass Criteria of `ARCH-001` in the check catalogue (catalog_hash 091f446b…).

### Evidence / Gaps

- Namespace prefixing is now mixed: search_gazette_procurement and gazette_source_status carry a gazette_ prefix, while search_publications, get_publication and list_rubrics do not. Introduced by the v0.2.0 rename, which prefixed only the two names that collided with swiss-procurement-mcp. Either prefix all five or none

### Remediation

Decide one rule and apply it to all five tools. Either add the gazette_ prefix to search_publications, get_publication and list_rubrics, or drop it from the two that carry it and rely on the client-side server namespace alone. A mixed scheme is the worst of both: it neither disambiguates reliably nor stays predictable.

### Effort Estimate

S


### ARCH-008

## Finding: ARCH-008 — Drei Primitive nutzen: Tools, Resources und Prompts

**Severity:** medium
**Status:** open
**Server:** amtsblatt-mcp v0.3.0
**Check-Reference:** ARCH-008
**PDF-Reference:** Anhang A2

### Observed Behavior

- Tools only; list_rubrics and gazette_source_status are Resource candidates

### Expected Behavior

See the Pass Criteria of `ARCH-008` in the check catalogue (catalog_hash 091f446b…).

### Evidence / Gaps

- No Resources, no Prompts, no documented tools-only rationale (unchanged since the last run)

### Remediation

Either expose the stable reference data (canton list, code systems, rubric taxonomy) as Resources, or add a short README paragraph stating why this server is tools-only. The rationale is cheap and closes the check.

### Effort Estimate

S


### ARCH-012

## Finding: ARCH-012 — protocolVersion-Pinning + CHANGELOG + SDK-Update-Disziplin

**Severity:** medium
**Status:** open
**Server:** amtsblatt-mcp v0.3.0
**Check-Reference:** ARCH-012
**PDF-Reference:** Anhang A9

### Observed Behavior

- CHANGELOG.md in Keep-a-Changelog format, three releases documented since the last audit
- Dependabot active

### Expected Behavior

See the Pass Criteria of `ARCH-012` in the check catalogue (catalog_hash 091f446b…).

### Evidence / Gaps

- protocolVersion still not pinned anywhere; FastMCP default in use (unchanged since the last run)

### Remediation

Pin the negotiated protocolVersion explicitly in the server module and add a short "MCP Protocol Version" README section naming it.

### Effort Estimate

S


### SDK-002

## Finding: SDK-002 — Pydantic v2 / TypedDict / Dataclass als Tool-Returns

**Severity:** medium
**Status:** open
**Server:** amtsblatt-mcp v0.3.0
**Check-Reference:** SDK-002
**PDF-Reference:** Sec 3.1

### Observed Behavior

- Pydantic v2 input models with ConfigDict(extra='forbid') on every tool
- JSON output carries a consistent envelope with source, provenance, count, results and now language_mix

### Expected Behavior

See the Pass Criteria of `SDK-002` in the check catalogue (catalog_hash 091f446b…).

### Evidence / Gaps

- Tool return type is str (rendered Markdown or JSON), not a Pydantic model (unchanged since the last run)

### Remediation

Return Pydantic models instead of rendered strings, or document the Markdown-first contract as a deliberate deviation.

### Effort Estimate

L


### SDK-003

## Finding: SDK-003 — Context Injection für Progress Reports und Logging

**Severity:** medium
**Status:** open
**Server:** amtsblatt-mcp v0.3.0
**Check-Reference:** SDK-003
**PDF-Reference:** Sec 3.1

### Observed Behavior

- Structured per-tool-call logging via the logged_tool decorator

### Expected Behavior

See the Pass Criteria of `SDK-003` in the check catalogue (catalog_hash 091f446b…).

### Evidence / Gaps

- Tools take no ctx: Context, so no progress reporting or ctx.warning (unchanged since the last run)

### Remediation

Add ctx: Context to the tools that can exceed two seconds (get_publication, the searches) and report progress there.

### Effort Estimate

M


---

## 6. Remediation-Plan

### Empfohlene Reihenfolge

1. **ARCH-001** (medium, partial)
2. **ARCH-008** (medium, partial)
3. **ARCH-012** (medium, partial)
4. **SDK-002** (medium, partial)
5. **SDK-003** (medium, partial)

---

## 7. Audit-Metadata

| Feld | Wert |
|---|---|


_Generated by tools/build_report.py — do not edit by hand._


---

## Re-Audit-Delta gegenüber `2026-07-20T212024-Z-amtsblatt-mcp`

Beide Läufe verwenden denselben Katalog (`catalog_hash` `091f446b…`) und dieselbe
Applicability-Menge. Unterschiede stammen daher ausschliesslich aus dem Code, nicht
aus einer Katalog-Änderung.

| | Vorlauf, nach Fixes (v0.1.1) | Dieser Lauf (v0.3.0) |
|---|---|---|
| pass | 42 | 41 |
| partial | 4 | **5** |
| fail | 0 | 0 |

**Unverändert offen:** ARCH-008 (nur Tools, keine Resources/Prompts, keine begründete
Doku), ARCH-012 (kein `protocolVersion`-Pin), SDK-002 (Tool-Returns sind `str`),
SDK-003 (kein `ctx: Context`). Keiner dieser vier Punkte wurde von den Releases 0.2.0
und 0.3.0 berührt.

**Neu:** ARCH-001 fällt von `pass` auf `partial`. Die Umbenennung in v0.2.0 hat nur die
zwei Tools mit einem `gazette_`-Präfix versehen, die mit `swiss-procurement-mcp`
kollidierten — `search_publications`, `get_publication` und `list_rubrics` blieben ohne.
Das Ergebnis ist ein gemischtes Schema, das weder zuverlässig disambiguiert noch
vorhersagbar bleibt. Der Befund geht auf genau die Änderung zurück, die dieser
Audit-Zyklus selbst eingeführt hat.

**Bestätigt trotz grösserer Eingriffe:** Die Releases 0.2.0 und 0.3.0 haben Dedup-Logik,
Rubrik-Scope, XML-Parsing und die Tool-Oberfläche angefasst, ohne eine der
Datenschutz-Invarianten zu verletzen — `test_allowlist.py` läuft weiterhin als eigener
CI-Job grün, und die Freigabe der drei Subrubriken sendet nachweislich nie die
gesperrte Elternrubrik.

