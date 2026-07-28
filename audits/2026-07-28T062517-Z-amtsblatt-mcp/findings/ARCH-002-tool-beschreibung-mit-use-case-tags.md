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
