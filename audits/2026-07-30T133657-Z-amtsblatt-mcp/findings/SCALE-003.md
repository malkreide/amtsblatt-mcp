## Finding: SCALE-003 — Mcp-Session-Id Routing via Edge-LB (HAProxy Stick-Tables)

**Severity:** high
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** SCALE-003
**Category:** SCALE
**Audit-Run:** 2026-07-29T135616-Z-amtsblatt-mcp

### Observed Behavior

Check status: **fail** (1 Evidenzpunkte).

- Konfigurationsvorlage in docs/load-balancing.md vorhanden

### Expected Behavior

Alle Pass-Kriterien von SCALE-003 erfuellt. Siehe den mcp-audit-Katalog
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- Kein Edge-LB deployed, keine Stick-Table, kein TTL

### Effort Estimate

L
