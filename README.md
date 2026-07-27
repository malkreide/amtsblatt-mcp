> 🇨🇭 **Part of the [Swiss Public Data MCP Portfolio](https://github.com/malkreide)**

# 📰 amtsblatt-mcp

![Version](https://img.shields.io/badge/version-0.2.0-blue)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-Model%20Context%20Protocol-purple)](https://modelcontextprotocol.io/)
[![No Auth Required](https://img.shields.io/badge/auth-none%20required-brightgreen)](https://github.com/malkreide/amtsblatt-mcp)
![CI](https://github.com/malkreide/amtsblatt-mcp/actions/workflows/ci.yml/badge.svg)

> MCP server for **amtsblattportal.ch** — the Swiss official gazette portal
> (SHAB + 27 cantonal gazettes). Public procurement and official notices,
> **person-data rubrics excluded by design**.

[🇩🇪 Deutsche Version](README.de.md)

## Overview

The Amtsblattportal publishes roughly **2.79 million** official notices: public
procurement, cantonal and communal announcements, enactments, spatial planning
— and also bankruptcies, debt collection, inheritance calls and civil-status
records naming natural persons.

This server exposes only the first group. Rubrics carrying systematic
natural-person data are **not queryable**, and no tool accepts a person's name,
birth date or address. That is a deliberate data-protection decision, explained
in [Data Protection & Scope](#data-protection--scope).

**Anchor demo query:** *"Which public tenders did canton Ticino publish this month?"*
→ `search_gazette_procurement(canton="TI", only_language=True, language="it")` → `get_publication(id=…)`

For procurement in any other canton — including Zürich, Bern and Basel-Stadt —
use [`swiss-procurement-mcp`](https://github.com/malkreide/swiss-procurement-mcp);
see [Boundary with `swiss-procurement-mcp`](#boundary-with-swiss-procurement-mcp).

## Features

- **Fail-closed green allow-list** — 49 released rubrics out of 152; everything
  else is blocked by default, including rubrics the upstream adds later
- **Explanatory refusals** — a blocked rubric returns *why*, never a silent
  empty result and never a workaround hint
- **Procurement-aware** — knows that only AR and TI still publish tenders here,
  that BS wound down during 2024 and BL/VS are historical archives, that `OB-ZG`
  was never filled after the simap switch, and that ZH routes everything through
  simap.ch — so it explains instead of returning nothing. Activity is
  [measured, not read off the rubric label](docs/procurement-coverage.md)
- **Deadline arithmetic** in Europe/Zurich, the legally relevant timezone
- **Honest multilingual counts** — the portal publishes one record per language
  with a *different* publication number each; identical editions are collapsed,
  translated ones are reported via `language_mix` rather than guessed at, and
  `only_language=True` gives a single-language view
- **Defensive XML parsing** — the schema is per-sub-rubric; no rubric-specific
  path is hard-coded, and entity-escaped HTML bodies are unescaped and stripped
- **Egress allow-list**, retry with backoff, structured JSON logging
- **Markdown or JSON output** with per-response attribution + `provenance`

## Prerequisites

- Python 3.11+
- **No API key.** The read API of amtsblattportal.ch is freely accessible.

## Installation

```bash
pip install amtsblatt-mcp
# or, without installing:
uvx amtsblatt-mcp
```

From source:

```bash
git clone https://github.com/malkreide/amtsblatt-mcp
cd amtsblatt-mcp
pip install -e ".[dev]"
```

## Configuration

### Claude Desktop

```json
{
  "mcpServers": {
    "amtsblatt": {
      "command": "uvx",
      "args": ["amtsblatt-mcp"]
    }
  }
}
```

### Cloud deployment (SSE)

```bash
export MCP_TRANSPORT=sse
export MCP_API_KEY="$(openssl rand -hex 32)"   # mandatory — fails loud if unset
export PORT=8000
amtsblatt-mcp
```

| Variable | Default | Purpose |
|---|---|---|
| `MCP_TRANSPORT` | `stdio` | `stdio` or `sse` |
| `MCP_HOST` | `127.0.0.1` | SSE bind address. Defaults to loopback; set `0.0.0.0` to expose on all interfaces (the Docker image does this deliberately). |
| `MCP_API_KEY` | — | Bearer token; **required** for SSE |
| `MCP_RATE_LIMIT` / `MCP_RATE_WINDOW` | `60` / `60` | Sliding-window rate limit |
| `MCP_ALLOWED_HOSTS` | `amtsblattportal.ch,www.amtsblattportal.ch` | Egress allow-list. An override replaces the default entirely. |
| `RUBRICS_TTL` | `86400` | Taxonomy cache TTL (seconds) |
| `LOG_LEVEL` | `INFO` | Structured JSON logs to stderr |

## Available Tools

| Tool | Signature | Notes |
|---|---|---|
| `search_publications` | `(keyword?, rubric?, sub_rubric?, canton?, date_start?, date_end?, limit=20, page=0, language='de', only_language=False)` | Green rubrics enforced. Without `rubric`, all green rubrics are injected — a keyword-only query can never reach a blocked one. |
| `search_gazette_procurement` | `(keyword?, canton?, date_start?, date_end?, include_inactive=False, limit=20, page=0, language='de', only_language=False)` | `OB-*` only. A canton with no *active* `OB-*` rubric gets a simap.ch explainer and **no HTTP call**. No CPV — the source has none. |
| `get_publication` | `(id, response_format='markdown')` | Full official text from XML. Re-checks the rubric after fetching; content from a blocked rubric is discarded. |
| `list_rubrics` | `(language='de', rubric_class='green', response_format='markdown')` | `rubric_class='all'` shows the full taxonomy with traffic-light classes and reasons — listed ≠ queryable. |
| `gazette_source_status` | `(response_format='markdown')` | Reachability, latency, cache age, scope metrics. |

All tools are `readOnlyHint=True`.

### Example use cases

| Question | Tool chain |
|---|---|
| Tenders in Ticino this quarter | `search_gazette_procurement(canton="TI", only_language=True, language="it")` |
| Tenders in any other canton | → use [`swiss-procurement-mcp`](https://github.com/malkreide/swiss-procurement-mcp) |
| What is even queryable here? | `list_rubrics()` |
| Why can't I search bankruptcies? | `list_rubrics(rubric_class="all")` |
| Zoning changes in Zurich | `search_publications(rubric="RP-ZH")` |
| Full text of a notice | `get_publication(id="fbf0ff9e-…")` |
| Everything published about one company | → use [`register-mcp`](https://github.com/malkreide/register-mcp) |

## Data Protection & Scope

The Amtsblattportal systematically publishes personal data of **natural**
persons. Those publications are public — but making them *systematically
queryable by name* through an AI agent is a repurposing the publication never
intended, and a profiling instrument under the revised Swiss FADP (revDSG).

Four rules follow, and they are enforced in code, not in documentation:

1. **Allow-list, never block-list.** Not explicitly green ⇒ not queryable.
   New upstream rubrics are closed by default.
2. **No person-based search entry** in any tool signature.
3. **No persistence.** Publications have statutory deletion periods; a cache
   outliving them would actively undermine them. Only the *taxonomy* is cached.
4. **Blocked ⇒ explained.** Never a silent empty result, never a hint at
   circumvention.

### What is excluded

🔴 Konkurse (`KK`), Schuldbetreibungen (`SB`), Schuldenrufe (`LS`, `SR`),
Nachlass (`NA`), Erbschaft/Testament/Ableben (`ES`, `TE-*`, `VA-*`),
Familie & Zivilstand (`FZ-*`, `BV-*`, `BU-*`), gerichtliche Vorladungen
(`UV`, `GB-*`, `GE-*`, `SJ-BE`), Baugesuche (`BP-*`), Grundbuch (`GR-*`),
Meldungskatalog GR (`AA-GR`).

🟡 Deferred: Steuerwesen, Anzeigen, Bewilligungen, Bildungs- und Kirchenwesen
and the general catch-all rubrics.

The full audit trail — including three documented extensions to the source
specification — is in [`docs/rubric-classification.md`](docs/rubric-classification.md).

### The boundary with `register-mcp`

For publications about a specific **company**, use
[`register-mcp`](https://github.com/malkreide/register-mcp). It keeps full
rubric access — including a firm's own bankruptcy — but only ever keyed on a
company **UID**. A firm's insolvency is corporate data, not natural-person
profiling, and UID scoping makes name-based enumeration impossible.

`amtsblatt-mcp` has the opposite shape: broad search, narrow rubrics. It does
not expose the upstream `uids` parameter at all.

### Boundary with `swiss-procurement-mcp`

**simap.ch is the primary source for Swiss public procurement** — all 26 cantons
plus the Confederation, with CPV and BKP codes, awards and publication history.
Use [`swiss-procurement-mcp`](https://github.com/malkreide/swiss-procurement-mcp)
for procurement questions.

**amtsblattportal.ch is the primary source for official notices** — commercial
register, spatial planning, enactments, cantonal and communal announcements.
That is what this server is for; procurement is 6 of its 49 released rubrics.

Procurement here is largely a **second publication** of the same tenders. Three
of the six `OB-*` rubrics say so in their own labels: `OB-BL` — "über Simap
importiert (I N A K T I V)", `OB-VS` — "bis Ende 2023 über simap.ch importiert",
`OB-ZG` — "bis Ende Februar 2024 via simap.ch importiert". Only TI and AR still
publish actively, and their notices are republications of simap tenders.

The two servers stay separate on purpose: different sources, different reuse
terms, and a fail-closed rubric gate that only means something while it covers
*every* tool in the server. See
[`docs/procurement-coverage.md`](docs/procurement-coverage.md) for the numbers.

## Architecture

```
   Claude / MCP client
            │
      amtsblatt-mcp
            │
   ┌────────┴────────┐
   │  green gate     │  ← rubrics.py: fail-closed allow-list
   └────────┬────────┘     (checked at the tool AND at the query builder)
            │
   ┌────────┴────────┐
   │  param allow-   │  ← Silent Ignore guard
   │  list + quirks  │  ← Silent Empty guard (taxonomy validation)
   └────────┬────────┘  ← plausibility guard (corpus-size check)
            │
   ┌────────┴────────┐
   │ egress allow-   │
   │ list (httpx)    │
   └────────┬────────┘
            │
  amtsblattportal.ch/api/v1
   /publications · /publications/{id}/xml · /rubrics · /tenants
```

**Architecture A (live-API-only).** The endpoints answer stably without
authentication, so no bulk dump is maintained.

### Verified upstream quirks (live-checked 2026-07-20)

| Quirk | Behaviour | Defence |
|---|---|---|
| **Silent Ignore** | An unknown parameter *name* returns HTTP 200 and the **full corpus**. `canton=ZH` (singular typo) silently drops the filter. | Query params built exclusively from `ALLOWED_GAZETTE_PARAMS`; plausibility guard rejects results > 2 000 000. |
| **Silent Empty** | An unknown rubric *value* returns HTTP 200 with `total: 0` — indistinguishable from a real no-hit. | Every code validated against the taxonomy **before** the call. |
| **Metadata only** | The list endpoint and `GET /publications/{id}` both return `content: null`. | Full text only via `/publications/{id}/xml`. |
| **Sorting ignored** | `pageRequest.sortOrders` is accepted with 200 but has no effect; `sortOrders` comes back `[]`. | Sorted client-side. |
| **Missing `publicationStates`** | Returns **401**, not 400 — it does *not* mean credentials are required. | Always injected; the 401 message says so. |
| **No page-size cap** | `pageRequest.size=2000` returns 2000 items. | Client-side cap of 100. |
| **Inconsistent plurals** | `rubrics`/`cantons`/`subRubrics` are plural, `keyword`/`tenant` singular. | Exact spellings encoded, not a pluralisation rule. |

## Known Limitations

- **Uneven cantonal coverage.** Only 16 of 29 mandates expose their own rubric
  taxonomy; AG, FR, GE, GL, JU, LU, NE, UR are still incomplete.
- **Deletion periods.** Publications drop out of the API over time — hence
  pass-through only.
- **Procurement boundary.** Most cantons, including **Zürich**, route tenders
  through simap.ch, outside this portal. There is no `OB-ZH`, and no CPV
  classification exists here.
- **Procurement coverage, measured** (`publicationStates=PUBLISHED`, 2026-07-27,
  records per calendar year — reproduce with
  `python scripts/measure_procurement_coverage.py`):

  | Rubric | 2022 | 2023 | 2024 | 2025 | 2026 | Latest | Status |
  |---|---|---|---|---|---|---|---|
  | `OB-TI` | 517 | 491 | 625 | 607 | 546 | 2026-07-27 | active |
  | `OB-AR` | 95 | 85 | 79 | 56 | 40 | 2026-05-22 | active |
  | `OB-BS` | 1 149 | 1 058 | 319 | 15 | **2** | 2026-05-20 | wound down during 2024 |
  | `OB-VS` | 0 | 1 052 | 1 | 0 | 0 | 2024-01-05 | archive — simap import until end of 2023 |
  | `OB-BL` | 0 | 74 | 0 | 0 | 0 | 2023-03-30 | archive — labelled «I N A K T I V» |
  | `OB-ZG` | 0 | 0 | 0 | 0 | 0 | — | never filled |

  **Only TI and AR still publish actively.** `OB-BS` is the instructive case:
  its label is a plain "Öffentliches Beschaffungswesen" with no inactive marker,
  so only the volume reveals the migration — which is why `active` is measured,
  never read. Use `include_inactive=True` to reach the BS, BL and VS archives.
  Details in [`docs/procurement-coverage.md`](docs/procurement-coverage.md).
- **No push.** Polling only; no subscription or webhook mechanism.
- **Legally binding text** is the signed PDF, not this API.

## Testing

```bash
pip install -e ".[dev]"
PYTHONPATH=src pytest tests/ -m "not live"   # 75 tests, no network
PYTHONPATH=src pytest tests/ -m live         # hits the real API
ruff check src/ tests/
```

The suite covers the mandatory portfolio set: green-rubric search with source
URL, **blocked rubric → explanation with zero HTTP calls**, canton filtering,
Europe/Zurich deadline arithmetic against a fixed "today", pagination across a
page boundary, language deduplication, boolean normalisation, and API-unreachable
handling. Fixtures are shortened real responses, consistently anonymised — no
real personal data.

## Project Structure

```
amtsblatt-mcp/
├── src/amtsblatt_mcp/
│   ├── rubrics.py       # Fail-closed green allow-list — the scope decision
│   ├── server.py        # FastMCP server, 5 tools, quirk guards, XML parsing
│   ├── _log.py          # Structured JSON logging + per-tool call events
│   ├── _middleware.py   # Bearer auth + sliding-window rate limit (SSE only)
│   └── _otel.py         # Optional OpenTelemetry wiring
├── tests/
│   ├── test_allowlist.py    # Data-protection invariants (own CI job)
│   ├── test_search.py       # Search, procurement, pagination, dedup, errors
│   ├── test_publication.py  # XML parsing, deadlines, egress allow-list
│   └── fixtures.py          # Anonymised real responses
├── docs/
│   ├── rubric-classification.md   # Why each of the 152 rubrics is open/closed
│   └── procurement-coverage.md    # Measured OB-* volume; why `active` is measured
├── scripts/
│   └── measure_procurement_coverage.py
├── Dockerfile · compose.yaml      # Hardened, non-root, read-only container
└── server.json                    # MCP registry manifest
```

## Changelog

See [CHANGELOG.md](CHANGELOG.md).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Changes to
[`src/amtsblatt_mcp/rubrics.py`](src/amtsblatt_mcp/rubrics.py) require an
explicit rationale in the PR description: releasing a rubric is a
data-protection decision, not a feature.

## Security

See [SECURITY.md](SECURITY.md) for reporting and operator hardening notes.

## License

MIT — see [LICENSE](LICENSE).

Data source: **amtsblattportal.ch**, operated by SECO / State Secretariat for
Economic Affairs on behalf of the Swiss Confederation. Freely usable, but
without warranty of completeness or accuracy. Only the signed PDF of a
publication is legally binding.

## Author

Hayal Oezkan · [malkreide](https://github.com/malkreide)

## Credits & Related Projects

Part of the **Swiss Public Data MCP Portfolio**:

- [`register-mcp`](https://github.com/malkreide/register-mcp) — Zefix commercial
  register with a company-UID join to the gazettes

<!-- mcp-name: io.github.malkreide/amtsblatt-mcp -->

