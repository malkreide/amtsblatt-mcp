## Finding: SDK-002 — Pydantic v2 / TypedDict / Dataclass als Tool-Returns

**Severity:** medium
**Status:** open
**Server:** amtsblatt-mcp v0.3.0
**Check-Reference:** SDK-002
**PDF-Reference:** Sec 3.1

### Observed Behavior

- Pydantic v2 input models with ConfigDict(extra='forbid') on every tool
- JSON output carries a consistent envelope with source, provenance, count, results and now language_mix

### Expected Behavior

See the Pass Criteria of `SDK-002` in the check catalogue (catalog_hash 091f446b…).

### Evidence / Gaps

- Tool return type is str (rendered Markdown or JSON), not a Pydantic model (unchanged since the last run)

### Remediation

Return Pydantic models instead of rendered strings, or document the Markdown-first contract as a deliberate deviation.

### Effort Estimate

L
