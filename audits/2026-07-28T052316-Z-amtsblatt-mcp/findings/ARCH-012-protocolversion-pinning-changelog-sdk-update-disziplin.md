## Finding: ARCH-012 — protocolVersion-Pinning + CHANGELOG + SDK-Update-Disziplin

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `amtsblatt-mcp` v0.6.0 |
| **Check-Reference** | `ARCH-012` |
| **PDF-Reference** | Anhang A9 |
| **Audit-Datum** | 2026-07-28 |
| **Auditor** | mcp-audit v1.0.0 (catalog 091f446b…) |

### Observed Behavior

- CHANGELOG.md in Keep-a-Changelog format, three releases documented since the last audit
- Dependabot active

### Expected Behavior

See the Pass Criteria of `ARCH-012` in the check catalogue (catalog_hash 091f446b…).

### Evidence / Gaps

- protocolVersion still not pinned anywhere; FastMCP default in use (unchanged since the last run)

### Effort Estimate

S
