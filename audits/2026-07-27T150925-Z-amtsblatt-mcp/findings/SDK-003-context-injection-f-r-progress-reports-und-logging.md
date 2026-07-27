## Finding: SDK-003 — Context Injection für Progress Reports und Logging

**Severity:** medium
**Status:** open
**Server:** amtsblatt-mcp v0.3.0
**Check-Reference:** SDK-003
**PDF-Reference:** Sec 3.1

### Observed Behavior

- Structured per-tool-call logging via the logged_tool decorator

### Expected Behavior

See the Pass Criteria of `SDK-003` in the check catalogue (catalog_hash 091f446b…).

### Evidence / Gaps

- Tools take no ctx: Context, so no progress reporting or ctx.warning (unchanged since the last run)

### Remediation

Add ctx: Context to the tools that can exceed two seconds (get_publication, the searches) and report progress there.

### Effort Estimate

M
