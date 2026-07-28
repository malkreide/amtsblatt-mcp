## Finding: ARCH-011 — Standardisierte Repo-Struktur (src-Layout, tests, README.de.md)

**Severity:** medium
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** ARCH-011
**Category:** ARCH
**Audit-Run:** 2026-07-28T062517-Z-amtsblatt-mcp

### Observed Behavior

Check status: **partial** (4 evidence points collected).

- All mandatory top-level files present
- src/ layout correct
- ci.yml + publish.yml present
- README.de.md parallel

### Expected Behavior

All pass criteria of ARCH-011 satisfied. See `checks/ARCH-011` in the mcp-audit catalogue
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- 6 tools (>5) but no tools/ directory split — server.py is ~2200 lines holding all handlers
- No README justification for the deviation

### Evaluator Notes

(none)

### Effort Estimate

S
