## Finding: SEC-013 — API-Key-Storage: Secret Manager statt Plain-Text Env-Vars

**Severity:** high
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** SEC-013
**Category:** SEC
**Audit-Run:** 2026-07-28T062517-Z-amtsblatt-mcp

### Observed Behavior

Check status: **partial** (3 evidence points collected).

- MCP_API_KEY held as SecretStr, never logged
- Container image carries no secrets
- Public Open Data, so Stufe 1 env vars are acceptable

### Expected Behavior

All pass criteria of SEC-013 satisfied. See `checks/SEC-013` in the mcp-audit catalogue
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- docs/secret-management.md absent, which the check requires even at Stufe 1
- No rotation mechanism — the key is read once at startup

### Evaluator Notes

(none)

### Effort Estimate

M
