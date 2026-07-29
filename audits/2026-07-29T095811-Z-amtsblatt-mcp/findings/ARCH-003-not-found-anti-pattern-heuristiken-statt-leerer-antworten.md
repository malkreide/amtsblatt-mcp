## Finding: ARCH-003 — «Not Found» Anti-Pattern: Heuristiken statt leerer Antworten

**Severity:** medium
**Status:** partial
**Server:** amtsblatt-mcp
**Check-Reference:** ARCH-003
**Category:** ARCH
**Audit-Run:** 2026-07-29T095811-Z-amtsblatt-mcp

### Observed Behavior

Check status: **partial** (2 Evidenzpunkte).

- Leeres Ergebnis liefert eine erklaerende Zeile mit Anpassungshinweis (server.py:1360)
- gazette_list_rubrics existiert, um 'nichts gefunden' von 'nicht erschlossen' zu trennen

### Expected Behavior

Alle Pass-Kriterien von ARCH-003 erfuellt. Siehe den mcp-audit-Katalog
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- Kein Fuzzy-/Suggestion-Mechanismus und kein match_type-Feld

### Effort Estimate

M
