## Finding: OBS-003 — Structured Logging mit RFC 5424 Severity-Stufen

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `amtsblatt-mcp` v0.4.0 |
| **Check-Reference** | `OBS-003` |
| **PDF-Reference** | Sec 6.3 |
| **Audit-Datum** | 2026-07-27 |
| **Auditor** | mcp-audit v1.0.0 (catalog 091f446b…) |

### Observed Behavior

- Structured JSON to stderr (_log.py:28-41)
- Rich bound context per event: rubric, publication_id, params, host, status, attempt, total (server.py log_event call sites)
- Three severity levels in use: INFO, WARNING, ERROR
- No print() anywhere in src/
- OpenTelemetry tracing wired via _otel.py

### Expected Behavior

See the Pass Criteria of `OBS-003` in the check catalogue (catalog_hash 091f446b…).

### Evidence / Gaps

- No structured-logging dependency (structlog/loguru) in pyproject.toml; stdlib logging with a hand-rolled formatter.
- DEBUG is never emitted, so 3 of the 4 required severity levels are active.

### Effort Estimate

S
