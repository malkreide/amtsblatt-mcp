## Finding: SCALE-006 — Per-container resource limits

**Severity:** medium
**Status:** closed — remediated 2026-07-20
**Server:** amtsblatt-mcp
**Check-Reference:** SCALE-006

### Observed Behavior
`compose.yaml` set read_only / cap_drop ALL / no-new-privileges but no memory, CPU or PID limits.

### Expected Behavior
Explicit resource limits to bound blast radius and prevent noisy-neighbour exhaustion.

### Risk Description
Without limits a runaway or abused process could exhaust host memory/CPU/FDs.

### Remediation
Added `mem_limit: 256m`, `cpus: 0.5`, `pids_limit: 128` to `compose.yaml` (honoured by `docker compose up` v2).

### Effort Estimate
S
