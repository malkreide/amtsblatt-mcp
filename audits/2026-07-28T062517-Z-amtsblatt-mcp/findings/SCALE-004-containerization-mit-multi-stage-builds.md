## Finding: SCALE-004 — Containerization mit Multi-Stage-Builds

**Severity:** medium
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** SCALE-004
**Category:** SCALE
**Audit-Run:** 2026-07-28T062517-Z-amtsblatt-mcp

### Observed Behavior

Check status: **partial** (5 evidence points collected).

- Two FROM statements — multi-stage (Dockerfile:3,19)
- Stages named AS builder / AS runtime
- python:3.14-slim base
- USER 10001:10001 non-root

### Expected Behavior

All pass criteria of SCALE-004 satisfied. See `checks/SCALE-004` in the mcp-audit catalogue
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- No HEALTHCHECK directive, which the check requires for LB integration
- Final image size not measured

### Evaluator Notes

(none)

### Effort Estimate

S
