## Finding: OBS-002 — Mask Error Details: keine Stacktraces / SQL ans LLM

**Severity:** high
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** OBS-002
**Category:** OBS
**Audit-Run:** 2026-07-28T062517-Z-amtsblatt-mcp

### Observed Behavior

Check status: **partial** (2 evidence points collected).

- No traceback.format_exc() or sys.exc_info() in src/
- Upstream bodies not echoed to the caller

### Expected Behavior

All pass criteria of OBS-002 satisfied. See `checks/OBS-002` in the mcp-audit catalogue
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- FastMCP constructed without mask_error_details=True (server.py:972)

### Evaluator Notes

(none)

### Effort Estimate

M
