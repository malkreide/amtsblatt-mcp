## Finding: SCALE-003 — Mcp-Session-Id Routing via Edge-LB (HAProxy Stick-Tables)

**Severity:** high
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** SCALE-003
**Category:** SCALE
**Audit-Run:** 2026-07-28T062517-Z-amtsblatt-mcp

### Observed Behavior

Check status: **fail** (1 evidence points collected).

- No edge load balancer configuration in the repo

### Expected Behavior

All pass criteria of SCALE-003 satisfied. See `checks/SCALE-003` in the mcp-audit catalogue
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- No Mcp-Session-Id-aware routing
- No stick-table or hash mechanism
- No failover test

### Evaluator Notes

Same root cause as SCALE-002.

### Effort Estimate

M
