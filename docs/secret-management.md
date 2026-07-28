# Secret management (SEC-013)

## Position: Stufe 1 (environment variables), deliberately

This server holds exactly **one** secret: `MCP_API_KEY`, the bearer key that
guards the SSE transport. The upstream it queries — amtsblattportal.ch — is
public and unauthenticated, so no credential is ever sent outbound.

SEC-013 permits Stufe 1 for `Public Open Data` provided the position is written
down. This document is that record.

## Why Stufe 1 is defensible here

The key protects **access to a read-only public-data server**, not the data
itself. Everything this server returns is already published by the
Confederation and the cantons. A leaked key lets someone query gazette
publications they could have queried on the portal directly; it does not
disclose anything, does not permit a write, and cannot be replayed against
amtsblattportal.ch because it is never forwarded there.

What the key actually buys is rate-limit attribution and keeping an
internet-exposed endpoint from being open to the world. That is worth having,
and worth rotating — but it does not warrant a secret manager.

## How it is handled

| Property | Implementation |
|---|---|
| In-memory type | `SecretStr` (`server.py`, `_middleware.py`) — an accidental `repr()`, f-string or config log renders `**********` |
| Comparison | `hmac.compare_digest` against a hash, constant time, so the endpoint leaks nothing by timing |
| Plaintext unwrap | Exactly one call site, the comparison itself |
| Startup behaviour | `MCP_TRANSPORT=sse` without `MCP_API_KEY` exits with an error. There is no implicit "auth disabled" mode |
| In the image | Not baked in. The `Dockerfile` sets no `ENV` carrying it; `compose.yaml` requires it from the shell or `.env` |
| In git | `.env` and `.env.*` are gitignored (except `.env.example`); gitleaks runs on every PR |
| In logs | `tests/test_secrets.py` asserts the key does not appear via `repr`, f-string or structured log output |

## Rotation

Possible without a code change, and it is a restart rather than a reload: the
key is read once at startup.

1. Generate: `openssl rand -hex 32`
2. Update the value in the deployment environment (or `.env`)
3. Restart the container
4. Update clients

There is no key-overlap window — a restart invalidates the old key immediately.
For a deployment where that matters, put a gateway in front and rotate there;
the built-in bearer gate is single-instance by design (see the operator
hardening notes in `SECURITY.md`).

## Not secrets

Everything else in the environment is operational: `MCP_TRANSPORT`,
`MCP_HOST`, `PORT`, `MCP_RATE_LIMIT`, `MCP_RATE_WINDOW`, `LOG_LEVEL`,
`RUBRICS_TTL`, `GAZETTE_MAX_RETRIES`, `GAZETTE_RETRY_BACKOFF`, and the
`OTEL_*` variables. Disclosing them reveals configuration, not access.

Note that `ALLOWED_HOSTS` is deliberately **not** an environment variable — it
is a literal `frozenset` in `server.py` with no override (SEC-021), so egress
cannot be widened from config.

## What would move this off Stufe 1

Each requires this document to be rewritten before the change ships:

- **Wrapping an authenticated upstream.** An outbound credential is a different
  risk class from an inbound gate: it would be replayable against a third party.
  Stufe 3 (secret manager), region Switzerland or EU per CH-001.
- **Serving non-public data.** The green allow-list is what keeps this server on
  `Public Open Data`; indexing a red rubric changes the data class and the
  storage requirement together.
- **Per-user identity instead of a shared key.** That is the `SEC-002`/`SEC-003`
  path and needs an identity provider, not a stronger place to put one string.

## Relationship to the sister server

`swiss-procurement-mcp` holds no secret at all — the simap.ch read endpoints are
public and it exposes no authenticated transport. Its own
`docs/secret-management.md` records that. The two servers are deliberately
different here; neither document should be copied onto the other.
