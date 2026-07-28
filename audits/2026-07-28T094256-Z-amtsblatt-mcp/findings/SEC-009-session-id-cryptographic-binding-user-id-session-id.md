## Finding: SEC-009 — Session-ID Cryptographic Binding (user_id:session_id)

**Severity:** critical
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** SEC-009
**Category:** SEC
**Audit-Run:** 2026-07-28T094256-Z-amtsblatt-mcp

### Observed Behavior

Check status: **fail** (1 evidence points).

- No session layer of the server's own

### Expected Behavior

All pass criteria of SEC-009 satisfied. See the mcp-audit catalogue
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- No session id generation, binding, TTL or invalidation

### Evaluator Notes

Documented as an accepted risk in SECURITY.md by explicit decision — recorded as fail because the control is absent.

### Effort Estimate

M
