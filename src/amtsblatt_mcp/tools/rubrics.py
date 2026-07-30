"""The taxonomy tool — what exists, and what this server will serve.

Extracted from `server.py` for `ARCH-011`.

This is the tool that lets a caller tell "no such publication" apart from "that
rubric is deliberately not served", which is why the empty-result note of every
search points at it. With `rubric_class='all'` the blocked rubrics appear *with
their reason*, so the scope decision is inspectable rather than merely enforced.
Being listed is not the same as being queryable; only green is.
"""

from __future__ import annotations

from .._app import mcp
from .._envelope import _handle_error, _json_out, _md
from .._log import logged_tool
from .._normalise import _pick_language, _to_bool
from .._taxonomy import _fetch_rubrics
from ..constants import ResponseFormat, RubricClass
from ..inputs import RubricsInput
from ..rubrics import RED_RUBRICS, YELLOW_RUBRICS, classify, is_green

_CLASS_ICON = {"green": "🟢", "yellow": "🟡", "red": "🔴", "unclassified": "⚪"}


@mcp.tool(
    name="gazette_list_rubrics",
    annotations={
        "title": "Rubriken auflisten (mit Ampel-Klassierung)",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
@logged_tool("gazette_list_rubrics")
async def gazette_list_rubrics(params: RubricsInput) -> str:
    """<use_case>Discover which rubrics exist and which this server serves, before searching. Call this when a search returns nothing to tell "no such publications" apart from "that rubric is deliberately not served".</use_case>

    Rubrik-Taxonomie des Amtsblattportals mit Ampel-Klassierung.

    Voraussetzung für gültige Filter: Rubrik-Codes werden in den Such-Tools
    gegen diese Taxonomie UND gegen die Freigabe-Liste validiert. Standardmässig
    werden nur die erschlossenen («grünen») Rubriken gezeigt.

    Mit `rubric_class='all'` erscheint die vollständige Taxonomie inklusive der
    gesperrten Rubriken mit Begründung — zur Transparenz über den Scope-Entscheid.
    Aufgeführt zu sein bedeutet nicht durchsuchbar zu sein; nur 🟢 ist abfragbar.

    Args:
        params (RubricsInput):
            - language (str): 'de', 'fr', 'it', 'en'
            - rubric_class (str): 'green' (Standard) oder 'all'
            - response_format (str): 'markdown' oder 'json'

    Returns:
        str: Rubriken mit Code, Name, Ampel-Klasse und Subrubriken.
    """
    try:
        rubrics_data, from_cache = await _fetch_rubrics()
    except Exception as e:
        return _handle_error(e)

    provenance = "cached" if from_cache else "live_api"
    lang = params.language
    green_only = params.rubric_class == RubricClass.GREEN

    entries = []
    for r in rubrics_data:
        if not isinstance(r, dict):
            continue
        code = r.get("code")
        if not code:
            continue
        klass = classify(code)
        if green_only and klass != "green":
            continue
        subs = [s for s in (r.get("subRubrics") or []) if isinstance(s, dict)]
        entries.append(
            {
                "code": code,
                "name": _pick_language(r.get("name"), lang) or "",
                "class": klass,
                "active": _to_bool(r.get("active"), default=True),
                "reason": RED_RUBRICS.get(code) or YELLOW_RUBRICS.get(code),
                "subRubrics": [
                    {
                        "code": s.get("code"),
                        "name": _pick_language(s.get("name"), lang) or "",
                        "queryable": is_green(s.get("code") or "") or klass == "green",
                    }
                    for s in subs
                ],
            }
        )
    entries.sort(key=lambda e: e["code"])

    if params.response_format == ResponseFormat.JSON:
        return _json_out(
            {
                "count": len(entries),
                "filter": params.rubric_class.value,
                "queryable_note": "Nur Rubriken der Klasse 'green' sind durchsuchbar.",
                "rubrics": entries,
            },
            provenance,
        )

    heading = "Erschlossene Rubriken" if green_only else "Rubriken (vollständige Taxonomie)"
    lines = [f"## {heading}", f"Total: **{len(entries)}**", ""]
    if green_only:
        lines += [
            "_Nur Rubriken ohne systematische Personendaten. "
            "`rubric_class='all'` zeigt auch die gesperrten mit Begründung._",
            "",
        ]
    for e in entries:
        icon = _CLASS_ICON.get(e["class"], "⚪")
        suffix = "" if e["active"] else " _(inaktiv)_"
        lines.append(f"### {icon} `{e['code']}` — {e['name']}{suffix}")
        if e["reason"] and e["class"] != "green":
            lines.append(f"_Nicht durchsuchbar: {e['reason']}._")
        for s in e["subRubrics"]:
            lines.append(f"- `{s['code']}` — {s['name']}")
        lines.append("")
    return _md(lines, provenance)


# ---------------------------------------------------------------------------
# Tool: gazette_source_status
