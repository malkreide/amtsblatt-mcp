## Finding: ARCH-005 — Keine Hardcoded Secrets: Env-Vars / Secret Manager only

| Feld | Wert |
|---|---|
| **Severity** | critical |
| **Status** | open |
| **Server** | `amtsblatt-mcp` v0.4.0 |
| **Check-Reference** | `ARCH-005` |
| **PDF-Reference** | Sec 2.1 |
| **Audit-Datum** | 2026-07-27 |
| **Auditor** | mcp-audit v1.0.0 (catalog 091f446b…) |

### Observed Behavior

- No secrets in source; MCP_API_KEY read from the environment at startup
- .gitignore covers .env (.gitignore:12)

### Expected Behavior

See the Pass Criteria of `ARCH-005` in the check catalogue (catalog_hash 091f446b…).

### Evidence / Gaps

- No gitleaks/trufflehog CI workflow — .github/workflows/ holds only ci.yml and publish.yml. The companion swiss-procurement-mcp ships one (.github/workflows/security.yml); this repo does not.
- No .env.example with placeholders in the repo.
- API key held as a plain str, not SecretStr, so it can reach an f-string.

### Effort Estimate

S
