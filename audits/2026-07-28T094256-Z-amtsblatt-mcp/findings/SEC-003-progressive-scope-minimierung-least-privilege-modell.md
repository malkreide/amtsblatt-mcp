## Finding: SEC-003 — Progressive Scope-Minimierung: Least-Privilege-Modell

**Severity:** high
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** SEC-003
**Category:** SEC
**Audit-Run:** 2026-07-28T094256-Z-amtsblatt-mcp

### Observed Behavior

Check status: **fail** (1 evidence points).

- Single all-or-nothing bearer key

### Expected Behavior

All pass criteria of SEC-003 satisfied. See the mcp-audit catalogue
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- No scope hierarchy
- No per-tool scope documentation
- No per-call scope validation
- No 403 with WWW-Authenticate

### Evaluator Notes

Read-only public data limits the blast radius, but the control is absent.

### Effort Estimate

M
