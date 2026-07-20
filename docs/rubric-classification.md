# Rubric classification — audit trail

> **Snapshot:** live `/rubrics` taxonomy of **2026-07-20** — 152 top-level
> rubrics, 825 sub-rubrics, 29 tenants.
> **Source of truth in code:** [`src/amtsblatt_mcp/rubrics.py`](../src/amtsblatt_mcp/rubrics.py)

This document records *why* each rubric is or is not queryable. It exists so
the scope decision is reviewable rather than buried in a `frozenset`.

## The rule

`amtsblatt-mcp` operates a **fail-closed green allow-list**:

1. A rubric that is not *explicitly* green is not queryable. New rubrics
   appearing upstream are closed by default.
2. No person-based search parameter exists in any tool signature — no name,
   birth date or residential address.
3. No persistence of publication content. Pass-through only.
4. A blocked rubric yields a clear explanatory message — never a silent empty
   result, and never a circumvention hint.

## Coverage

| Class | Count | Queryable |
|---|---:|---|
| 🟢 green | 49 rubrics + 4 sub-rubrics | **yes** |
| 🔴 red | 56 | no — systematic natural-person data |
| 🟡 yellow | 47 | no — deferred until explicitly released |
| ⚪ unclassified | 0 | no — blocked by default |

All 152 live rubrics carry an explicit classification. `test_every_live_rubric_is_explicitly_classified`
fails when the upstream taxonomy grows, which is the prompt to classify the new
code deliberately rather than letting it sit on the implicit default.

## Deviation 1 — globs are expanded to literal codes

The source proposal's traffic-light table uses glob notation (`KA-*`, `RS-*`,
`RE-*`, `PR-*`, `RP-*`). Transcribing those globs into code would **violate the
proposal's own rule 1**: a future upstream rubric matching `RS-*` would
auto-green itself without review. Every glob is therefore expanded against the
2026-07-20 taxonomy into explicit literal codes, and
`test_green_set_is_literal_codes_not_globs` enforces that no wildcard survives.

Consequence: adding a rubric is always a deliberate, reviewable commit.

## Deviation 2 — three documented extensions to the green set

Expanding the globs exposed gaps where the proposal's *prose* and its *table*
disagree. These were released after explicit review:

| Added | Rubrics | Rationale |
|---|---|---|
| `KO-*` | `KO-AR`, `KO-BE`, `KO-BS`, `KO-TI`, `KO-ZG`, `KO-ZH` | "Weitere **kommunale** Bekanntmachungen" — the municipal twin of the green `KA-*`. The proposal's prose reads "Kantonale/kommunale Bekanntmachungen" but its table lists only `KA-*`. Institutional content. |
| `PL-BL` | `PL-BL` | Basel-Landschaft spells *Politische Rechte* `PL-`, not `PR-`. The table's `PR-*` row silently excluded one canton's political-rights rubric. |
| `VE-*` | `VE-AR`, `VE-BE`, `VE-BS`, `VE-TI`, `VE-ZG`, `VE-ZH` | *Umwelt, Verkehr und Energie* — institutional infrastructure notices, comparable in character to the green `RP-*` (Raumplanung). Not mentioned in the table in either direction. |

## Deviation 3 — red entries the source table did not cover

Fail-closed already blocked these, but *silently*. They are now explicitly red
so the user receives a reason:

| Rubric | Why it matters |
|---|---|
| `AA-GR` | Graubünden's *Meldungskatalog* bundles Testamentseröffnung, Erbenaufruf, gerichtliche Vorladung **and** Baugesuch into one rubric whose code matches none of the table's red prefixes. Highest-priority gap found. |
| `BU-NW`, `BU-OW`, `BU-SH`, `BU-SO`, `BU-SZ`, `BU-VS` | *Bürgerrecht, Steuer- und Zivilstandswesen* — six cantons merge into one rubric what other cantons split into the (classified) `BV-*`, `FZ-*` and `SW-*`. |
| `GR-BL`, `GR-BS` | *Grundbuch* — Handänderungen name natural owners. |
| `SJ-BE` | *Staats- und Jugendanwaltschaft* — prosecution and juvenile justice. |

## The sub-rubric special case

Four procurement sub-rubrics are green while their **parent stays blocked**:

| Green sub-rubric | Blocked parent | Parent's content |
|---|---|---|
| `AR-NW40` | `AR-NW` | Wirtschaft, Arbeit und Bildung (mixed) |
| `AR-OW40` | `AR-OW` | Wirtschaft und Arbeit (mixed) |
| `AR-VS40` | `AR-VS` | Wirtschaft, Arbeit und Bildung (mixed) |
| `BA-SH40` | `BA-SH` | Bau/Raum/Verkehr — contains Baugesuche |

A search on one of these must **never** have its parent injected alongside it.
`test_green_sub_rubric_search_does_not_inject_its_blocked_parent` guards this.

## Where the boundary with `register-mcp` runs

`register-mcp` deliberately keeps *full* rubric access — including a firm's own
`KK`/`SB` — but only ever keyed on a company **UID**. A firm's bankruptcy is
corporate data, not natural-person profiling, and UID scoping makes name-based
enumeration impossible.

`amtsblatt-mcp` has the opposite shape: broad search, narrow rubrics. It
therefore does **not** expose the upstream `uids` parameter at all — admitting
it would create a second UID entry point whose scope this server does not
govern. `FORBIDDEN_GAZETTE_PARAMS` encodes that.

## Re-verifying this snapshot

```bash
curl -s 'https://amtsblattportal.ch/api/v1/rubrics' \
  | python -c "import json,sys; print(len(json.load(sys.stdin)))"
```

If the count differs from 152, diff the live codes against the union of the
three sets in `rubrics.py` and classify anything new. Until that happens the
new rubric is blocked — which is the intended behaviour, not a bug.
