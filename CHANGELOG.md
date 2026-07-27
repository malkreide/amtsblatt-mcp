# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] — 2026-07-27

Opens the part of this portal's procurement coverage that simap.ch does not
have, and makes the mirror/original distinction visible per publication. Both
follow from an exact corpus join, not an estimate.

### The measurement

A publication's XML carries `<simapPublicationNumber>` (e.g. `#41510-01`) when
it originates on simap.ch — that is simap's own `publicationNumber`, so the two
corpora join exactly, with no title or fuzzy matching.

Resolving every one of the 546 `OB-TI` records of 2026 against a simap TI
universe of 974 projects:

| | Records | Share |
|---|---|---|
| simap reference present and resolvable | 503 | 92.1% |
| placeholder `--` in the field | 3 | 0.5% |
| **no simap reference** | **40** | **7.3%** |

The split follows exactly one sub-rubric — `OB-TI65`, whose own name is
"Avvisi di gara **non CIAP**": 0 of its 39 records carry a reference, while
`OB-TI10`/`20`/`70` carry one in 506 of 507 cases.

Across all procurement rubrics (newest-records sample): `OB-AR` 25/25,
`OB-BS` 24/25, `OB-BL` 25/25, `OB-VS` 25/25 carry a reference — while
`AR-VS40` 0/25, `AR-OW40` 0/7 and `BA-SH40` 0/2 carry none.

Full write-up in [`docs/simap-overlap.md`](docs/simap-overlap.md).

### Added

- **`search_gazette_procurement` now searches the gazette-native sub-rubrics.**
  `AR-VS40` (Valais, 150 awards), `AR-OW40` (Obwalden, 7) and `BA-SH40`
  (Schaffhausen, 2) were declared in `PROCUREMENT_SUB_RUBRICS` since 0.1.0 but
  never used by any code path. They are the only procurement records here that
  simap.ch does not also carry.

  They are sent as `subRubrics` and never folded into `rubrics`: their parents
  `AR-VS`, `AR-OW` and `BA-SH` are collector rubrics holding Arbeitsvergaben and
  Baugesuche and stay blocked. A test asserts the parent is never transmitted.

- **`simap_publication_number` on `get_publication`.** Promoted out of
  `additional_fields`, with the `#` stripped and publisher placeholders (`--`)
  read as absent. A mirrored record now points at `swiss-procurement-mcp` for
  the original; a gazette-native one says it exists nowhere else.

### Changed

- **Valais, Obwalden and Schaffhausen return results instead of a redirect.**
  Previously every canton without an *active* `OB-*` rubric got the "use
  simap.ch" explainer — correct for most, wrong for these three, whose native
  sub-rubrics simap does not have. Valais is the sharp case: `OB-VS` is a dead
  simap import while `AR-VS40` is live, so an inactive rubric no longer
  suppresses a live sub-rubric.
- `AR-NW40` dropped from the searched scope: 0 publications. It stays on the
  green allow-list — emptiness is a coverage fact, not a data-protection one.
- Tool description states the mirror relationship and names the exception.

## [0.2.0] — 2026-07-27

Correctness release. Two defects were found by measuring the live corpus rather
than reading the documentation, and both had been silently wrong since 0.1.0.
Tool names change — see *Breaking* below.

### Breaking

- **`search_procurement` → `search_gazette_procurement`** and
  **`source_status` → `gazette_source_status`.** The old names collide with the
  companion server [`swiss-procurement-mcp`](https://github.com/malkreide/swiss-procurement-mcp),
  whose tools are `search_procurements` (one letter apart) and `source_status`
  (identical). Both servers are meant to be loaded side by side, so the names
  had to disambiguate for the model, not just for the client's namespacing.
  Bundled into this release deliberately: the deduplication fix below already
  changes result counts, and breaking twice would be worse than breaking once.

### Fixed

- **Language deduplication never deduplicated anything.** `_dedupe_languages`
  keyed on `publicationNumber` in the belief that language variants share it.
  They do not: verified live on `OB-TI`/2026-07-24, four tenders appear as eight
  records with consecutive but *different* numbers (…2888/2889, …2890/2891,
  …2892/2893, …2894/2895), different ids and `language` `it` vs `fr`. Every
  bilingual result set was therefore inflated — exactly the failure the
  function's own docstring promised to prevent.

  There is no structural pairing key in the list metadata (`dossierReference`
  and `repeatedPublications` are null, `onBehalfOf` is itself translated), so
  the replacement collapses only what is provable: records agreeing on rubric,
  sub-rubric, date and publication *form* whose title bodies are identical once
  the language-carrying form prefix ("Bando -" / "Appel d'offres -") is removed.
  The form class comes from an explicit literal map, so an unknown prefix never
  collapses — fail-closed, as for rubric codes. `Bando - X` and
  `Rettifica Bando - X` stay separate even on the same day.

  Cantons that translate the *body* as well (AR, parts of TI) are not
  collapsible without fuzzy matching, which this server does nowhere. Those are
  now reported instead of guessed at: every response carries `language_mix`, and
  a multilingual result set carries a caveat that the count exceeds the number
  of distinct notices.

- **`OB-BS` was still flagged as an active procurement rubric.** Measured
  2026-07-27: 504 (2021) → 1 149 → 1 058 → 319 (2024) → 15 (2025) → **2** (2026
  YTD). Basel-Stadt moved to simap.ch during 2024. Unlike `OB-BL`, `OB-VS` and
  `OB-ZG`, its rubric label carries no inactive marker — only the volume reveals
  it, which is why `active` must never be derived from the label. Same failure
  mode as the `OB-ZG` fix in 0.1.3, one release later and without the textual
  hint. `search_gazette_procurement(canton="BS")` now returns the simap.ch
  explanation; `include_inactive=True` still reaches the archive.

### Added

- **`only_language`** on both search tools: return a single language edition
  instead of one record per language. On `OB-TI`/2026-07-24 this turns eight
  upstream records into the four tenders that actually exist.
- **`language_mix`** in every search response, and the publication language on
  every rendered result line.
- **`scripts/measure_procurement_coverage.py`** — reproduces the per-year volume
  per `OB-*` rubric and flags candidates for `active=False`. Deliberately a
  hint, not an automatic switch.
- **[`docs/procurement-coverage.md`](docs/procurement-coverage.md)** — the
  measurement, why the rubric label is not sufficient evidence, and the language
  breakdown per rubric.

### Changed

- Test fixtures now mirror the real multilingual shape (distinct
  `publicationNumber` per language) instead of the assumed shared one. The old
  fixture encoded the very assumption that made the bug invisible.
- `Development Status` classifier `3 - Alpha` → `4 - Beta`.

## [0.1.3] — 2026-07-22

### Fixed

- **`OB-ZG` was misclassified as an active procurement rubric.** A live probe
  (`publicationStates=PUBLISHED`, 2026-07-22) confirmed it holds 0 publications
  and was never filled after the simap switch. `PROCUREMENT_RUBRICS["ZG"]` is
  now `active=False`, so a canton-less `search_procurement` no longer sweeps the
  empty rubric and `search_procurement(canton="ZG")` returns the same
  explanation-instead-of-empty response as the other inactive cantons.
- README claimed ZG publishes tenders and omitted the BL and VS historical
  archives (1 127 records reachable via `include_inactive=True`). The green
  allow-list in `rubrics.py` was already correct and is unchanged.

### Changed

- Tool and field descriptions now state the accurate active set (AR, BS, TI)
  and describe BL/VS as archives and ZG as an empty rubric. The inactive-canton
  list in the no-scope warning is derived from `PROCUREMENT_RUBRICS` instead of
  hard-coded.

## [0.1.2] — 2026-07-21

Metadata-fix release so the MCP Registry publish succeeds (0.1.1 published to
PyPI but the registry rejected it).

### Fixed

- **`server.json` description shortened to ≤100 characters.** The MCP Registry
  enforces a 100-char limit on the server description; the 120-char string used
  through 0.1.1 caused `publish` to fail with HTTP 422.

### Changed

- CI `publish.yml` sets `skip-existing: true` on the PyPI upload, so the
  registry job can be re-driven after a metadata fix without a duplicate-upload
  failure blocking the run.

## [0.1.1] — 2026-07-20

Hardening release following the first `mcp-audit-skill` audit (run
`2026-07-20T212024-Z-amtsblatt-mcp`, 46/68 checks applicable). Closes both
blocking findings; no behavioural change to the tools. See
[`audits/`](audits/) for the full report.

### Changed

- **Shared HTTP client (SDK-001).** A single `httpx.AsyncClient` is now reused
  across all upstream requests and closed by a FastMCP lifespan, instead of a
  new client (and TLS handshake) per call.
- **Loopback-default SSE bind (SEC-016).** The SSE transport now binds
  `127.0.0.1` by default; exposing all interfaces requires an explicit
  `MCP_HOST=0.0.0.0`. The Docker image sets it deliberately.
- **Container resource limits (SCALE-006).** `compose.yaml` now sets
  `mem_limit`, `cpus` and `pids_limit`.

### Added

- MCP Registry publishing on release (`mcp-name` marker + `publish-mcp` job).
- Regression tests for the shared-client lifecycle.

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
