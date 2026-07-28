## Finding: OBS-006 — OpenTelemetry Distributed Tracing pro Tool-Call

**Severity:** medium
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** OBS-006
**Category:** OBS
**Audit-Run:** 2026-07-28T062517-Z-amtsblatt-mcp

### Observed Behavior

Check status: **partial** (5 evidence points collected).

- OTel SDK in the otel extra (pyproject.toml:49)
- TracerProvider with OTLP HTTP exporter (_otel.py:27-33)
- HTTPXClientInstrumentor auto-instrumentation active
- OTLP endpoint via OTEL_EXPORTER_OTLP_ENDPOINT
- service.name set (_otel.py:40)

### Expected Behavior

All pass criteria of OBS-006 satisfied. See `checks/OBS-006` in the mcp-audit catalogue
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- No per-tool-call span — mcp.tool.name, mcp.user.id and mcp.tool.result.is_error are never set
- Only HTTP client spans are produced, so a tool call has no root span of its own

### Evaluator Notes

(none)

### Effort Estimate

S
