## Finding: SDK-003 — Context Injection für Progress Reports und Logging

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `amtsblatt-mcp` v0.6.0 |
| **Check-Reference** | `SDK-003` |
| **PDF-Reference** | Sec 3.1 |
| **Audit-Datum** | 2026-07-28 |
| **Auditor** | mcp-audit v1.0.0 (catalog 091f446b…) |

### Observed Behavior

- Structured per-tool-call logging via the logged_tool decorator

### Expected Behavior

See the Pass Criteria of `SDK-003` in the check catalogue (catalog_hash 091f446b…).

### Evidence / Gaps

- Tools take no ctx: Context, so no progress reporting or ctx.warning (unchanged since the last run)

### Effort Estimate

M
