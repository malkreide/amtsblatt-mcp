# Container hardening (SEC-007)

What the shipped image and `compose.yaml` guarantee, and what an operator has
to add per platform.

## What the image does

| Property | How |
|---|---|
| Non-root | `USER 10001:10001` — an explicit UID, not `useradd --system` |
| No shell for the runtime user | `--shell /usr/sbin/nologin` |
| Minimal runtime layer | Multi-stage: the runtime stage copies only the built venv |
| Credential handling | `MCP_API_KEY` is required for the SSE transport, passed at runtime and never baked into a layer. Held as `SecretStr` in-process (ARCH-005). |

### Why UID 10001 rather than `--system`

`useradd --system` picks a UID from the 100–999 range. That range is reserved
for host system accounts, so with a bind mount the container user can collide
with a real host user and inherit its file ownership. It is also *unstable*:
the exact number depends on which packages the base image installed first, so
it can change between rebuilds.

An explicit high UID avoids both. SEC-007 requires ≥ 10000.

## What `compose.yaml` adds

```yaml
read_only: true
cap_drop: [ALL]
security_opt: [no-new-privileges:true]
user: "10001:10001"
mem_limit: 256m
cpus: 0.5
pids_limit: 128
```

### The seccomp question

Docker applies its built-in seccomp profile automatically — the equivalent of
Kubernetes' `RuntimeDefault`. There is no Compose syntax that *names* it.

This matters because the obvious-looking line is actively harmful:

```yaml
security_opt: [seccomp:unconfined]   # WRONG — this DISABLES seccomp
```

So the profile is deliberately absent from `security_opt`: absence means the
default applies. Only add a `seccomp:` entry when you are shipping a custom
profile JSON that is narrower than the default.

Verify what a running container actually got:

```bash
docker run --rm amtsblatt-mcp:ci grep Seccomp /proc/self/status
# Seccomp:	2      → filtering active (2 = SECCOMP_MODE_FILTER)
# Seccomp:	0      → disabled; something overrode the default
```

## Kubernetes

Compose settings do not carry over. The equivalent `securityContext`:

```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 10001
  runAsGroup: 10001
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: true
  capabilities:
    drop: ["ALL"]
  seccompProfile:
    type: RuntimeDefault
```

With `readOnlyRootFilesystem: true`, mount an `emptyDir` at `/tmp` if any
dependency needs scratch space. This server does not write to disk, but a
transitive dependency might.

Pair it with an egress `NetworkPolicy` — the in-process allow-list documented
in [`network-egress.md`](network-egress.md) is defence in depth, not a
substitute for one.

## What CI verifies

The `Docker build` job asserts the two properties that silently regress:

- the image does not run as uid 0
- the server still imports under `--read-only --cap-drop ALL`

A Dockerfile that builds but runs as root would otherwise pass CI while failing
the check it was written for.
