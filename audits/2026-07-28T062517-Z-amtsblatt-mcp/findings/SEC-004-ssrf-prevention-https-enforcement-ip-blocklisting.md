## Finding: SEC-004 — SSRF-Prevention: HTTPS-Enforcement + IP-Blocklisting

**Severity:** critical
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** SEC-004
**Category:** SEC
**Audit-Run:** 2026-07-28T062517-Z-amtsblatt-mcp

### Observed Behavior

Check status: **partial** (2 evidence points collected).

- Egress event hook rejects non-allow-listed hosts before the request leaves (server.py:325-341)
- GAZETTE_BASE is a hardcoded https constant

### Expected Behavior

All pass criteria of SEC-004 satisfied. See `checks/SEC-004` in the mcp-audit catalogue
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- No explicit https scheme validation
- No resolved-IP blocklist — 169.254.169.254, private and link-local ranges unchecked
- No DNS pinning

### Evaluator Notes

(none)

### Effort Estimate

M
