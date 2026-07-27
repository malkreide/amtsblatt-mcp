## Finding: ARCH-012 — protocolVersion-Pinning + CHANGELOG + SDK-Update-Disziplin

**Severity:** medium
**Status:** open
**Server:** amtsblatt-mcp v0.3.0
**Check-Reference:** ARCH-012
**PDF-Reference:** Anhang A9

### Observed Behavior

- CHANGELOG.md in Keep-a-Changelog format, three releases documented since the last audit
- Dependabot active

### Expected Behavior

See the Pass Criteria of `ARCH-012` in the check catalogue (catalog_hash 091f446b…).

### Evidence / Gaps

- protocolVersion still not pinned anywhere; FastMCP default in use (unchanged since the last run)

### Remediation

Pin the negotiated protocolVersion explicitly in the server module and add a short "MCP Protocol Version" README section naming it.

### Effort Estimate

S
