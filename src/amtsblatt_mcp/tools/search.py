"""The three search tools, and the rendering they share.

Extracted from `server.py` for `ARCH-011`. They sit together because they share
`_prepare_summaries` and `_render_results` — a caller comparing a plain search
against the procurement-scoped one should not get two different result layouts
for the same underlying records.

None of them widens a search term, deliberately: see `ARCH-003` in `SECURITY.md`
and the reasoning in `_matching`. `_render_results` takes the empty-result note
as a required argument so a fourth search tool added here cannot quietly fall
back to a generic line.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from .._app import mcp
from .._envelope import _handle_error, _json_out, _md, _note
from .._http import _search
from .._log import log_event, logged_tool
from .._matching import empty_note, match_type
from .._normalise import (
    _collapse_language_variants,
    _days_remaining,
    _iso_date,
    _language_mix,
    _language_note,
    _meta_summary,
    _pick_language,
    _to_bool,
)
from .._taxonomy import _validate_rubric_code
from ..constants import (
    CPV_RE,
    GAZETTE_MAX_LIMIT,
    PROCUREMENT_ACTIVE_CANTONS,
    PROCUREMENT_INACTIVE_CANTONS,
    PROCUREMENT_RUBRICS,
    PROCUREMENT_SUB_RUBRICS,
    ResponseFormat,
)
from ..inputs import DetailedSearchInput, ProcurementInput, SearchInput
from ..rubrics import GREEN_RUBRICS, explain_blocked, is_green
from .publication import _fetch_publication_gated

# ---------------------------------------------------------------------------
# Tool: gazette_search_publications
# ---------------------------------------------------------------------------


def _prepare_summaries(
    content: list[dict], lang: str, only_language: bool
) -> tuple[list[dict], dict[str, int], str | None]:
    """Shared post-processing for both search tools.

    Returns the result rows, the language mix and — when the set spans more
    than one language — the note explaining why the count can exceed the number
    of distinct notices.
    """
    summaries = [_meta_summary(i, lang) for i in content]
    if only_language:
        summaries = [s for s in summaries if s.get("language") == lang]
    summaries = _collapse_language_variants(summaries, lang)
    mix = _language_mix(summaries)
    return summaries, mix, _language_note(mix)


def _render_results(
    summaries: list[dict], heading: str, meta_line: str, no_match_note: str
) -> list[str]:
    """Shared Markdown rendering for both search tools.

    `no_match_note` has no default on purpose. It is what a caller gets instead
    of results, and ARCH-003 asks that it be actionable; a default would let the
    next search tool added here fall back to a generic line without anyone
    noticing. Three call sites is a cheap price for that.

    The match type is rendered into the meta line rather than left implicit in
    the count, because these tools return Markdown rather than a typed object —
    if it is not in the text, it does not reach the model.
    """
    lines = [f"## {heading}", f"{meta_line} | Treffertyp: `{match_type(len(summaries))}`", ""]
    if not summaries:
        lines.append(no_match_note)
    for s in summaries:
        cantons = s.get("cantons")
        canton_str = ", ".join(cantons) if isinstance(cantons, list) else (cantons or "—")
        lines += [
            f"- **{s.get('publicationDate') or '—'}** | {canton_str} · "
            f"{s.get('rubric') or '?'}/{s.get('subRubric') or '?'} | "
            f"{s.get('title') or '—'}",
            f"  ↳ ID: `{s.get('id')}` | Nr.: {s.get('publicationNumber') or '—'} "
            f"| Sprache: {s.get('language') or '—'} "
            f"| Amt: {s.get('registrationOffice') or '—'}",
            f"  ↳ Quelle: {s.get('url') or '—'}",
        ]
    return lines


@mcp.tool(
    name="gazette_search_publications",
    annotations={
        "title": "Amtsblatt-Publikationen suchen (freigegebene Rubriken)",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
@logged_tool("gazette_search_publications")
async def gazette_search_publications(params: SearchInput) -> str:
    """<use_case>Search the released gazette rubrics by keyword, rubric, canton and date — the general entry point when the question is "what was officially published about X?". Combine rubric with canton: a bare rubric filter is silently ignored upstream.</use_case>

    Sucht amtliche Publikationen im Amtsblattportal (SHAB + kantonale Amtsblätter).

    Durchsucht ausschliesslich die freigegebenen («grünen») Rubriken: Handels-
    register, öffentliche Beschaffung, kantonale und kommunale Bekanntmachungen,
    Beschlüsse und Rechtsetzung, politische Rechte, Raumplanung sowie Umwelt/
    Verkehr/Energie. Rubriken mit systematischen Personendaten — Konkurse,
    Schuldbetreibungen, Erbschaft, Zivilstand, gerichtliche Vorladungen,
    Baugesuche — sind bewusst nicht erschlossen und liefern eine Erklärung
    statt Daten. Ein Personennamen-Sucheinstieg existiert nicht.

    Ohne `rubric` werden alle freigegebenen Rubriken injiziert, sodass eine
    reine Stichwortsuche niemals eine gesperrte Rubrik erreichen kann.

    Args:
        params (SearchInput):
            - keyword (Optional[str]): Volltext-Suchbegriff
            - rubric / sub_rubric (Optional[str]): freigegebene Codes
            - canton (Optional[str]): Kantonskürzel
            - date_start / date_end (Optional[str]): Zeitraum YYYY-MM-DD
            - limit (int): 1–100 (Standard 20), page (int): 0-basiert
            - language (str): bevorzugte Sprache
            - only_language (bool): nur diese Sprachfassung
            - response_format (str): 'markdown' oder 'json'

    Hinweis zur Trefferzahl: Das Portal publiziert eine Bekanntmachung je Sprache
    als eigenen Datensatz mit eigener Publikationsnummer. Sprachfassungen mit
    identischem Titel werden zusammengefasst, übersetzte bleiben getrennt — die
    Trefferzahl kann daher über der Zahl verschiedener Bekanntmachungen liegen.
    `language_mix` weist die Verteilung aus, `only_language=True` erzwingt eine
    einzelne Sprachfassung.

    Returns:
        str: Trefferliste mit Datum, Kanton, Rubrik, Titel, Sprache, ID und URL.
    """
    # Green gate — before any network call, and before code validation, so a
    # blocked rubric never even reveals whether it exists upstream.
    for code, kind in ((params.rubric, "rubric"), (params.sub_rubric, "subRubric")):
        if code and not is_green(code):
            return _note(explain_blocked(code, kind=kind), "refused")

    try:
        if params.rubric:
            await _validate_rubric_code(params.rubric, "rubric")
        if params.sub_rubric:
            await _validate_rubric_code(params.sub_rubric, "subRubric")

        # No rubric given → inject the full green set. This is what makes a
        # keyword-only query fail-closed rather than corpus-wide.
        rubrics: Any = params.rubric or sorted(GREEN_RUBRICS)
        # A green sub-rubric lives under a BLOCKED parent, so the parent must
        # not be injected alongside it.
        if params.sub_rubric and not params.rubric:
            rubrics = None

        data = await _search(
            {
                "keyword": params.keyword,
                "rubrics": rubrics,
                "subRubrics": params.sub_rubric,
                "cantons": params.canton,
                "publicationDate.start": params.date_start,
                "publicationDate.end": params.date_end,
                "pageRequest.size": min(params.limit, GAZETTE_MAX_LIMIT),
                "pageRequest.page": params.page or None,
            }
        )
    except Exception as e:
        return _handle_error(e)

    content = data.get("content", []) or []
    total = data.get("total")
    summaries, mix, lang_note = _prepare_summaries(content, params.language, params.only_language)

    no_match = empty_note(
        keyword=params.keyword,
        rubric=params.rubric,
        sub_rubric=params.sub_rubric,
        canton=params.canton,
        date_start=params.date_start,
        date_end=params.date_end,
    )

    if params.response_format == ResponseFormat.JSON:
        return _json_out(
            {
                "count": len(summaries),
                "total": total,
                "page": params.page,
                "scope": "green_rubrics_only",
                "match_type": match_type(len(summaries)),
                "note": no_match if not summaries else None,
                "language_mix": mix,
                "warnings": [lang_note] if lang_note else [],
                "results": summaries,
            },
            "live_api",
        )

    scope = params.rubric or params.sub_rubric or "alle freigegebenen Rubriken"
    meta_line = f"Gefunden: **{len(summaries)}** (total: {total}) | Bereich: {scope}"
    lines = _render_results(summaries, "Amtsblatt-Suche", meta_line, no_match)
    if lang_note:
        lines = lines[:2] + ["", f"> ⚠️ {lang_note}"] + lines[2:]
    if isinstance(total, int) and total > len(summaries):
        lines += ["", f"_Weitere Treffer vorhanden — `page={params.page + 1}` abrufen._"]
    lines += ["", "_Volltext einer Publikation via `gazette_get_publication(id=…)`._"]
    return _md(lines, "live_api")


# ---------------------------------------------------------------------------
# Tool: gazette_search_detailed
# ---------------------------------------------------------------------------


@mcp.tool(
    name="gazette_search_detailed",
    annotations={
        "title": "Suchen und Volltexte in einem Aufruf holen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
@logged_tool("gazette_search_detailed")
async def gazette_search_detailed(params: DetailedSearchInput) -> str:
    """<use_case>Answer a question needing both the hit list and each hit's full text in one step. Prefer this over a search followed by N gazette_get_publication calls.</use_case>

    Sucht Publikationen UND liefert den Volltext der obersten Treffer — ein Aufruf.

    Aggregierter Einstieg für den häufigen Fall «finde Bekanntmachungen und zeig
    mir, was drinsteht». Ohne dieses Tool braucht dieselbe Frage 1 + N Aufrufe:
    einmal `gazette_search_publications`, dann `gazette_get_publication` je
    Treffer. Hier laufen die Detailabrufe **parallel**, die Wartezeit ist also
    die des langsamsten Einzelabrufs statt ihrer Summe.

    Filter und Semantik sind identisch mit `gazette_search_publications` —
    einschliesslich der Freigabeliste: ohne `rubric` werden alle freigegebenen
    Rubriken injiziert, und jeder abgerufene Volltext durchläuft dasselbe
    Post-Fetch-Green-Gate. Eine Publikation aus gesperrter Rubrik wird auch hier
    verworfen und nie gerendert.

    Für Ausschreibungen mit Volltext in einem Aufruf: `rubric='OB-<Kanton>'`
    setzen, z.B. `rubric='OB-TI'`. `gazette_search_procurement` bleibt der
    bequemere Einstieg, wenn nur die Trefferliste gebraucht wird — es kennt die
    Kanton-zu-Rubrik-Auflösung und die inaktiven Kantone.

    Wann stattdessen die Einzeltools:
    - Nur die Trefferliste gewünscht → `gazette_search_publications` (billiger).
    - Volltext zu einer bekannten ID → `gazette_get_publication`.
    - Mehr als 5 Volltexte → suchen und die gewünschten gezielt einzeln holen.

    Args:
        params (DetailedSearchInput):
            - top_n (int): Anzahl Volltexte (1–5, Standard 3)
            - übrige Felder: identisch zu `gazette_search_publications`

    Returns:
        str: Trefferliste plus Volltext der obersten `top_n` Publikationen.
    """
    # Same green gate as the plain search, before any network call.
    for code, kind in ((params.rubric, "rubric"), (params.sub_rubric, "subRubric")):
        if code and not is_green(code):
            return _note(explain_blocked(code, kind=kind), "refused")

    try:
        if params.rubric:
            await _validate_rubric_code(params.rubric, "rubric")
        if params.sub_rubric:
            await _validate_rubric_code(params.sub_rubric, "subRubric")

        rubrics: Any = params.rubric or sorted(GREEN_RUBRICS)
        if params.sub_rubric and not params.rubric:
            rubrics = None

        data = await _search(
            {
                "keyword": params.keyword,
                "rubrics": rubrics,
                "subRubrics": params.sub_rubric,
                "cantons": params.canton,
                "publicationDate.start": params.date_start,
                "publicationDate.end": params.date_end,
                "pageRequest.size": min(params.limit, GAZETTE_MAX_LIMIT),
                "pageRequest.page": params.page or None,
            }
        )
    except Exception as e:
        return _handle_error(e)

    content = data.get("content", []) or []
    total = data.get("total")
    summaries, mix, lang_note = _prepare_summaries(content, params.language, params.only_language)

    wanted = summaries[: params.top_n]
    ids = [s.get("id") for s in wanted if s.get("id")]

    # ARCH-007: bounded fan-out, run concurrently. Every one of these goes
    # through the same gate as the single-publication tool.
    gathered = await asyncio.gather(
        *(_fetch_publication_gated(pub_id) for pub_id in ids),
        return_exceptions=True,
    )

    details: list[dict[str, Any]] = []
    withheld: list[str] = []
    for pub_id, outcome in zip(ids, gathered):
        if isinstance(outcome, BaseException):
            withheld.append(pub_id)
            continue
        parsed, refusal = outcome
        if refusal is not None or parsed is None:
            withheld.append(pub_id)
            continue
        details.append({"id": pub_id, **parsed})

    log_event(
        logging.INFO,
        "aggregated_search",
        requested=len(ids),
        expanded=len(details),
        withheld=len(withheld),
    )

    no_match = empty_note(
        keyword=params.keyword,
        rubric=params.rubric,
        sub_rubric=params.sub_rubric,
        canton=params.canton,
        date_start=params.date_start,
        date_end=params.date_end,
    )

    if params.response_format == ResponseFormat.JSON:
        return _json_out(
            {
                "count": len(summaries),
                "total": total,
                "page": params.page,
                "scope": "green_rubrics_only",
                "match_type": match_type(len(summaries)),
                "note": no_match if not summaries else None,
                "language_mix": mix,
                "warnings": [lang_note] if lang_note else [],
                "results": summaries,
                "expanded": details,
                "withheld_ids": withheld,
            },
            "live_api",
        )

    scope = params.rubric or params.sub_rubric or "alle freigegebenen Rubriken"
    meta_line = (
        f"Gefunden: **{len(summaries)}** (total: {total}) | Bereich: {scope} | "
        f"Volltext: {len(details)} von {len(ids)} angefordert"
    )
    lines = _render_results(summaries, "Amtsblatt-Suche (mit Volltexten)", meta_line, no_match)
    if lang_note:
        lines = lines[:2] + ["", f"> ⚠️ {lang_note}"] + lines[2:]

    for detail in details:
        meta = detail["meta"]
        title = _pick_language(meta.get("title"))
        lines += [
            "",
            "---",
            "",
            f"### {title or 'Publikation'}",
            "",
            f"`{detail['id']}` · {meta.get('rubric') or '?'} / "
            f"{meta.get('subRubric') or '?'} · "
            f"{_iso_date(meta.get('publicationDate')) or '—'}",
            "",
            (detail.get("publicationText") or "").strip() or "_Kein Volltext im XML._",
        ]
        if detail.get("deadline"):
            remaining = _days_remaining(detail["deadline"])
            lines += ["", f"**Eingabefrist:** {detail['deadline']} ({remaining})"]

    if withheld:
        lines += [
            "",
            "---",
            "",
            f"> {len(withheld)} Publikation(en) konnten nicht im Volltext "
            "geliefert werden — nicht abrufbar oder aus einer gesperrten Rubrik. "
            "Die Trefferliste oben ist davon unberührt.",
        ]

    return _md(lines, "live_api")


# ---------------------------------------------------------------------------
# Tool: gazette_search_procurement
# ---------------------------------------------------------------------------


def _procurement_scope(
    canton: str | None, include_inactive: bool
) -> tuple[list[str], list[str], list[str]]:
    """Resolve the rubric AND sub-rubric codes for a procurement search.

    Returns (rubric_codes, sub_rubric_codes, warnings). An empty scope means
    the request cannot be served — the warnings then explain why, and no HTTP
    call is made.

    Sub-rubrics are kept apart from rubrics for two independent reasons. They
    must be sent as `subRubrics`, because their PARENT rubric is blocked and
    injecting it would open a rubric full of Baugesuche and Zivilstand entries.
    And they are the gazette-native procurement — the part that does not also
    exist on simap.ch — so a canton can have no active rubric and still have
    something worth returning (Wallis: `OB-VS` is a dead simap import, while
    `AR-VS40` is live and simap has none of it).
    """
    warnings: list[str] = []
    if canton:
        entry = PROCUREMENT_RUBRICS.get(canton)
        sub_entry = PROCUREMENT_SUB_RUBRICS.get(canton)
        subs = [sub_entry["sub_rubric"]] if sub_entry and _to_bool(sub_entry["active"]) else []
        if sub_entry and subs:
            warnings.append(f"{sub_entry['sub_rubric']}: {sub_entry['note']}.")

        if not entry:
            if subs:
                # No OB-* rubric, but a native sub-rubric — serve it rather than
                # sending the caller to simap for publications simap lacks.
                return [], subs, warnings
            warnings.append(
                f"Kanton {canton} führt keine Beschaffungsrubrik im Amtsblattportal. "
                f"Öffentliche Ausschreibungen des Kantons {canton} laufen in der Regel "
                "über simap.ch — eine separate Plattform ausserhalb dieser Quelle. "
                f"Beschaffungsrubriken existieren nur für: "
                f"{', '.join(PROCUREMENT_ACTIVE_CANTONS)} (aktiv) sowie "
                f"{', '.join(PROCUREMENT_INACTIVE_CANTONS)} (inaktiv)."
            )
            return [], [], warnings

        if not _to_bool(entry["active"]) and not include_inactive:
            warnings.append(
                f"Beschaffungsrubrik {entry['rubric']} ({canton}) ist inaktiv "
                f"({entry['note']}). Nur historische Daten. "
                "Mit include_inactive=True dennoch durchsuchen."
            )
            # An inactive rubric does not suppress a live sub-rubric.
            return [], subs, warnings

        if entry["note"]:
            warnings.append(f"{entry['rubric']}: {entry['note']}.")
        return [entry["rubric"]], subs, warnings

    codes = [
        v["rubric"]
        for v in PROCUREMENT_RUBRICS.values()
        if _to_bool(v["active"]) or include_inactive
    ]
    subs = [v["sub_rubric"] for v in PROCUREMENT_SUB_RUBRICS.values() if _to_bool(v["active"])]
    return codes, subs, warnings


@mcp.tool(
    name="gazette_search_procurement",
    annotations={
        "title": "Öffentliche Ausschreibungen / Submissionen suchen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
@logged_tool("gazette_search_procurement")
async def gazette_search_procurement(params: ProcurementInput) -> str:
    """<use_case>Find public tenders published in the gazette (Submissionen) — the procurement-specific entry point. Note only AR, BS, TI, ZG, BL and VS mirror tenders here; for full Swiss coverage including Zurich use swiss-procurement-mcp.</use_case>

    Sucht öffentliche Ausschreibungen (Beschaffungswesen/Submissionen).

    Beschaffung ist ausschliesslich eine KANTONALE Rubrik (`OB-<Kanton>`), nicht
    föderal. Nur wenige Kantone publizieren sie hier: AR und TI (aktiv) sowie
    BS, BL, VS, ZG (inaktiv — BS/BL/VS nur Archiv, ZG leer).

    WICHTIG — Spiegel vs. Original: Die `OB-*`-Rubriken sind praktisch
    vollständig Zweitpublikationen von simap.ch-Ausschreibungen (gemessen über
    den OB-TI-Jahrgang 2026: 92,1 % tragen eine simap-Publikationsnummer). Wer
    Beschaffung sucht, ist mit `swiss-procurement-mcp` an der Primärquelle
    besser bedient — alle 26 Kantone plus Bund, mit CPV- und BKP-Codes,
    Zuschlägen und Publikationsverlauf.

    Was es NUR hier gibt, sind die Beschaffungs-Subrubriken `AR-VS40` (Wallis,
    Zuschläge), `AR-OW40` (Obwalden) und `BA-SH40` (Schaffhausen) sowie die
    Ticiner Subrubrik `OB-TI65` («Avvisi di gara non CIAP»): keine davon trägt
    eine simap-Nummer. Kanton VS, OW und SH liefern deshalb Treffer, obwohl sie
    keine aktive `OB-*`-Rubrik haben. Die meisten Kantone —
    inklusive **Zürich** —
    publizieren Ausschreibungen über simap.ch, das NICHT Teil dieser Quelle ist;
    eine Abfrage für einen solchen Kanton liefert eine Erklärung statt eines
    leeren Ergebnisses. Die Quelle kennt keine CPV-Codes.

    Args:
        params (ProcurementInput):
            - keyword (Optional[str]): Freitext (kein CPV-Code)
            - canton (Optional[str]): Kantonskürzel; ohne Angabe alle aktiven
            - date_start / date_end (Optional[str]): Zeitraum YYYY-MM-DD
            - include_inactive (bool): inaktive Rubriken (BL/BS/VS/ZG) einbeziehen
            - limit (int): 1–100 (Standard 20), page (int): 0-basiert
            - language (str), only_language (bool), response_format (str)

    Hinweis zur Trefferzahl: Ticino publiziert überwiegend it/fr, Appenzell A.Rh.
    de/fr — je Sprache ein eigener Datensatz mit eigener Publikationsnummer.
    Identische Titel werden zusammengefasst, übersetzte bleiben getrennt; die
    Trefferzahl kann daher über der Zahl verschiedener Ausschreibungen liegen.
    `only_language=True` erzwingt eine einzelne Sprachfassung.

    Returns:
        str: Ausschreibungen (neueste zuerst) mit Datum, Kanton, Titel, Sprache, ID.
    """
    rubrics, sub_rubrics, warnings = _procurement_scope(params.canton, params.include_inactive)

    cpv_warning = None
    if params.keyword and CPV_RE.match(params.keyword):
        cpv_warning = (
            f"«{params.keyword}» sieht wie ein CPV-Code aus. Das Amtsblattportal "
            "unterstützt keine CPV-Filterung — der Wert wird als Freitext gesucht "
            "und liefert vermutlich keine Treffer. Bitte ein Stichwort verwenden."
        )

    if not rubrics and not sub_rubrics:
        all_warnings = warnings + ([cpv_warning] if cpv_warning else [])
        if params.response_format == ResponseFormat.JSON:
            return _json_out(
                {
                    "count": 0,
                    "total": 0,
                    "rubrics": [],
                    "warnings": all_warnings,
                    "results": [],
                },
                "no_call",
            )
        lines = ["## Öffentliche Ausschreibungen", ""]
        lines += [f"> ⚠️ {w}" for w in all_warnings]
        return _md(lines, "no_call")

    try:
        for code in rubrics:
            await _validate_rubric_code(code, "rubric")
        for code in sub_rubrics:
            await _validate_rubric_code(code, "subRubric")
        data = await _search(
            {
                # Sent as `subRubrics`, never folded into `rubrics`: their parent
                # rubrics are blocked and carry Baugesuche / Zivilstand entries.
                "rubrics": (rubrics if len(rubrics) > 1 else rubrics[0]) if rubrics else None,
                "subRubrics": (
                    (sub_rubrics if len(sub_rubrics) > 1 else sub_rubrics[0])
                    if sub_rubrics
                    else None
                ),
                "keyword": params.keyword,
                "publicationDate.start": params.date_start,
                "publicationDate.end": params.date_end,
                "pageRequest.size": min(params.limit, GAZETTE_MAX_LIMIT),
                "pageRequest.page": params.page or None,
            }
        )
    except Exception as e:
        return _handle_error(e)

    content = data.get("content", []) or []
    total = data.get("total")
    summaries, mix, lang_note = _prepare_summaries(content, params.language, params.only_language)
    # Upstream sorting is silently ignored (default is newest-first); sort
    # client-side so the order is guaranteed rather than assumed.
    summaries.sort(key=lambda s: s.get("publicationDate") or "", reverse=True)

    all_warnings = warnings + ([cpv_warning] if cpv_warning else [])
    if lang_note:
        all_warnings = all_warnings + [lang_note]

    no_match = empty_note(
        keyword=params.keyword,
        canton=params.canton,
        date_start=params.date_start,
        date_end=params.date_end,
    )

    if params.response_format == ResponseFormat.JSON:
        return _json_out(
            {
                "count": len(summaries),
                "total": total,
                "page": params.page,
                "rubrics": rubrics,
                "sub_rubrics": sub_rubrics,
                "canton": params.canton,
                "keyword": params.keyword,
                "match_type": match_type(len(summaries)),
                "note": no_match if not summaries else None,
                "language_mix": mix,
                "warnings": all_warnings,
                "results": summaries,
            },
            "live_api",
        )

    scope = params.canton or f"alle aktiven Rubriken ({', '.join(rubrics + sub_rubrics)})"
    meta_line = f"Gefunden: **{len(summaries)}** (total: {total})" + (
        f" | Stichwort: «{params.keyword}»" if params.keyword else ""
    )
    lines = _render_results(
        summaries, f"Öffentliche Ausschreibungen · {scope}", meta_line, no_match
    )
    if all_warnings:
        lines = lines[:2] + [""] + [f"> ⚠️ {w}" for w in all_warnings] + lines[2:]
    if isinstance(total, int) and total > len(summaries):
        lines += ["", f"_Weitere Treffer vorhanden — `page={params.page + 1}` abrufen._"]
    lines += [
        "",
        "_Detail inkl. Eingabefrist via `gazette_get_publication(id=…)`._",
    ]
    return _md(lines, "live_api")
