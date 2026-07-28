## Finding: SDK-004 — CORS Mcp-Session-Id Exposure bei HTTP/SSE

**Severity:** high
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** SDK-004
**Category:** SDK
**Audit-Run:** 2026-07-28T062517-Z-amtsblatt-mcp

### Observed Behavior

Check status: **fail** (1 evidence points collected).

- Transport is dual and the server is cloud-deployed

### Expected Behavior

All pass criteria of SDK-004 satisfied. See `checks/SDK-004` in the mcp-audit catalogue
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- No CORS middleware — _middleware.py provides only BearerAuth and RateLimit
- expose_headers does not include Mcp-Session-Id
- allow_headers not configured
- allow_origins not configured

### Evaluator Notes

Cloud-deployed with HTTP transport, so this bites harder here than in the sister server.

### Effort Estimate

M
