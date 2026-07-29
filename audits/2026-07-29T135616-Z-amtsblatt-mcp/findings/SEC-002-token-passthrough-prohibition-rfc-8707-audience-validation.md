## Finding: SEC-002 — Token Passthrough Prohibition (RFC 8707 Audience Validation)

**Severity:** critical
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** SEC-002
**Category:** SEC
**Audit-Run:** 2026-07-29T135616-Z-amtsblatt-mcp

### Observed Behavior

Check status: **fail** (1 Evidenzpunkte).

- Bearer-Gate in _middleware.py schuetzt den SSE-Transport

### Expected Behavior

Alle Pass-Kriterien von SEC-002 erfuellt. Siehe den mcp-audit-Katalog
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- Ein einziger statischer Shared-Key, kein OAuth-Token — aud-Claim existiert nicht und kann nicht validiert werden

### Effort Estimate

XL
