## Finding: SEC-009 — Session-ID Cryptographic Binding (user_id:session_id)

**Severity:** critical
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** SEC-009
**Category:** SEC
**Audit-Run:** 2026-07-29T135616-Z-amtsblatt-mcp

### Observed Behavior

Check status: **fail** (3 Evidenzpunkte).

- Bearer-Gate vor jedem HTTP-Pfad, auf beiden Transporten identisch gebaut
- Serverseitige Invalidierung ist seit 0.18.0 vorhanden: DELETE /mcp wird vom streamable-http-Transport behandelt (gemessen: 400 'Missing session ID' statt 405). Auf /sse weiterhin 405 bei nur GET/HEAD — das war die Luecke im Vorlauf
- MCP_STATELESS=1 entfernt Session-Tracking vollstaendig und macht Hijacking strukturell unmoeglich

### Expected Behavior

Alle Pass-Kriterien von SEC-009 erfuellt. Siehe den mcp-audit-Katalog
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- Shared-Key identifiziert das Deployment, nicht einen Nutzer — kein sub-Claim zum Binden
- Kein Session-TTL setzbar: session_idle_timeout wird von MCPServer nicht durchgereicht
- SDK-Session-IDs tragen 122 statt der geforderten 128 Zufallsbits
- Von sechs Kriterien ist eines erfuellt — Abwesenheit von Sessions ist keine Bindung

### Effort Estimate

XL
