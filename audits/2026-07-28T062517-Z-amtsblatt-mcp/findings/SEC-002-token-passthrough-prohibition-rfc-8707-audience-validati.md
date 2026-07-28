## Finding: SEC-002 — Token Passthrough Prohibition (RFC 8707 Audience Validation)

**Severity:** critical
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** SEC-002
**Category:** SEC
**Audit-Run:** 2026-07-28T062517-Z-amtsblatt-mcp

### Observed Behavior

Check status: **partial** (2 evidence points collected).

- Upstream calls carry no client credential — the gazette API is public and the inbound key is never forwarded
- Inbound key compared in constant time (_middleware.py:42)

### Expected Behavior

All pass criteria of SEC-002 satisfied. See `checks/SEC-002` in the mcp-audit catalogue
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- Static shared bearer key, so there is no aud claim to validate
- No iss validation
- No user identity propagated for an audit trail

### Evaluator Notes

Criteria assume a JWT-issuing IdP. The passthrough risk itself is absent; the token-validation controls are not implementable with a static key.

### Effort Estimate

M
