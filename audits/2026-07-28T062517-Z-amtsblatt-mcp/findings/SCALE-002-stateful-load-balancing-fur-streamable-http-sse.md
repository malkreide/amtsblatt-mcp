## Finding: SCALE-002 — Stateful Load Balancing für Streamable HTTP / SSE

**Severity:** high
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** SCALE-002
**Category:** SCALE
**Audit-Run:** 2026-07-28T062517-Z-amtsblatt-mcp

### Observed Behavior

Check status: **fail** (1 evidence points collected).

- No sticky-session or shared-state session manager

### Expected Behavior

All pass criteria of SCALE-002 satisfied. See `checks/SCALE-002` in the mcp-audit catalogue
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- Neither pattern implemented
- No session TTL
- No failover test

### Evaluator Notes

Documented as an accepted risk in SECURITY.md by explicit decision — recorded as fail because the control is absent.

### Effort Estimate

M
