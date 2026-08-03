#!/usr/bin/env python3
"""Measure which part of the Amtsblattportal corpus this server can reach.

`docs/rubric-classification.md` records *why* each rubric is green or blocked.
It does not record *how much* each decision covers, and that is the number a
scope justification needs. Without it, «Konkurse are out of scope» and «Konkurse
are not in the source» read the same in a review — the first is a decision, the
second is wrong, and only a measurement tells them apart.

The axis comes from the source, not from `rubrics.py`: `/rubrics` is enumerated
in full and the green set is marked *into* it. Deriving the list from the code
could not, by construction, surface a rubric the classification overlooked.

    python scripts/measure_coverage_matrix.py           # table
    python scripts/measure_coverage_matrix.py --json    # machine-readable

Refresh `docs/coverage-matrix.md` from its output. One request per rubric plus
one for the taxonomy — read-only, hits only amtsblattportal.ch.

Procedure: `mcp-data-source-probe` 1.3b (Abdeckungs-Matrix).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amtsblatt_mcp.rubrics import GREEN_RUBRICS, GREEN_SUB_RUBRICS, RED_RUBRICS  # noqa: E402

BASE = "https://amtsblattportal.ch/api/v1"

# Without this parameter the endpoint answers HTTP 401 AccessDeniedException,
# not an empty page. A caller that reads `content` without checking the status
# code sees zero hits and takes them for a statement about the corpus.
REQUIRED_STATE = "PUBLISHED"

SNAPSHOT = Path(__file__).resolve().parents[1] / "docs" / "coverage-matrix.json"

# Sub-rubric names that mark systematic natural-person data. Used ONLY to sort
# unclassified rubrics into "look here first" and "probably harmless" — never to
# grant or deny access. Absence of a marker is not a clearance: the decision is
# made on the content of a publication, not on the wording of a label, exactly
# as `PROCUREMENT_RUBRICS["active"]` is measured rather than read off the label.
PERSON_DATA_MARKERS = (
    "baugesuch",
    "betreibung",
    "bürgerrecht",
    "einbürgerung",
    "erbschaft",
    "erben",
    "grundbuch",
    "handänderung",
    "konkurs",
    "nachlass",
    "schuldenruf",
    "testament",
    "todesfall",
    "vorladung",
    "zivilstand",
    "ableben",
    "ausländerrecht",
)


def _taxonomy(client: httpx.Client) -> list[dict]:
    r = client.get(f"{BASE}/rubrics")
    r.raise_for_status()
    payload = r.json()
    rows = payload if isinstance(payload, list) else payload.get("content") or []
    if not rows:
        raise SystemExit("empty /rubrics response — shape changed, not an empty taxonomy")
    if "code" not in rows[0]:
        raise SystemExit(f"no 'code' in the first rubric — keys: {sorted(rows[0])[:8]}")
    return rows


def _count(
    client: httpx.Client, *, rubric: str | None = None, sub_rubric: str | None = None
) -> int:
    params: dict[str, object] = {"publicationStates": REQUIRED_STATE, "pageRequest.size": 1}
    if rubric:
        params["rubrics"] = rubric
    if sub_rubric:
        params["subRubrics"] = sub_rubric
    r = client.get(f"{BASE}/publications", params=params)
    r.raise_for_status()
    payload = r.json()
    if "total" not in payload:
        raise SystemExit(f"no 'total' in the response — keys: {sorted(payload)[:8]}")
    return int(payload["total"] or 0)


def _classify(code: str) -> str:
    if code in GREEN_RUBRICS:
        return "green"
    if code in RED_RUBRICS:
        return "red"
    return "unclassified"


def _sub_names(row: dict) -> list[str]:
    out = []
    for sub in row.get("subRubrics") or []:
        name = sub.get("name")
        out.append(name.get("de", "") if isinstance(name, dict) else str(name or ""))
    return [n for n in out if n]


def _markers(sub_names: list[str]) -> list[str]:
    """Sub-rubric names carrying a person-data marker. Evidence, not a verdict."""
    return [n for n in sub_names if any(mark in n.lower() for mark in PERSON_DATA_MARKERS)]


def _triage(rows: list[dict], counts: dict[str, int]) -> int:
    """Sort the unclassified rubrics by whether their sub-rubrics mention persons."""
    unclassified = [r for r in rows if _classify(r["code"]) == "unclassified"]
    unclassified.sort(key=lambda r: -counts[r["code"]])
    flagged, clear = [], []
    for row in unclassified:
        hits = _markers(_sub_names(row))
        (flagged if hits else clear).append((row, hits))

    print(
        f"{len(unclassified)} unklassifizierte Rubriken, {sum(counts[r['code']] for r in unclassified):,} Publikationen\n"
    )
    print(f"## Personendaten-Marker in einer Sub-Rubrik — {len(flagged)} Rubriken\n")
    for row, hits in flagged:
        code = row["code"]
        print(f"  {code:<8} {counts[code]:>8,}  {hits[0][:52]}")
    print(f"\n## Kein Marker — {len(clear)} Rubriken, Kandidaten für eine Prüfung\n")
    for row, _ in clear[:15]:
        code = row["code"]
        subs = ", ".join(_sub_names(row)[:3])
        print(f"  {code:<8} {counts[code]:>8,}  {subs[:60]}")
    if len(clear) > 15:
        rest = sum(counts[r["code"]] for r, _ in clear[15:])
        print(f"  … {len(clear) - 15} weitere, zusammen {rest:,} Publikationen")
    print(
        "\nDas ist Evidenz, kein Urteil. Ein fehlender Marker ist keine Freigabe: "
        "Entschieden wird am Inhalt einer Publikation, nicht am Wortlaut eines Labels. "
        "Die Freigabe bleibt eine Änderung an GREEN_RUBRICS mit Review."
    )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument(
        "--triage",
        action="store_true",
        help="sort the unclassified rubrics by person-data markers in their sub-rubrics",
    )
    ap.add_argument(
        "--write-snapshot",
        action="store_true",
        help=f"refresh {SNAPSHOT.name} — the axis the live drift test compares against",
    )
    args = ap.parse_args()

    with httpx.Client(timeout=30.0, headers={"Accept": "application/json"}) as client:
        rows = _taxonomy(client)
        corpus = _count(client)
        counts = {row["code"]: _count(client, rubric=row["code"]) for row in rows}
        subs = {code: _count(client, sub_rubric=code) for code in sorted(GREEN_SUB_RUBRICS)}
        names = {
            row["code"]: (row.get("name") or {}).get("de", "")
            if isinstance(row.get("name"), dict)
            else str(row.get("name") or "")
            for row in rows
        }

    if args.triage:
        return _triage(rows, counts)

    by_class: dict[str, list[str]] = {"green": [], "red": [], "unclassified": []}
    for code in counts:
        by_class[_classify(code)].append(code)
    totals = {k: sum(counts[c] for c in v) for k, v in by_class.items()}
    reachable = totals["green"] + sum(subs.values())
    summed = sum(counts.values())

    if args.write_snapshot:
        # Codes and classes only — no counts. Counts move every day; the axis
        # does not, and it is the axis whose drift makes the matrix stale.
        SNAPSHOT.write_text(
            json.dumps(
                {
                    "measured_at": date.today().isoformat(),
                    "note": (
                        "Axis snapshot for tests/test_live.py. Refresh with "
                        "scripts/measure_coverage_matrix.py --write-snapshot and "
                        "update docs/coverage-matrix.md in the same commit."
                    ),
                    "rubrics": {code: _classify(code) for code in sorted(counts)},
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"{SNAPSHOT.relative_to(SNAPSHOT.parents[1])} geschrieben: {len(counts)} Rubriken")
        return 0

    result = {
        "measured_at": date.today().isoformat(),
        "corpus_total": corpus,
        "rubrics": len(counts),
        "reachable": reachable,
        "by_class": {
            k: {"rubrics": len(v), "publications": totals[k]} for k, v in by_class.items()
        },
        "green_sub_rubrics": subs,
        "counts": counts,
        "axis_partitions_corpus": summed == corpus,
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    print(f"Gemessen am {result['measured_at']} (publicationStates={REQUIRED_STATE})\n")
    print(f"Bestandsachse: {len(counts)} Top-Level-Rubriken aus /rubrics")
    if summed == corpus:
        print(f"Konsistenz: Summe über alle Rubriken == ungefilterter Gesamtwert ({corpus:,})\n")
    else:
        print(
            f"⚠️  Konsistenz: Summe {summed:,} != ungefilterter Gesamtwert {corpus:,} "
            f"(Differenz {summed - corpus:+,}) — die Achse partitioniert den Bestand NICHT\n"
        )

    print("| Klasse | Rubriken | Publikationen | Anteil |")
    print("|---|---:|---:|---:|")
    print(
        f"| erreichbar (grün + {len(subs)} Sub) | {len(by_class['green'])}+{len(subs)} "
        f"| {reachable:,} | {reachable / corpus:.1%} |"
    )
    for cls, label in (("red", "bewusst gesperrt"), ("unclassified", "noch offen")):
        n, v = len(by_class[cls]), totals[cls]
        print(f"| {label} | {n} | {v:,} | {v / corpus:.1%} |")
    print(f"| **gesamt** | **{len(counts)}** | **{corpus:,}** | 100 % |")

    print("\nGrösste gesperrte Rubriken:")
    for code in sorted(by_class["red"] + by_class["unclassified"], key=lambda c: -counts[c])[:10]:
        print(f"  {code:<8} {counts[code]:>9,}  {_classify(code):<13} {names.get(code, '')[:44]}")

    print(
        "\nJede gesperrte Rubrik braucht einen von drei Gründen (1.3b): bewusst ausserhalb "
        "des Scopes, technisch nicht erreichbar, oder noch offen. «unclassified» ist der "
        "dritte Fall — ein offener Befund, kein erledigter Punkt."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
