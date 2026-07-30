"""Source health, so a degraded upstream is distinguishable from an empty result.

Extracted from `server.py` for `ARCH-011`.

At the tool layer those two look identical, which is why every empty search
result points here. This tool probes the endpoints directly and reports cache age
alongside, so "nothing matched" can be separated from "the source is not
answering" without guessing from prose.
"""

from __future__ import annotations

from time import monotonic
from typing import Any

from .. import __version__
from .._app import mcp
from .._envelope import _json_out, _md
from .._http import _get_client
from .._log import logged_tool
from .._taxonomy import rubrics_cache_state
from ..constants import GAZETTE_BASE, ResponseFormat
from ..inputs import StatusInput
from ..rubrics import GREEN_RUBRICS, GREEN_SUB_RUBRICS, RED_RUBRICS


async def _probe_endpoint(url: str) -> dict:
    """Lightweight reachability probe: reports reachable/status/latency."""
    start = monotonic()
    try:
        r = await _get_client().get(url)
        r.raise_for_status()
        return {
            "reachable": True,
            "status": r.status_code,
            "latency_ms": int((monotonic() - start) * 1000),
        }
    except Exception as e:
        return {
            "reachable": False,
            "error": type(e).__name__,
            "latency_ms": int((monotonic() - start) * 1000),
        }


def _cache_age(cache: tuple[float, Any] | None) -> str:
    if not cache:
        return "nicht geladen"
    age = int(monotonic() - cache[0])
    if age < 90:
        return f"{age}s"
    if age < 5400:
        return f"{age // 60}min"
    return f"{age // 3600}h"


@mcp.tool(
    name="gazette_source_status",
    annotations={
        "title": "Erreichbarkeit der Quelle + Cache-Alter",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
@logged_tool("gazette_source_status")
async def gazette_source_status(params: StatusInput) -> str:
    """<use_case>Check whether amtsblattportal.ch is reachable and what the released scope is. Call this when a search returns nothing and you need to distinguish an empty result from a source that could not be asked — the two are not the same answer.</use_case>

    Status des Amtsblattportals, Cache-Alter und Umfang der Freigabe-Liste.

    Prüft die Erreichbarkeit des Upstreams, meldet das Alter des
    Taxonomie-Caches und wie viele Rubriken erschlossen sind.

    Args:
        params (StatusInput):
            - response_format (str): 'markdown' oder 'json'

    Returns:
        str: Erreichbarkeit, Latenz, Cache-Alter und Scope-Kennzahlen.
    """
    probe = await _probe_endpoint(f"{GAZETTE_BASE}/rubrics")
    payload = {
        "gazette": {**probe, "base": GAZETTE_BASE},
        "rubrics_cache_age": _cache_age(rubrics_cache_state()),
        "scope": {
            "green_rubrics": len(GREEN_RUBRICS),
            "green_sub_rubrics": len(GREEN_SUB_RUBRICS),
            "documented_red_rubrics": len(RED_RUBRICS),
            "policy": "fail-closed allow-list",
        },
        "version": __version__,
    }

    if params.response_format == ResponseFormat.JSON:
        return _json_out(payload, "live_api")

    icon = "✅" if probe["reachable"] else "❌"
    lines = [
        "## Quellen-Status",
        "",
        "| Feld | Wert |",
        "|------|------|",
        f"| **Amtsblattportal** | {icon} {probe['latency_ms']}ms |",
        f"| **Basis-URL** | {GAZETTE_BASE} |",
        f"| **Taxonomie-Cache** | {_cache_age(rubrics_cache_state())} |",
        f"| **Freigegebene Rubriken** | {len(GREEN_RUBRICS)} "
        f"(+ {len(GREEN_SUB_RUBRICS)} Subrubriken) |",
        "| **Policy** | fail-closed Allow-List |",
        f"| **Version** | {__version__} |",
    ]
    if not probe["reachable"]:
        lines += [
            "",
            f"> ⚠️ Quelle nicht erreichbar ({probe.get('error')}). Suchanfragen "
            "liefern derzeit einen Fehler — **kein** leeres Ergebnis.",
        ]
    return _md(lines, "live_api")
