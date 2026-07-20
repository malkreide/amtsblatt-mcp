## Finding: ARCH-008 — Three primitives: Tools, Resources, Prompts

**Severity:** medium
**Status:** accepted-risk
**Server:** amtsblatt-mcp
**Check-Reference:** ARCH-008

### Observed Behavior
Only the Tools primitive is exposed; no Resources or Prompts, and no explicit rationale documented.

### Expected Behavior
At least one Resource/Prompt, or a documented rationale for a tools-only design.

### Risk Description
Read-only, addressable content (e.g. the rubric taxonomy) could be a Resource; agents lose a discovery affordance. Low impact for this server's search-oriented use.

### Remediation
Accepted for 0.1.x. Every tool is parameterised (language/format/class) and thus a poor fit for static Resource URIs; the fail-closed taxonomy is already exposed via `list_rubrics`. Candidate for a documented rationale or a `rubric://` Resource in a later minor.

### Effort Estimate
M
