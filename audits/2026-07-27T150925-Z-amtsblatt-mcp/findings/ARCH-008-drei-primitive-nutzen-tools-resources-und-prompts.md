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
