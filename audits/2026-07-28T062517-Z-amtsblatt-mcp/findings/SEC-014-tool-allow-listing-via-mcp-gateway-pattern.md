## Finding: SEC-014 — Tool-Allow-Listing via MCP-Gateway-Pattern

**Severity:** medium
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** SEC-014
**Category:** SEC
**Audit-Run:** 2026-07-28T062517-Z-amtsblatt-mcp

### Observed Behavior

Check status: **partial** (2 evidence points collected).

- Only 6 tools, all read-only, so the exposure surface is small
- Green rubric allow-list is default-deny at the data layer

### Expected Behavior

All pass criteria of SEC-014 satisfied. See `checks/SEC-014` in the mcp-audit catalogue
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- No per-team or per-role tool allow-list
- Denied-tool calls are not audited separately

### Evaluator Notes

(none)

### Effort Estimate

S
