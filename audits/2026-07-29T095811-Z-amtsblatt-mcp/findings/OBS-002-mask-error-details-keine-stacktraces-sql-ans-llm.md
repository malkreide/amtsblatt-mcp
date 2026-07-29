## Finding: OBS-002 — Mask Error Details: keine Stacktraces / SQL ans LLM

**Severity:** high
**Status:** partial
**Server:** amtsblatt-mcp
**Check-Reference:** OBS-002
**Category:** OBS
**Audit-Run:** 2026-07-29T095811-Z-amtsblatt-mcp

### Observed Behavior

Check status: **partial** (2 Evidenzpunkte).

- Keine Tracebacks/Pfade in Tool-Results, per Test abgesichert
- _handle_error liefert kuratierte Meldungen statt roher Exceptions

### Expected Behavior

Alle Pass-Kriterien von OBS-002 erfuellt. Siehe den mcp-audit-Katalog
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- mask_error_details existiert in mcp 2.0.0 nicht — an 2.0.0 erneut geprueft

### Effort Estimate

S
