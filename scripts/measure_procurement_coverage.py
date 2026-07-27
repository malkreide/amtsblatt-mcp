#!/usr/bin/env python3
"""Measure how much each `OB-*` procurement rubric still publishes.

`PROCUREMENT_RUBRICS["<canton>"]["active"]` in `amtsblatt_mcp.server` is a
MEASURED fact, not one read off the rubric label. Three of the six labels
announce their own retirement ("über Simap importiert", "I N A K T I V"), but
OB-BS does not — its label is a plain "Öffentliches Beschaffungswesen" while its
volume collapsed from 1 149 (2022) to 2 (2026 YTD). A server that trusted the
label would have kept sweeping a dead rubric, exactly as it did for OB-ZG before
v0.1.3.

Run this before changing an `active` flag, and refresh
`docs/procurement-coverage.md` from its output.

    python scripts/measure_procurement_coverage.py [--since 2021] [--json]

Read-only; hits only amtsblattportal.ch.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date

import httpx

BASE = "https://amtsblattportal.ch/api/v1"
RUBRICS = ("OB-AR", "OB-BS", "OB-BL", "OB-TI", "OB-VS", "OB-ZG")
# A rubric publishing fewer than this in the current year is a candidate for
# active=False. Deliberately a hint for the reader, not an automatic switch —
# flipping the flag stays a reviewed decision.
ACTIVE_HINT_THRESHOLD = 20


def _count(client: httpx.Client, rubric: str, start: str, end: str) -> int:
    r = client.get(
        f"{BASE}/publications",
        params={
            "publicationStates": "PUBLISHED",
            "rubrics": rubric,
            "publicationDate.start": start,
            "publicationDate.end": end,
            "pageRequest.size": 1,
        },
    )
    r.raise_for_status()
    return int(r.json().get("total") or 0)


def _latest(client: httpx.Client, rubric: str) -> str | None:
    r = client.get(
        f"{BASE}/publications",
        params={
            "publicationStates": "PUBLISHED",
            "rubrics": rubric,
            "pageRequest.size": 1,
        },
    )
    r.raise_for_status()
    content = r.json().get("content") or []
    if not content:
        return None
    return (content[0].get("meta", {}).get("publicationDate") or "")[:10] or None


def _labels(client: httpx.Client) -> dict[str, str]:
    """Rubric display names — the very field that must NOT drive the decision."""
    r = client.get(f"{BASE}/rubrics", params={"lang": "de"})
    r.raise_for_status()
    payload = r.json()
    rows = payload if isinstance(payload, list) else payload.get("content") or []
    out: dict[str, str] = {}
    for row in rows:
        code = row.get("code") or row.get("id")
        name = row.get("name")
        if isinstance(name, dict):
            name = name.get("de")
        if code:
            out[str(code)] = name or ""
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--since", type=int, default=2021, help="first year to count")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    today = date.today()
    years = list(range(args.since, today.year + 1))
    result: dict[str, dict] = {}

    with httpx.Client(timeout=30.0, headers={"Accept": "application/json"}) as client:
        labels = _labels(client)
        for rubric in RUBRICS:
            per_year = {
                y: _count(client, rubric, f"{y}-01-01", f"{y}-12-31") for y in years
            }
            result[rubric] = {
                "per_year": per_year,
                "latest": _latest(client, rubric),
                "label": labels.get(rubric, ""),
                "current_year": per_year[today.year],
                "active_hint": per_year[today.year] >= ACTIVE_HINT_THRESHOLD,
            }

    if args.json:
        print(json.dumps({"measured_at": today.isoformat(), "rubrics": result},
                         ensure_ascii=False, indent=2))
        return 0

    header = "| Rubrik | " + " | ".join(str(y) for y in years) + " | Letzte | active? |"
    print(f"Gemessen am {today.isoformat()} (publicationStates=PUBLISHED)\n")
    print(header)
    print("|" + "---|" * (len(years) + 3))
    for rubric, row in result.items():
        counts = " | ".join(f"{row['per_year'][y]:,}".replace(",", " ") for y in years)
        hint = "ja" if row["active_hint"] else "**nein**"
        print(f"| `{rubric}` | {counts} | {row['latest'] or '—'} | {hint} |")

    print("\nRubrik-Labels (bewusst NICHT entscheidungsrelevant):")
    for rubric, row in result.items():
        print(f"  {rubric}: {row['label']}")
    print(
        f"\nHinweis: «active? nein» ab <{ACTIVE_HINT_THRESHOLD} Publikationen im "
        "laufenden Jahr. Das ist ein Prüfhinweis, keine automatische Umstellung — "
        "PROCUREMENT_RUBRICS bleibt eine bewusste Entscheidung."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
