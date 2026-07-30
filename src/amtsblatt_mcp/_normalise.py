"""Shaping upstream records into the fields the tools actually render.

Extracted from `server.py` for `ARCH-011`. Two concerns live here that look
cosmetic and are not:

`_collapse_language_variants` exists because the gazette publishes one record
*per language*, so a naive count reports three hits for one notice. And
`_days_remaining` / `_format_deadline` are computed in Europe/Zurich rather than
UTC, because a submission deadline is a legal date in a Swiss timezone and being
a day out is a real answer being wrong.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from .constants import _FORM_CLASSES, _FORM_SEPARATOR_RE, DATE_RE, GAZETTE_WEB, TZ_ZURICH

# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------


def _to_bool(value: Any, default: bool = False) -> bool:
    """Normalise the upstream's inconsistent boolean encodings.

    The taxonomy and publication payloads spell booleans as real booleans,
    as the strings "true"/"false"/"1"/"0"/"yes"/"no", and as null. A bare
    truthiness test would read the string "false" as True.
    """
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ("true", "1", "yes", "y", "ja"):
            return True
        if v in ("false", "0", "no", "n", "nein", ""):
            return False
    return default


def _pick_language(value: Any, lang: str = "de") -> Any:
    """Collapse a multilingual dict to one language: requested → de → first."""
    if isinstance(value, dict):
        return value.get(lang) or value.get("de") or next(iter(value.values()), None)
    return value


def _iso_date(value: Any) -> Any:
    """Truncate an ISO timestamp to a bare date. JSON carries a full timestamp
    (`2026-05-20T00:00:00.000Z`), XML carries `2026-05-20`."""
    if isinstance(value, str) and "T" in value:
        return value.split("T", 1)[0]
    return value


def _today_zurich() -> date:
    """Today in Europe/Zurich — the legally relevant timezone for deadlines."""
    return datetime.now(TZ_ZURICH).date()


def _days_remaining(deadline: Any, today: date | None = None) -> int | None:
    """Whole days from `today` (Europe/Zurich) until `deadline`.

    Negative when the deadline has passed, 0 on the deadline day itself.
    Returns None when the value is not a parseable date, so callers can render
    "—" rather than a misleading number.
    """
    raw = _iso_date(deadline)
    if not isinstance(raw, str) or not DATE_RE.match(raw):
        return None
    try:
        target = date.fromisoformat(raw)
    except ValueError:
        return None
    return (target - (today or _today_zurich())).days


def _format_deadline(deadline: Any, today: date | None = None) -> str:
    """Render a deadline with its remaining time, in German."""
    raw = _iso_date(deadline)
    days = _days_remaining(deadline, today)
    if days is None:
        return str(raw) if raw else "—"
    if days < 0:
        return f"{raw} (abgelaufen vor {abs(days)} Tagen)"
    if days == 0:
        return f"{raw} (läuft heute ab)"
    if days == 1:
        return f"{raw} (noch 1 Tag)"
    return f"{raw} (noch {days} Tage)"


def _meta_summary(item: dict, lang: str = "de") -> dict:
    """Normalise a publication list item (meta only) into a flat summary."""
    meta = item.get("meta") if isinstance(item, dict) else None
    meta = meta if isinstance(meta, dict) else (item if isinstance(item, dict) else {})
    ro = meta.get("registrationOffice")
    ro_name = ro.get("displayName") if isinstance(ro, dict) else ro
    return {
        "id": meta.get("id"),
        "rubric": meta.get("rubric"),
        "subRubric": meta.get("subRubric"),
        "publicationNumber": meta.get("publicationNumber"),
        "publicationDate": _iso_date(meta.get("publicationDate")),
        "expirationDate": _iso_date(meta.get("expirationDate")),
        "registrationOffice": ro_name,
        "title": _pick_language(meta.get("title"), lang),
        "language": meta.get("language"),
        "cantons": meta.get("cantons"),
        "url": f"{GAZETTE_WEB}/{meta.get('id')}" if meta.get("id") else None,
    }


def _split_form_prefix(title: Any) -> tuple[str | None, str]:
    """Split "Bando - Neubau Turnhalle" into ("tender", "Neubau Turnhalle").

    Returns ``(None, title)`` when the prefix is absent or not on the literal
    form map, so an unrecognised form is never treated as equivalent to a known
    one. A title without the separator (e.g. "Bando di concorso Opere da
    impresario forestale") is deliberately left whole: the form word cannot be
    told apart from the body there without guessing.
    """
    if not isinstance(title, str) or not title:
        return None, ""
    parts = _FORM_SEPARATOR_RE.split(title, maxsplit=1)
    if len(parts) != 2:
        return None, title
    head, body = parts
    key = re.sub(r"\s+", " ", head.strip().replace("’", "'").replace("`", "'")).lower()
    form = _FORM_CLASSES.get(key)
    if form is None:
        return None, title
    return form, body.strip()


def _norm_body(text: str) -> str:
    """Case- and punctuation-insensitive form of a title body, for EXACT match."""
    return re.sub(r"[^0-9a-zà-ÿ]+", " ", text.lower()).strip()


def _collapse_language_variants(summaries: list[dict], lang: str = "de") -> list[dict]:
    """Collapse the provable multi-language duplicates, and only those.

    Two records are the same publication when they agree on rubric, sub-rubric,
    publication date and form class AND their title bodies are identical after
    the language-carrying form prefix is removed. That is an exact match, never
    a fuzzy one — see the `_FORM_CLASSES` note for why the residue (genuinely
    translated bodies) is reported rather than guessed at.

    The variant whose `language` matches `lang` wins; otherwise the first one
    seen is kept, and input order is preserved.
    """
    chosen: dict[Any, dict] = {}
    order: list[Any] = []
    for s in summaries:
        form, body = _split_form_prefix(s.get("title"))
        norm = _norm_body(body)
        if form is None or not norm:
            # Not collapsible — keep as its own entry, keyed on identity.
            key: Any = ("_unique", s.get("id"))
        else:
            key = (s.get("rubric"), s.get("subRubric"), s.get("publicationDate"), form, norm)
        if key not in chosen:
            chosen[key] = s
            order.append(key)
        elif s.get("language") == lang and chosen[key].get("language") != lang:
            chosen[key] = s
    return [chosen[k] for k in order]


def _language_mix(summaries: list[dict]) -> dict[str, int]:
    """Count publication languages in a result set, most frequent first."""
    counts: dict[str, int] = {}
    for s in summaries:
        code = s.get("language") or "?"
        counts[code] = counts.get(code, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))


def _language_note(mix: dict[str, int]) -> str | None:
    """Warn that a multilingual result set counts one notice more than once.

    Only the exact duplicates are collapsed upstream of this; cantons that
    translate the title body (AR, parts of TI) still contribute one record per
    language, and a count that silently included them would overstate how many
    distinct notices exist.
    """
    if len(mix) < 2:
        return None
    listed = ", ".join(f"{code} {n}" for code, n in mix.items())
    return (
        f"Mehrsprachige Publikation: {listed}. Das Amtsblattportal veröffentlicht "
        "eine Bekanntmachung je Sprache als eigenen Datensatz mit eigener "
        "Publikationsnummer. Identische Titel wurden zusammengefasst; bei "
        "übersetzten Titeln (u. a. AR, teilweise TI) bleibt pro Sprache ein "
        "Eintrag, die Trefferzahl liegt also über der Zahl verschiedener "
        "Ausschreibungen. Mit `only_language=True` nur eine Sprachfassung."
    )


# ---------------------------------------------------------------------------
