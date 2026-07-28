## Finding: ARCH-004 — Inversion of Control: Transport-agnostische Server-Logik

**Severity:** high
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** ARCH-004
**Category:** ARCH
**Audit-Run:** 2026-07-28T094256-Z-amtsblatt-mcp

### Observed Behavior

Check status: **partial** (3 evidence points).

- Transport selected by env var, stdio default
- Shared _lifespan across transports (server.py:934)
- Outputs transport-independent

### Expected Behavior

All pass criteria of ARCH-004 satisfied. See the mcp-audit catalogue
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- No tool uses ctx: Context
- Config read via os.environ at module scope, not a Settings object

### Evaluator Notes

(none)

### Effort Estimate

M
