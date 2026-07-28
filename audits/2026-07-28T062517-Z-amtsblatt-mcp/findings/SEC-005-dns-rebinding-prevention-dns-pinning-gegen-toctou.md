## Finding: SEC-005 — DNS-Rebinding-Prevention: DNS-Pinning gegen TOCTOU

**Severity:** high
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** SEC-005
**Category:** SEC
**Audit-Run:** 2026-07-28T062517-Z-amtsblatt-mcp

### Observed Behavior

Check status: **partial** (1 evidence points collected).

- Single httpx request per attempt

### Expected Behavior

All pass criteria of SEC-005 satisfied. See `checks/SEC-005` in the mcp-audit catalogue
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- No DNS pinning
- No test asserting one DNS call per request

### Evaluator Notes

(none)

### Effort Estimate

M
