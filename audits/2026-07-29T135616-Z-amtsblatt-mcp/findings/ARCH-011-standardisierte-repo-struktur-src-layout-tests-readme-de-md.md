## Finding: ARCH-011 — Standardisierte Repo-Struktur (src-Layout, tests, README.de.md)

**Severity:** medium
**Status:** partial
**Server:** amtsblatt-mcp
**Check-Reference:** ARCH-011
**Category:** ARCH
**Audit-Run:** 2026-07-29T135616-Z-amtsblatt-mcp

### Observed Behavior

Check status: **partial** (2 Evidenzpunkte).

- Module getrennt: _cors, _log, _middleware, _net, _otel, rubrics
- build_http_app() buendelt beide Transporte in einer Funktion statt in zwei Zweigen

### Expected Behavior

Alle Pass-Kriterien von ARCH-011 erfuellt. Siehe den mcp-audit-Katalog
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- server.py mit 2433 Zeilen, alle 6 Handler darin — kein tools/-Package

### Effort Estimate

L
