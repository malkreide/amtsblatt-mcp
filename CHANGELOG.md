# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2026-07-20

Initial release. Implements the `amtsblatt-mcp` specification split out of
`register-mcp` (`docs/amtsblatt-mcp-proposal.md`).

### Added

- **Fail-closed green allow-list** (`src/amtsblatt_mcp/rubrics.py`) — 49 released
  rubrics plus 4 sub-rubrics out of the 152 live top-level rubrics. All 152 are
  explicitly classified; anything unclassified is blocked by default.
- Five read-only tools: `search_publications`, `search_procurement`,
  `get_publication`, `list_rubrics`, `source_status`.
- Two-layer green gate: checked at the tool boundary *and* again in the query
  builder, so no code path can smuggle a blocked rubric into a request.
- Explanatory refusals for blocked rubrics — with the reason, without a
  circumvention hint, and without an HTTP call.
- Europe/Zurich deadline arithmetic for procurement submission dates.
- Language deduplication for notices published in de/fr/it.
- Defensive XML parsing across per-sub-rubric schemas, including unescaping and
  stripping entity-encoded HTML bodies used by the procurement rubrics.
- Guards for the verified upstream quirks: Silent Ignore (parameter allow-list
  plus corpus-size plausibility check) and Silent Empty (taxonomy validation
  before every call).
- Egress allow-list on the httpx client, enforced on redirects too.
- Bearer auth and sliding-window rate limiting for the SSE transport.
- Structured JSON logging; optional OpenTelemetry via the `otel` extra.

### Notes on deviations from the specification

- The proposal's traffic-light table uses glob notation (`KA-*`, `RS-*`, …).
  Globs are **expanded to literal codes**: a glob in code would auto-green any
  future upstream rubric matching the prefix, violating the proposal's own
  fail-closed rule.
- Three documented extensions to the green set after review: `KO-*` (communal
  notices, the twin of the green `KA-*`), `PL-BL` (Basel-Landschaft spells
  *Politische Rechte* `PL-`, not `PR-`), and `VE-*` (environment/transport/
  energy, institutional).
- Explicit red entries added for rubrics the source table did not cover:
  `AA-GR`, `BU-*`, `GR-BL`, `GR-BS`, `SJ-BE`.
- The upstream `uids` parameter is **not** exposed. The UID-keyed join belongs
  to `register-mcp`; a second entry point would sit outside this server's scope.

See [`docs/rubric-classification.md`](docs/rubric-classification.md) for the
full audit trail.
