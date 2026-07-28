## Finding: SEC-015 — Pre-Flight Tool-Poisoning Detection

**Severity:** medium
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** SEC-015
**Category:** SEC
**Audit-Run:** 2026-07-28T062517-Z-amtsblatt-mcp

### Observed Behavior

Check status: **fail** (1 evidence points collected).

- No gateway layer in front of the server

### Expected Behavior

All pass criteria of SEC-015 satisfied. See `checks/SEC-015` in the mcp-audit catalogue
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- No pre-flight tool-poisoning detection
- None of the four pattern classes covered
- No SIEM audit events

### Evaluator Notes

(none)

### Effort Estimate

S
