# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.9.0] — 2026-07-28

Closes **SEC-021**: the egress allow-list is no longer configurable.

### Breaking

`MCP_ALLOWED_HOSTS` is removed. `ALLOWED_HOSTS` is a literal `frozenset` in
`server.py`, changeable only in code.

### Why

SEC-021 requires the code-layer allow-list to be non-config-mutable, and the
reasoning holds: a guard that anything able to set an environment variable can
widen is not a guard. This was a regression against `swiss-procurement-mcp`,
which passes the same check with a hard `frozenset` — not a gap the two servers
shared.

Removing the override costs nothing real, which is what makes this a clean fix
rather than a trade-off. `GAZETTE_BASE` is a hardcoded constant, so nothing in
this server ever builds a URL for another host: **adding one to the allow-list
could never have caused a request to go there.** The `mirror.example.ch` example
that `docs/network-egress.md` used to suggest could not have worked. The
override's only reachable effects were widening what a *followed redirect* may
reach, and disabling the server outright if an override omitted the gazette
host — both downside.

### Test

`test_the_allow_list_is_not_environment_mutable` launches a subprocess with
`MCP_ALLOWED_HOSTS=evil.example,...` set and asserts the imported set is
unchanged. A subprocess rather than `importlib.reload`, because reloading swaps
the module's classes in `sys.modules` and every other test still holding the
original `EgressDenied` stops matching the newly-raised one — three unrelated
tests failed that way before the approach was changed. A fresh interpreter also
tests what actually matters: the value the module takes at real process startup.

Mutation-tested — restoring the env override fails the new test.

### Docs

`docs/network-egress.md` rewritten; the `MCP_ALLOWED_HOSTS` rows are gone from
both READMEs, and the operator hardening note in `SECURITY.md` / `SECURITY.de.md`
now says a change is deliberately a code change.

## [0.8.0] — 2026-07-28

Closes **SDK-004**: CORS with `Mcp-Session-Id`, in front of the bearer gate.

### The defect

MCP over SSE carries the session in the `Mcp-Session-Id` header. A browser
cannot *read* a response header the server does not name in
`Access-Control-Expose-Headers`, and cannot *send* it back unless the server
names it in `Access-Control-Allow-Headers`. `_middleware.py` provided bearer
auth and rate limiting and no CORS at all, so a browser-based MCP client
completed the initialize handshake and then lost the session on the very next
call. This server is cloud-deployed over SSE, so the transport it exposes to the
internet was the one that did not work from a browser.

### Middleware order is the load-bearing part

A browser never sends `Authorization` on a preflight `OPTIONS`. With auth ahead
of CORS every preflight would answer 401 and browser clients would be shut out
entirely — with a symptom pointing at the wrong layer. `apply_cors` is therefore
added *last*, because Starlette runs the most recently added middleware first.
`test_preflight_succeeds_without_the_bearer_key` sends no bearer key, exactly as
a browser would, and fails if that order ever regresses.

CORS short-circuits preflights and nothing else:
`test_auth_still_rejects_a_real_request_without_the_key` asserts that GET and
POST without the key still return 401, so putting CORS in front is not a hole in
the bearer gate.

### Origins are fail-closed

`MCP_CORS_ORIGINS` is unset by default, meaning no cross-origin browser access.
An operator who wants browser clients names the origins; nobody inherits a
permissive default. `*` is honoured but logs a WARNING and forces
`allow_credentials=False` — browsers reject a wildcard origin together with
credentials, so accepting both would ship a config that fails at request time
rather than at startup.

`tests/test_cors.py`, 12 tests, driving real requests through the assembled app
rather than inspecting the middleware stack — asserting that a `CORSMiddleware`
object exists would pass with an empty `expose_headers`, which is the defect
itself. Mutation-tested: reversing the middleware order fails 8 tests, emptying
`expose_headers` fails 1, defaulting to `*` fails the fail-closed test.

`starlette` is now a declared dependency; `_cors.py` imports it directly and it
previously arrived only transitively via `mcp`.

## [0.7.0] — 2026-07-28

Closes ARCH-008 and ARCH-012 from the 2026-07-28 re-audit, and records the
accepted deviation on SDK-002. Documentation and one constant — no behaviour
changes.

### ARCH-012 — MCP protocol version pinned

**Spec version `2025-11-25`** is now pinned as `MCP_PROTOCOL_VERSION` in
`server.py`, with a new *MCP Protocol Version* section in the README stating the
version, where it lives, and the update policy.

The SDK offers no way to configure this: negotiation happens in the session
layer and neither `FastMCP.__init__` nor `Settings` takes the parameter. So the
pin is a declared constant plus detection — a mismatch logs
`protocol_version_drift` at `WARNING` at runtime, and `tests/test_protocol_version.py`
fails in CI.

That split is the point: an SDK bump should break *our* build, not the runtime
of someone who upgraded `mcp` downstream.

Future protocol-version bumps get their own CHANGELOG line rather than being
folded into a dependency-bump entry.

### ARCH-008 — tools-only rationale documented

The check accepts either two of the three primitives or a documented reason for
using one. The README now carries the reason, and it is specific to this server
rather than generic.

The core of it: publication ids are opaque, so the rubric behind one cannot be
known until the document is fetched — which is why the post-fetch green gate
exists. Exposing publications as resources would mean either handing out
enumerable ids that have not been gated, or gating at fetch time anyway, at
which point the resource abstraction buys nothing and costs a second content
path to keep the guarantee on. v0.6.0 already showed what that costs: the
aggregated tool needed the gate extracted into a shared helper precisely because
a second path is where such guarantees quietly stop holding.

`gazette_list_rubrics` was checked concretely as a resource candidate and
rejected with a reason, rather than by blanket policy.

### SDK-002 — accepted deviation, documented

Tools return `str` rather than Pydantic models. The rendered output is composed
for the reader, not serialised from an object: it carries provenance, the
`green_rubrics_only` scope statement, the deduplication warning, and the
explanation a blocked rubric returns instead of data. Those are prose, not
fields. The `json` response format already covers machine-readable callers.

The README states what would change this: a caller that computes over results
rather than reading them, at which point typed models belong on the JSON path
specifically — not on every tool's return.

### Added

- `tests/test_protocol_version.py` — 4 tests: the pin matches the installed SDK,
  it is a dated spec version rather than a moving target, and the README names
  both the version and an update policy

## [0.6.0] — 2026-07-28

Closes ARCH-007, the last open finding from the 2026-07-27 re-audit. Additive —
no existing tool, argument or return shape changed.

### The gap

Every tool returned pointers. "Find notices and show me what they say" cost
1 + N calls — one search, then one `gazette_get_publication` per hit — and the
model had to do the chaining itself. `asyncio.gather` appeared nowhere in
`src/`.

### Added — `gazette_search_detailed`

Search *and* the full text of the top `top_n` hits in a single call, with the
detail fetches running concurrently, so the wait is the slowest single fetch
rather than their sum.

It inherits `SearchInput` outright, so the query surface is identical to
`gazette_search_publications` — callers do not learn a second dialect of the
same search. `top_n` is bounded to 1–5 so one call cannot become an unbounded
burst of upstream requests.

For procurement with full text in one call, pass `rubric='OB-<canton>'`.
`gazette_search_procurement` remains the better entry point when only the hit
list is wanted — it knows the canton-to-rubric resolution and the inactive
cantons.

### The part that mattered most: the green gate

Aggregation adds a **second** path to publication content. A data-protection
control that holds in one path and not the other is worse than none, because it
looks enforced.

So the post-fetch gate moved into a shared `_fetch_publication_gated()` helper
that both tools call, rather than being reimplemented. Every expanded document
passes it; one from a blocked rubric is discarded, counted, and reported as
withheld — never rendered, in Markdown or JSON.

That is asserted directly on the aggregated path rather than inferred from the
shared helper. Verified by mutation: disabling the gate fails three tests in
`tests/test_aggregation.py`.

### One bug this caught in itself

The first version of the rendering read `detail.get("text")`. The parser returns
that field as `publicationText`, so the tool emitted *"Kein Volltext im XML"*
for every single hit — the aggregation returned no text at all, which is the
entire point of it.

The test that should have caught this asserted a title that comes from the
search summary, not from the publication body, so it passed. It now asserts a
phrase that exists only inside the XML, and mutation-testing the field name back
to the broken one fails it.

### Added

- `tests/test_aggregation.py` — 12 tests: aggregation, fan-out bounds, partial
  failure, filter parity with the plain search, and four on the green gate
- `GAZETTE_MAX_DETAIL_N = 5`

### Changed

- `tests/test_logging.py::test_every_registered_tool_is_wrapped` now derives its
  tool list from the live registry instead of a hardcoded one. A hardcoded list
  goes stale exactly when a tool is added — which is when the check matters.

## [0.5.0] — 2026-07-27

Closes the six findings the 2026-07-27 re-audit downgraded, plus a version-drift
bug found along the way. No tool, argument or return shape changed.

### Context

The re-audit re-verified 36 checks that the prior run had carried forward on a
single line of evidence. Six did not hold up. Three of them — ARCH-005, SEC-019,
SEC-021 — had been closed in the companion `swiss-procurement-mcp`; here they
had been passing since the first run without the work ever being done.

### ARCH-005 — secret handling

- **gitleaks CI** (`.github/workflows/security.yml`) on push and PR, with
  `fetch-depth: 0` so a secret introduced in any past commit is caught, not just
  at the tip. Unlike the companion server this repo *does* take a credential
  (`MCP_API_KEY` for SSE), so the scan guards a real risk.
- **`.env.example`** with placeholders; `.gitignore` extended to `.env.*` with an
  explicit `!.env.example`.
- **`SecretStr`** for the API key. It is unwrapped at exactly one line — the one
  that builds the constant-time comparison target — so an accidental f-string or
  `repr()` renders `**********`. `BearerAuthMiddleware` now rejects a bare `str`
  with a `TypeError`, so the old shape cannot come back silently.

### SEC-019 — lethal-trifecta assessment

Written down in `SECURITY.md` and `SECURITY.de.md`, assessed leg by leg rather
than declared safe. At most one leg is present and it is the weakest: the
personal-data rubrics are unreachable by construction, egress is allow-listed to
one host, and there is no write, filesystem or sampling surface. The section
also states what would flip each leg on — which is the part that makes it useful
later.

### SEC-021 — egress documentation

`docs/network-egress.md`. Every behavioural claim in it was verified rather than
asserted: that `MCP_ALLOWED_HOSTS` *replaces* rather than extends the default
(an override omitting the gazette host disables the server, deliberately), that
the OTel exporter is inert without an endpoint, and that the documented pytest
selector matches real tests.

### SEC-007 — container hardening

- `useradd --system` picked a UID from the 100–999 range. That range is reserved
  for host system accounts, so under a bind mount the container user can inherit
  a real host user's ownership — and the exact number depends on package install
  order, so it moved between rebuilds. Now an explicit `10001`, with a numeric
  `USER 10001:10001` and a matching `user:` in compose.
- **seccomp:** Docker already applies its built-in profile, the equivalent of
  Kubernetes' `RuntimeDefault`, and Compose has no syntax that names it. The
  obvious-looking `security_opt: [seccomp:unconfined]` would *disable* it. So the
  posture is stated in a comment and in `docs/container-hardening.md` rather than
  "fixed" with a line that makes things worse.
- CI asserts both instead of trusting the Dockerfile: uid ≥ 10000 (not merely
  non-zero) and `Seccomp: 2` in `/proc/self/status`. The probe runs through
  `python` rather than `grep -oP`, because PCRE support in the base image is an
  assumption and the interpreter is not.
- The pre-existing non-root smoke test is kept and re-scoped: with a numeric
  `USER` it now asserts the `/etc/passwd` entry still resolves, which a numeric
  `USER` can silently lose.

### OBS-003 — structured logging

Moved to [structlog](https://www.structlog.org/). This server already emitted
INFO, WARNING and ERROR; the gaps were a logging library in `dependencies`,
`DEBUG` never being emitted, and nothing correlating the events of one call.

The dependency earns itself on the third: `structlog.contextvars` binds context
to the async task, so the retry and egress-denial events emitted deep in the
HTTP path carry the surrounding call's `correlation_id` without being threaded
through every signature.

`DEBUG` now marks tool entry, which tells an operator whether a hung call was
ever entered. `log_event` keeps its int-based signature, so none of the ~15 call
sites changed.

### Fixed — version drift

Found while writing the egress doc: `__init__.py` reported `0.1.3`, `_otel.py`
reported `0.1.2`, and the package was `0.4.0`. **Every OpenTelemetry span had
been carrying a `service.version` three releases stale.** All of them now read
`importlib.metadata`, so `pyproject.toml` is the single source, and
`tests/test_version.py` fails if a fourth literal appears.

### Added

- `tests/test_secrets.py` — 6 tests, including one that fails if `.env.example`
  ever accumulates a real-looking value
- `tests/test_logging.py` — 11 tests; this repo previously had none, which is
  part of why OBS-003 could be carried forward unnoticed
- `tests/test_version.py` — 3 tests, incl. a scan for new hardcoded literals
- `docs/network-egress.md`, `docs/container-hardening.md`

## [0.4.0] — 2026-07-27

Unifies the tool-naming scheme. **Breaking: four of the five tools are renamed.**

### The problem this closes

v0.2.0 introduced the `gazette_` prefix to resolve two real collisions with the
companion `swiss-procurement-mcp` — and prefixed only those two tools, leaving
`search_publications`, `get_publication` and `list_rubrics` bare. The 2026-07-27
re-audit graded ARCH-001 down from `pass` to `partial` for exactly that: a mixed
scheme neither disambiguates reliably nor stays predictable for a model reading
the tool list.

Two rules were available. Dropping the prefix everywhere is not viable — the
sister server also exposes `source_status`, so the collision returns the moment
both servers are mounted in one client. So: **all five carry the prefix**, and
the prefix leads rather than sits in the middle.

### Changed — breaking

| Before | After |
|---|---|
| `search_publications` | `gazette_search_publications` |
| `search_gazette_procurement` | `gazette_search_procurement` |
| `get_publication` | `gazette_get_publication` |
| `list_rubrics` | `gazette_list_rubrics` |
| `gazette_source_status` | unchanged |

Note that `search_gazette_procurement` moves the prefix from the middle to the
front. The old infix form was the least predictable name of the five: knowing
the prefix did not let you guess where it went.

No behaviour, arguments, return shapes or rubric scope changed. Callers that
pin tool names — client configs, prompt templates, saved conversations — need
the new names; nothing else is affected.

### Added

- `tests/test_tool_naming.py` — asserts every registered tool carries the
  prefix, that the surface is exactly the expected five, and that the prefix
  leads rather than repeats. A tool added without the prefix now fails in CI
  instead of surfacing in a client's tool list.

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
