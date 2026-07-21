## Finding: ARCH-012 — protocolVersion pinning

**Severity:** medium
**Status:** accepted-risk
**Server:** amtsblatt-mcp
**Check-Reference:** ARCH-012

### Observed Behavior
No `protocolVersion` pin; the FastMCP default negotiation is used. CHANGELOG and Dependabot are present.

### Expected Behavior
An explicit, tested spec-version pin plus SDK-update discipline.

### Risk Description
A future SDK bump could silently change the negotiated protocol version. Low, given pinned deps + Dependabot + CI across 3.11–3.13.

### Remediation
Accepted for 0.1.x. FastMCP negotiates the version and does not expose a stable pin kwarg in the pinned SDK; revisit when the SDK exposes one.

### Effort Estimate
S
