## Finding: SDK-002 — Pydantic v2 / TypedDict / Dataclass als Tool-Returns

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `amtsblatt-mcp` v0.6.0 |
| **Check-Reference** | `SDK-002` |
| **PDF-Reference** | Sec 3.1 |
| **Audit-Datum** | 2026-07-28 |
| **Auditor** | mcp-audit v1.0.0 (catalog 091f446b…) |

### Observed Behavior

- Pydantic v2 input models with ConfigDict(extra='forbid') on every tool
- JSON output carries a consistent envelope with source, provenance, count, results and now language_mix

### Expected Behavior

See the Pass Criteria of `SDK-002` in the check catalogue (catalog_hash 091f446b…).

### Evidence / Gaps

- Tool return type is str (rendered Markdown or JSON), not a Pydantic model (unchanged since the last run)

### Effort Estimate

M
