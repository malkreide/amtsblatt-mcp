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
