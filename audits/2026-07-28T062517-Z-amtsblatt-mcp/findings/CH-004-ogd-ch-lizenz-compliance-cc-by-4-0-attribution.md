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
