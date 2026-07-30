"""Full-text retrieval, and the second half of the scope gate.

Extracted from `server.py` for `ARCH-011`.

`_fetch_publication_gated` is where the green allow-list is enforced *after* the
fetch as well as before it. That is not belt-and-braces for its own sake: an id
arrives from the caller rather than from a rubric filter, so the only way to know
which rubric a publication belongs to is to fetch it and look. A blocked rubric
gets the scope explanation instead of the content.
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from typing import Any

from .._app import mcp
from .._envelope import _handle_error, _json_out, _md, _note
from .._http import _get_text
from .._log import log_event, logged_tool
from .._normalise import _days_remaining, _format_deadline, _iso_date, _pick_language
from .._xml import _parse_publication_xml
from ..constants import GAZETTE_WEB, PROCUREMENT_SUB_RUBRIC_CODES, ResponseFormat
from ..inputs import PublicationInput
from ..rubrics import explain_blocked, is_green


async def _fetch_publication_gated(pub_id: str) -> tuple[dict[str, Any] | None, str | None]:
    """Fetch, parse and green-gate one publication.

    Returns `(parsed, None)` when the document may be shown, or `(None, message)`
    when it must not be — either because the fetch or parse failed, or because
    the rubric turned out to be blocked.

    This exists as a shared helper rather than inline code because two tools now
    reach publication content: `gazette_get_publication` and the aggregated
    `gazette_search_detailed`. The post-fetch gate is the control that keeps
    person-data rubrics unreachable, and a control that holds in one path but
    not the other is worse than none — it looks enforced.

    The gate is post-fetch by necessity: a publication id is opaque, so the
    rubric can only be checked once the document is in hand.
    """
    try:
        xml_text = await _get_text(f"/publications/{pub_id}/xml")
    except Exception as e:
        return None, _handle_error(e)

    try:
        parsed = _parse_publication_xml(xml_text)
    except ET.ParseError as e:
        return None, _note(
            f"Fehler: XML der Publikation {pub_id} konnte nicht geparst werden ({e}).",
            "degraded",
        )

    meta = parsed["meta"]
    rubric = meta.get("rubric")
    sub_rubric = meta.get("subRubric")
    if rubric and not (is_green(rubric) or (sub_rubric and is_green(sub_rubric))):
        log_event(
            logging.WARNING,
            "blocked_publication_requested",
            rubric=rubric,
            publication_id=pub_id,
        )
        return None, _note(explain_blocked(rubric, kind="rubric"), "refused")

    return parsed, None


# ---------------------------------------------------------------------------
# Tool: gazette_get_publication
# ---------------------------------------------------------------------------


@mcp.tool(
    name="gazette_get_publication",
    annotations={
        "title": "Einzelpublikation inkl. amtlichem Volltext",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
@logged_tool("gazette_get_publication")
async def gazette_get_publication(params: PublicationInput) -> str:
    """<use_case>Retrieve the full text of one publication once you have its id from a search. Refuses ids whose rubric is not released, after fetching — the rubric is not knowable from the id alone.</use_case>

    Einzelne Publikation inkl. amtlichem Volltext (aus dem XML, defensiv geparst).

    Die Listen-API liefert nur Metadaten — der eigentliche Inhalt steht
    ausschliesslich im rubrikspezifischen XML unter `/publications/{id}/xml`.
    Das Schema ist pro Subrubrik verschieden; Pflichtfelder sind meta und der
    Publikationstext, bei HR-Rubriken zusätzlich die Firmenangaben. Alles
    Übrige landet best-effort in `additional_fields`.

    Nach dem Abruf wird die Rubrik der Publikation erneut gegen die
    Freigabe-Liste geprüft: eine ID aus einer gesperrten Rubrik liefert die
    Scope-Erklärung statt des Inhalts.

    Args:
        params (PublicationInput):
            - id (str): Publikations-ID (UUID)
            - response_format (str): 'markdown' oder 'json'

    Returns:
        str: Volltext, Metadaten, allfällige Eingabefrist und Zusatzfelder.
    """
    parsed, refusal = await _fetch_publication_gated(params.id)
    if refusal is not None:
        return refusal
    assert parsed is not None  # refusal is None ⇒ parsed is set

    meta = parsed["meta"]
    rubric = meta.get("rubric")
    sub_rubric = meta.get("subRubric")

    if params.response_format == ResponseFormat.JSON:
        payload = {**parsed}
        if parsed.get("deadline"):
            payload["days_remaining"] = _days_remaining(parsed["deadline"])
        return _json_out(payload, "live_api")

    title = _pick_language(meta.get("title"))
    lines = [
        f"## {title or 'Publikation'}",
        "",
        "| Feld | Wert |",
        "|------|------|",
        f"| **ID** | `{meta.get('id', params.id)}` |",
        f"| **Rubrik** | {rubric or '?'} / {sub_rubric or '?'} |",
        f"| **Datum** | {_iso_date(meta.get('publicationDate')) or '—'} |",
        f"| **Publ.-Nr.** | {meta.get('publicationNumber', '—')} |",
    ]
    ro = meta.get("registrationOffice")
    if isinstance(ro, dict):
        ro = ro.get("displayName")
    if ro:
        lines.append(f"| **Amt** | {ro} |")
    simap_ref = parsed.get("simap_publication_number")
    if simap_ref:
        lines.append(f"| **simap-Publikation** | `{simap_ref}` (Zweitpublikation) |")
    if parsed.get("deadline"):
        lines.append(f"| **Frist** | {_format_deadline(parsed['deadline'])} |")
    lines.append(f"| **Quelle** | {GAZETTE_WEB}/{meta.get('id', params.id)} |")
    lines.append("")

    company = parsed.get("company") or {}
    if company:
        lines.append("### Firma")
        for key in ("name", "uid", "seat", "legalForm"):
            if company.get(key):
                lines.append(f"- **{key}:** {company[key]}")
        addr = company.get("address")
        if isinstance(addr, dict):
            lines.append(f"- **address:** {' '.join(str(v) for v in addr.values() if v)}")
        elif addr:
            lines.append(f"- **address:** {addr}")
        lines.append("")

    if parsed.get("publicationText"):
        lines += ["### Amtlicher Text", parsed["publicationText"], ""]

    extra = parsed.get("additional_fields") or {}
    if extra:
        lines.append(f"_Zusatzfelder: {', '.join(sorted(extra.keys()))}_")

    if simap_ref:
        lines += [
            "",
            f"_Diese Publikation stammt von simap.ch (Nr. {simap_ref}) und ist hier "
            "eine Zweitpublikation. Der Originaldatensatz — mit CPV- und BKP-Codes, "
            "Zuschlägen und Publikationsverlauf — liegt in `swiss-procurement-mcp`._",
        ]
    elif rubric and (
        rubric.startswith("OB-") or (sub_rubric or "") in PROCUREMENT_SUB_RUBRIC_CODES
    ):
        lines += [
            "",
            "_Diese Beschaffungspublikation trägt keine simap-Nummer, existiert also "
            "nur im Amtsblattportal und ist über `swiss-procurement-mcp` nicht "
            "auffindbar._",
        ]

    return _md(lines, "live_api")


# ---------------------------------------------------------------------------
# Tool: gazette_list_rubrics
