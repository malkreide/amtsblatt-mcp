## Finding: SCALE-002 — Stateful Load Balancing für Streamable HTTP / SSE

**Severity:** high
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** SCALE-002
**Category:** SCALE
**Audit-Run:** 2026-07-29T095811-Z-amtsblatt-mcp

### Observed Behavior

Check status: **fail** (1 Evidenzpunkte).

- docs/load-balancing.md mit nginx- und K8s-Ingress-Konfiguration auf Mcp-Session-Id

### Expected Behavior

Alle Pass-Kriterien von SCALE-002 erfuellt. Siehe den mcp-audit-Katalog
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- Kein Sticky-LB und kein Shared-State-Session-Manager deployed
- Kein expliziter Session-TTL setzbar (an mcp 2.0.0 erneut geprueft)
- MCP_STATELESS nicht verfuegbar: SSE hat keinen Stateless-Modus

### Effort Estimate

L
