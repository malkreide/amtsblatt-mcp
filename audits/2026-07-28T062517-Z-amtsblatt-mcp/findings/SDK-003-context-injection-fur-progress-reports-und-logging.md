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
