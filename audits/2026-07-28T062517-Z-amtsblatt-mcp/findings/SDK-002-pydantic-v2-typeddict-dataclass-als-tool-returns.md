## Finding: SDK-002 — Pydantic v2 / TypedDict / Dataclass als Tool-Returns

**Severity:** medium
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** SDK-002
**Category:** SDK
**Audit-Run:** 2026-07-28T062517-Z-amtsblatt-mcp

### Observed Behavior

Check status: **partial** (2 evidence points collected).

- pydantic>=2.7 in use for all input models
- Field defaults used consistently

### Expected Behavior

All pass criteria of SDK-002 satisfied. See `checks/SDK-002` in the mcp-audit catalogue
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- All 6 tools return str (rendered Markdown), not a BaseModel/TypedDict/dataclass
- No structured response envelope with source/provenance/results/count

### Evaluator Notes

Explicitly accepted by the maintainer as a deliberate deviation; recorded as partial because the control is genuinely absent.

### Effort Estimate

S
