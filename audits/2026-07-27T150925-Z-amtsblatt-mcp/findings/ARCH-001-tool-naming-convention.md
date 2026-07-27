## Finding: ARCH-001 — Tool Naming Convention

**Severity:** medium
**Status:** open
**Server:** amtsblatt-mcp v0.3.0
**Check-Reference:** ARCH-001
**PDF-Reference:** Sec 2.2

### Observed Behavior

- All 5 tools snake_case, no special characters
- Descriptions carry use case and scope

### Expected Behavior

See the Pass Criteria of `ARCH-001` in the check catalogue (catalog_hash 091f446b…).

### Evidence / Gaps

- Namespace prefixing is now mixed: search_gazette_procurement and gazette_source_status carry a gazette_ prefix, while search_publications, get_publication and list_rubrics do not. Introduced by the v0.2.0 rename, which prefixed only the two names that collided with swiss-procurement-mcp. Either prefix all five or none

### Remediation

Decide one rule and apply it to all five tools. Either add the gazette_ prefix to search_publications, get_publication and list_rubrics, or drop it from the two that carry it and rely on the client-side server namespace alone. A mixed scheme is the worst of both: it neither disambiguates reliably nor stays predictable.

### Effort Estimate

S
