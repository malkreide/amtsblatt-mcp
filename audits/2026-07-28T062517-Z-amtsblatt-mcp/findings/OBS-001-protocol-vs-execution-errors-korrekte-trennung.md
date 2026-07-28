## Finding: OBS-001 — Protocol vs. Execution Errors: korrekte Trennung

**Severity:** high
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** OBS-001
**Category:** OBS
**Audit-Run:** 2026-07-28T062517-Z-amtsblatt-mcp

### Observed Behavior

Check status: **partial** (2 evidence points collected).

- Upstream failures return explanatory German tool results rather than crashing
- Egress denial produces a specific message (server.py:901)

### Expected Behavior

All pass criteria of OBS-001 satisfied. See `checks/OBS-001` in the mcp-audit catalogue
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- No explicit isError construction or documented -326xx/-320xx protocol codes
- No test distinguishes the protocol-error path from the execution-error path

### Evaluator Notes

(none)

### Effort Estimate

M
