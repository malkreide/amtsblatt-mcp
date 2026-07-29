## Finding: SEC-009 — Session-ID Cryptographic Binding (user_id:session_id)

**Severity:** critical
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** SEC-009
**Category:** SEC
**Audit-Run:** 2026-07-29T095811-Z-amtsblatt-mcp

### Observed Behavior

Check status: **fail** (1 Evidenzpunkte).

- Bearer-Gate vor jedem HTTP-Pfad

### Expected Behavior

Alle Pass-Kriterien von SEC-009 erfuellt. Siehe den mcp-audit-Katalog
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- Shared-Key identifiziert das Deployment, nicht einen Nutzer — kein sub-Claim zum Binden
- Kein Session-TTL setzbar
- SSE hat keinen DELETE-Endpunkt zur Session-Beendigung

### Effort Estimate

XL
