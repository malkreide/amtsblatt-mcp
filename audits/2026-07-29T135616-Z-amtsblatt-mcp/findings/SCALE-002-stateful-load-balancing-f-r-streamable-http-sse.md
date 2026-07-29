## Finding: SCALE-002 — Stateful Load Balancing für Streamable HTTP / SSE

**Severity:** high
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** SCALE-002
**Category:** SCALE
**Audit-Run:** 2026-07-29T135616-Z-amtsblatt-mcp

### Observed Behavior

Check status: **fail** (2 Evidenzpunkte).

- docs/load-balancing.md mit nginx- und K8s-Ingress-Konfiguration, seit 0.18.0 auf /mcp
- MCP_STATELESS=1 ist seit 0.18.0 hier verfuegbar und nimmt Session-Affinitaet als Frage heraus

### Expected Behavior

Alle Pass-Kriterien von SCALE-002 erfuellt. Siehe den mcp-audit-Katalog
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- Der Check verlangt Sticky-LB ODER Shared-State-Session-Manager — Stateless ist keins von beidem
- Kein expliziter Session-TTL setzbar
- Kein Edge-LB deployed

### Effort Estimate

L
