## Finding: SEC-003 — Progressive Scope-Minimierung: Least-Privilege-Modell

**Severity:** high
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** SEC-003
**Category:** SEC
**Audit-Run:** 2026-07-29T095811-Z-amtsblatt-mcp

### Observed Behavior

Check status: **fail** (1 Evidenzpunkte).

- Alle Tools sind read-only, der Schaden eines zu weiten Scopes ist begrenzt

### Expected Behavior

Alle Pass-Kriterien von SEC-003 erfuellt. Siehe den mcp-audit-Katalog
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- Keine Scope-Hierarchie; ein Shared-Key laesst keine Per-Tool-Scopes zu

### Effort Estimate

L
