## Finding: SCALE-006 — Resource-Limits per Container (Memory, CPU, FDs)

**Severity:** medium
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** SCALE-006
**Category:** SCALE
**Audit-Run:** 2026-07-28T094256-Z-amtsblatt-mcp

### Observed Behavior

Check status: **partial** (4 evidence points).

- mem_limit: 256m in compose.yaml
- cpus: 0.5 set
- read_only root filesystem
- cap_drop ALL

### Expected Behavior

All pass criteria of SCALE-006 satisfied. See the mcp-audit catalogue
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- No requests/limits split — Compose sets a flat limit with no burst allowance
- FD limit not raised; no ulimit stanza
- OOM restart behaviour not tested

### Evaluator Notes

(none)

### Effort Estimate

S
