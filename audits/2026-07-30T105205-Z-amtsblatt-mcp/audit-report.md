# MCP-Server Audit-Report — `amtsblatt-mcp`

**Audit-Datum:** 
**Skill-Version:** 1.0.0
**Catalog-Version:** ?

---

## 1. Executive Summary

Server `amtsblatt-mcp` wurde gegen 46 anwendbare Best-Practice-Checks geprüft. 33 bestanden, 13 Findings dokumentiert (2 critical, 6 high, 5 medium, 0 low). Production-Readiness: NICHT erreicht — blockierend: SCALE-002, SCALE-003, SEC-002, SEC-003, SEC-009.

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
| architecture | 10 | 0 | 1 | 0 | 0 |
| compliance | 1 | 0 | 0 | 0 | 0 |
| observability | 3 | 0 | 2 | 0 | 0 |
| operations | 3 | 0 | 0 | 0 | 0 |
| scalability | 3 | 2 | 0 | 0 | 0 |
| sdk | 2 | 0 | 2 | 0 | 0 |
| security | 11 | 4 | 2 | 0 | 0 |
| **Total** | **33** | **6** | **7** | **0** | **0** |

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
| SDK-002 | sdk | medium | partial |
| SDK-003 | sdk | medium | partial |
| SEC-014 | security | medium | partial |
| SEC-015 | security | medium | fail |

**Gesamt:** 13 Findings

---

## 5. Detail-Findings

### ARCH-003

## Finding: ARCH-003 — «Not Found» Anti-Pattern: Heuristiken statt leerer Antworten

**Severity:** medium
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** ARCH-003
**PDF-Reference:** Sec 2.2

### Observed Behavior

Version 0.20.0 closed three of the four pass criteria and deliberately declined
the first. Every search response now carries `match_type` (`exact` / `none`) in
the JSON payload and in the rendered Markdown meta line, and an empty result
names the filters that were applied and points at
`gazette_list_rubrics(rubric_class='all')` and `gazette_source_status`.
`_render_results` takes that note as a required argument, so a new search tool
cannot fall back to a generic line.

What is absent is criterion 1: no fuzzy-match and no term-suggestion mechanism on
any of the three search tools. `MatchType` has no `fuzzy` member, and
`tests/test_empty_results.py::test_no_search_tool_widens_the_callers_term`
asserts that an empty search issues exactly one upstream request carrying the
caller's keyword unmodified.

### Expected Behavior

Criterion 1 requires that **non-sensitive** search tools respond to an empty
result with a fuzzy match or a suggestion mechanism. Criterion 4 exempts
sensitive tools, which must stay exact-only with the decision documented.

### Evidence

- `src/amtsblatt_mcp/_matching.py:38` — `MatchType = Literal["exact", "none"]`,
  no `fuzzy` member, its absence asserted by a test.
- `src/amtsblatt_mcp/_matching.py:78` — `empty_note()` supplies the criterion-3
  hint.
- `src/amtsblatt_mcp/rubrics.py` — `GREEN_RUBRICS`, the searchable set: `BH`,
  `HR`, `KA-*`, `KO-*`, `OB-*`, `PL-*`, `PR-*`, `RE-*`, `RP-*`, `RS-*`, `VE-*`
  — commercial register, official notices, procurement, spatial planning,
  enactments.
- `RED_RUBRICS`, **not searchable**: `KK`, `SB`, `SR`, `LS`, `NA` (Konkurse,
  Schuldbetreibungen), `ES` / `TE-*` / `VA-*` (Erbschaft, Testament),
  `GB-*` / `GE-*` / `UV` / `SJ-BE` (gerichtliche Vorladungen), `BP-*`
  (Baugesuche), `BU-*` / `BV-*` / `FZ-*` (Zivilstand), `GR-*` (Grundbuch).
- `SECURITY.md` § "No fuzzy matching, anywhere (ARCH-003)" and
  `SECURITY.de.md` § "Keine unscharfe Suche — bewusst (ARCH-003)".

### Risk Description

**The exact-only decision was justified with rubrics this server does not
serve.** The 0.20.0 CHANGELOG, both `SECURITY` files and the PR that closed the
work argue it as follows: "All three searches query official gazette
publications — bankruptcy notices, debt-collection summonses, estate calls,
construction objections", with the stated failure mode "naming the wrong company
as bankrupt".

Every rubric in that list is **red** and unreachable through any tool. The green
allow-list exists precisely to exclude systematic natural-person data, so the
searchable set is the non-sensitive one — the set criterion 1 applies to, not the
set criterion 4 exempts.

The residual risk is narrower and real: `HR` / `BH` (Handelsregister) and `OB-*`
(Beschaffungen) name legal persons, so broadening `Muster AG` to `Muster` would
return entries about different companies. That is a genuine argument about *how*
to widen. It is not the sensitive-data exception the check grants, and it does not
justify having no mechanism at all — a suggestion mechanism that proposes terms
without silently re-running the search satisfies criterion 1 with none of the
confusion risk.

Consequence of leaving it: a caller whose term is slightly wrong gets `none` with
no route to the right term, on a corpus of procurement and enactment notices —
exactly the case this check was written for.

### Remediation

Two options, ascending cost:

1. **Suggestion-only (recommended, S).** On `match_type == "none"`, return
   candidate terms without re-running the search — e.g. rubric and sub-rubric
   labels from the cached taxonomy sharing a prefix with the caller's keyword.
   Satisfies criterion 1, adds no upstream request, and cannot present another
   company's notice as an answer because it returns *terms*, not *results*.
2. **Widening with a legal-person guard (M).** Add `fuzzy` to `MatchType` and
   widen only where no legal person can be confused — plausibly `RE-*`, `RS-*`,
   `VE-*`, `RP-*`, `PL-*` (enactments, ordinances, spatial planning) — keeping
   `HR`, `BH` and `OB-*` exact-only. That is a per-rubric split rather than a
   per-tool one, and needs the mutation testing the per-tool split received.

Either way the prose in `SECURITY.md` and `SECURITY.de.md` must be corrected: it
currently names rubrics the server does not serve.

### Effort Estimate

S (< 1d) for option 1, M (1-3d) for option 2.


### OBS-001




### OBS-002




### SCALE-002




### SCALE-003




### SDK-002




### SDK-003




### SEC-002




### SEC-003




### SEC-009




### SEC-014




### SEC-015




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
9. **ARCH-003** (medium, partial)
10. **SDK-002** (medium, partial)
11. **SDK-003** (medium, partial)
12. **SEC-014** (medium, partial)
13. **SEC-015** (medium, fail)

---

## 7. Audit-Metadata

| Feld | Wert |
|---|---|
| skill_version | `1.0.0` |


_Generated by tools/build_report.py — do not edit by hand._
