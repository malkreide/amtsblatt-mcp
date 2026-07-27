## Finding: SEC-007 — Container-Sandboxing: Docker / chroot mit minimalen Privilegien

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `amtsblatt-mcp` v0.4.0 |
| **Check-Reference** | `SEC-007` |
| **PDF-Reference** | Sec 4.5 |
| **Audit-Datum** | 2026-07-27 |
| **Auditor** | mcp-audit v1.0.0 (catalog 091f446b…) |

### Observed Behavior

- Multi-stage Dockerfile, non-root USER mcp (Dockerfile:28-33)
- compose: read_only, cap_drop [ALL], no-new-privileges, mem/cpu/pids limits
- Docker build job in CI

### Expected Behavior

See the Pass Criteria of `SEC-007` in the check catalogue (catalog_hash 091f446b…).

### Evidence / Gaps

- `useradd --system` yields a UID in the 100-999 system range; the criterion requires >= 10000 and no explicit --uid is set.
- No seccomp profile declared.

### Effort Estimate

S
