## Finding: SDK-002 — Pydantic v2 / TypedDict / Dataclass als Tool-Returns

**Severity:** medium
**Status:** partial
**Server:** amtsblatt-mcp
**Check-Reference:** SDK-002
**Category:** SDK
**Audit-Run:** 2026-07-29T135616-Z-amtsblatt-mcp

### Observed Behavior

Check status: **partial** (2 Evidenzpunkte).

- pydantic>=2.0, strikte Inputmodelle mit extra='forbid'
- Envelope mit attribution und provenance in jeder Antwort

### Expected Behavior

Alle Pass-Kriterien von SDK-002 erfuellt. Siehe den mcp-audit-Katalog
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- Alle 6 Tools geben str zurueck statt Pydantic-Modelle — bewusste, in ROADMAP.md begruendete Abweichung; JSON-Format deckt maschinenlesbare Aufrufer ab

### Effort Estimate

L
