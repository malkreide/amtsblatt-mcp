## Finding: SEC-021 — Egress-Allow-List: Code-Layer und Network-Layer

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `amtsblatt-mcp` v0.4.0 |
| **Check-Reference** | `SEC-021` |
| **PDF-Reference** | Anhang B5 + B12 |
| **Audit-Datum** | 2026-07-27 |
| **Auditor** | mcp-audit v1.0.0 (catalog 091f446b…) |

### Observed Behavior

- ALLOWED_HOSTS frozenset with a pre-request assertion (server.py:92-98)
- EgressDenied raised on a non-allow-listed host (server.py:302,337)
- MCP_ALLOWED_HOSTS override documented in-code

### Expected Behavior

See the Pass Criteria of `SEC-021` in the check catalogue (catalog_hash 091f446b…).

### Evidence / Gaps

- No docs/network-egress.md. The enforcement exists in code but the egress surface is not documented for an operator, which the criterion asks for.

### Effort Estimate

S
