## Finding: ARCH-007 — Capability-Aggregation: Composability intern, Atomarität extern

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `amtsblatt-mcp` v0.4.0 |
| **Check-Reference** | `ARCH-007` |
| **PDF-Reference** | Sec 2.3 |
| **Audit-Datum** | 2026-07-27 |
| **Auditor** | mcp-audit v1.0.0 (catalog 091f446b…) |

### Observed Behavior

- Tools are individually well-scoped and return composed markdown

### Expected Behavior

See the Pass Criteria of `ARCH-007` in the check catalogue (catalog_hash 091f446b…).

### Evidence / Gaps

- No aggregated tool: no asyncio.gather anywhere in src/. A caller wanting search plus detail still makes N+1 round trips. The companion server added search_procurements_detailed for exactly this.

### Effort Estimate

M
