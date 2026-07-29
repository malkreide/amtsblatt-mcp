## Finding: OBS-001 — Protocol vs. Execution Errors: korrekte Trennung

**Severity:** high
**Status:** partial
**Server:** amtsblatt-mcp
**Check-Reference:** OBS-001
**Category:** OBS
**Audit-Run:** 2026-07-29T095811-Z-amtsblatt-mcp

### Observed Behavior

Check status: **partial** (3 Evidenzpunkte).

- Protokollfehler tragen echte JSON-RPC-Codes: -32602 / -32603, an mcp 2.0.0 gemessen
- tests/test_error_paths.py deckt beide Pfade ueber einen echten Client ab (13 Tests)
- Alle drei Ausgaenge tragen provenance: live_api / refused / degraded

### Expected Behavior

Alle Pass-Kriterien von OBS-001 erfuellt. Siehe den mcp-audit-Katalog
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- Upstream-Ausfall und Policy-Ablehnung kommen als normales Ergebnis statt is_error=true — dokumentierte Abweichung
- Unbekanntes Tool wird als tool-result geliefert (SDK-Verhalten)

### Effort Estimate

M
