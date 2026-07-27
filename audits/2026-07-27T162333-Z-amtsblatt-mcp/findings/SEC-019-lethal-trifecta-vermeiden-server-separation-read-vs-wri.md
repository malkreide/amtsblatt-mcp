## Finding: SEC-019 — Lethal Trifecta vermeiden: Server-Separation Read vs Write/Send

| Feld | Wert |
|---|---|
| **Severity** | critical |
| **Status** | open |
| **Server** | `amtsblatt-mcp` v0.4.0 |
| **Check-Reference** | `SEC-019` |
| **PDF-Reference** | Anhang B1 |
| **Audit-Datum** | 2026-07-27 |
| **Auditor** | mcp-audit v1.0.0 (catalog 091f446b…) |

### Observed Behavior

- SECURITY.md exists and documents the data-protection model and egress scope

### Expected Behavior

See the Pass Criteria of `SEC-019` in the check catalogue (catalog_hash 091f446b…).

### Evidence / Gaps

- No lethal-trifecta assessment: SECURITY.md contains zero occurrences of 'trifecta'. The criterion wants the three legs (private data, untrusted content, external communication) assessed explicitly. The companion server carries a per-leg table; this one does not.

### Effort Estimate

S
