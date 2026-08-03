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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="machine-readable output")
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

    by_class: dict[str, list[str]] = {"green": [], "red": [], "unclassified": []}
    for code in counts:
        by_class[_classify(code)].append(code)
    totals = {k: sum(counts[c] for c in v) for k, v in by_class.items()}
    reachable = totals["green"] + sum(subs.values())
    summed = sum(counts.values())

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
