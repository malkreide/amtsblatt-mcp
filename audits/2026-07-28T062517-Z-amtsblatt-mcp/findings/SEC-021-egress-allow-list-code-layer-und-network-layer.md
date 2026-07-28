## Finding: SEC-021 — Egress-Allow-List: Code-Layer und Network-Layer

**Severity:** high
**Status:** open
**Server:** amtsblatt-mcp
**Check-Reference:** SEC-021
**Category:** SEC
**Audit-Run:** 2026-07-28T062517-Z-amtsblatt-mcp

### Observed Behavior

Check status: **partial** (4 evidence points collected).

- Pre-request egress hook on every outbound request (server.py:325)
- docs/network-egress.md documents hosts and update procedure
- Network-layer guidance documented (NetworkPolicy, egress proxy)
- DNS path addressed

### Expected Behavior

All pass criteria of SEC-021 satisfied. See `checks/SEC-021` in the mcp-audit catalogue
(catalog_hash 091f446b27965044ce658a1d5f4b2cabe2b0ab5661dcc1a53b6be8f1f2e093c0).

### Evidence / Gaps

- ALLOWED_HOSTS is overridable at runtime via the MCP_ALLOWED_HOSTS env var (server.py:92-99); the check requires the code-layer list be not config-mutable
- An override replaces the default set entirely, so a misconfigured deployment can redirect egress wholesale

### Evaluator Notes

The sister server's equivalent list is a hard frozenset with no override and passes.

### Effort Estimate

M
