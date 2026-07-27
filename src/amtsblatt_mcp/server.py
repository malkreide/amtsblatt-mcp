"""amtsblatt-mcp — MCP server for amtsblattportal.ch (SHAB + cantonal gazettes).

Covers public procurement and official notices across the **green** rubrics of
the Swiss gazette portal. Rubrics carrying systematic natural-person data are
excluded by design — see :mod:`amtsblatt_mcp.rubrics` for the fail-closed
allow-list that governs every rubric code reaching the query string.

Architecture A (live-API-only): the upstream endpoints answer stably without
authentication, so no bulk dump is maintained. Publication content is passed
through and never persisted — official publications have statutory deletion
periods that a cache outliving them would actively undermine.
"""

from __future__ import annotations

import asyncio
import difflib
import html
import json
import logging
import os
import re
import xml.etree.ElementTree as ET
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timezone
from enum import StrEnum
from time import monotonic
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ._log import configure_logging, log_event, logged_tool
from .rubrics import (
    GREEN_RUBRICS,
    GREEN_SUB_RUBRICS,
    RED_RUBRICS,
    YELLOW_RUBRICS,
    classify,
    explain_blocked,
    is_green,
)

configure_logging()

__version__ = "0.3.0"

# ---------------------------------------------------------------------------
# Source constants
# ---------------------------------------------------------------------------

GAZETTE_BASE = "https://amtsblattportal.ch/api/v1"
GAZETTE_WEB = "https://www.amtsblattportal.ch/#!/search/publications/detail"

ATTRIBUTION = (
    "Data: amtsblattportal.ch (SHAB and cantonal gazettes) — "
    "SECO / Swiss Confederation. No liability for content "
    "of individual publications; only the signed PDF is legally binding."
)

REQUEST_TIMEOUT = 15.0


def _load_zurich_tz() -> ZoneInfo | timezone:
    """Europe/Zurich, the legally relevant timezone for submission deadlines.

    Windows ships no system tz database, so `tzdata` is declared as a
    platform-conditional dependency. Should it still be missing, fall back to
    UTC loudly rather than refusing to start: every tool except the deadline
    arithmetic is timezone-independent, and UTC is at most two hours off — a
    difference that only changes a day count around midnight.
    """
    try:
        return ZoneInfo("Europe/Zurich")
    except ZoneInfoNotFoundError:
        log_event(
            logging.ERROR,
            "tzdata_missing",
            fallback="UTC",
            hint="pip install tzdata — Fristberechnungen können um einen Tag abweichen",
        )
        return UTC


TZ_ZURICH = _load_zurich_tz()

# Egress allow-list — every outbound request from `_make_client` is checked.
# Second-layer defence: even if a dependency follows a redirect to an
# unexpected host, the request is rejected before it leaves the process.
# Override via MCP_ALLOWED_HOSTS (comma-separated) — an override replaces the
# default entirely and MUST include the gazette host.
_DEFAULT_ALLOWED_HOSTS = frozenset({"amtsblattportal.ch", "www.amtsblattportal.ch"})
ALLOWED_HOSTS: frozenset[str] = frozenset(
    h.strip().lower()
    for h in os.environ.get(
        "MCP_ALLOWED_HOSTS", ",".join(sorted(_DEFAULT_ALLOWED_HOSTS))
    ).split(",")
    if h.strip()
)

# Silent Ignore (verified 2026-07-20): an unknown parameter *name* is not
# rejected — the upstream returns HTTP 200 and the FULL corpus. A typo like
# `canton=ZH` instead of `cantons=ZH` therefore silently drops the filter.
# Query parameters are consequently built EXCLUSIVELY from this allow-list;
# no user input ever becomes a query key.
#
# Note the deliberate inconsistency in the upstream spelling: `rubrics`,
# `subRubrics`, `cantons`, `uids`, `publicationStates` are PLURAL, but
# `keyword` and `tenant` are SINGULAR. The allow-list encodes the exact
# spellings rather than a pluralisation rule.
ALLOWED_GAZETTE_PARAMS: frozenset[str] = frozenset(
    {
        "publicationStates",
        "keyword",
        "rubrics",
        "subRubrics",
        "cantons",
        "tenant",
        "publicationDate.start",
        "publicationDate.end",
        "pageRequest.size",
        "pageRequest.page",
    }
)

# Person-profiling parameters that must never reach the query string. The
# upstream `uids` filter is excluded on purpose: a UID-keyed join is
# register-mcp's job, and admitting it here would create a second entry point
# whose scope this server does not govern.
FORBIDDEN_GAZETTE_PARAMS: frozenset[str] = frozenset(
    {"uids", "municipalityName", "municipalityId", "municipalityZipCodes"}
)

# Total published corpus, verified 2026-07-20 (2 791 236, growing ~1 300/day).
# Used only for the plausibility check — an exact match is not required.
GAZETTE_CORPUS_SIZE = 2_791_236
# A *filtered* request still reporting more than this means the upstream
# silently ignored our filter and the result is not trustworthy.
GAZETTE_IGNORED_FILTER_THRESHOLD = 2_000_000

# The upstream imposes NO server-side page-size cap (verified: size=2000
# returned 2000 items). The cap below is entirely client-side.
GAZETTE_MAX_LIMIT = 100

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# A CPV code is exactly 8 digits (optionally with a check digit). Used only to
# warn that CPV filtering is unsupported by this source.
CPV_RE = re.compile(r"^\d{8}(-\d)?$")

# Multilingual publication: the upstream publishes a notice once PER LANGUAGE,
# as separate records. Verified live 2026-07-27 on OB-TI/2026-07-24: four
# tenders appear as eight records with consecutive but DIFFERENT
# publicationNumbers (…2888/2889, …2890/2891, …2892/2893, …2894/2895),
# different ids, and `language` it vs fr. There is no structural pairing key in
# the list metadata — `dossierReference` and `repeatedPublications` are null and
# `onBehalfOf` is itself translated ("Gemeinde Herisau" / "Commune de Herisau").
#
# What CAN be paired is the subset whose title body is byte-identical across
# languages (only the form prefix differs, e.g. "Bando - X" / "Appel d'offres -
# X"). Everything else — AR/Herisau, TI/Morbio — carries a genuinely translated
# body and is NOT collapsible without fuzzy matching, which this server does not
# do anywhere (see rubrics.py on why globs are expanded to literals).
#
# The form prefix is what makes the exact match safe: "Bando - X" and "Rettifica
# Bando - X" are DIFFERENT publications about the same project, so the prefix
# must survive as a discriminator even though its language must not. Mapping it
# to a language-independent form class does both. The map is an explicit
# literal: an unrecognised prefix yields no form class and therefore never
# collapses — fail-closed, exactly as for rubric codes.
_FORM_SEPARATOR_RE = re.compile(r"\s+[-–—]\s+")
_FORM_CLASSES: dict[str, str] = {
    # Ausschreibung / bando / appel d'offres
    "ausschreibung": "tender",
    "bando": "tender",
    "bando di concorso": "tender",
    "appel d'offres": "tender",
    "concorso": "tender",
    "concours": "tender",
    "invitation to tender": "tender",
    # Berichtigung / rettifica / rectification
    "berichtigung": "correction",
    "rettifica": "correction",
    "rettifica bando": "correction",
    "rectification": "correction",
    "rectification appel d'offres": "correction",
    "correction": "correction",
    # Zuschlag / aggiudicazione / adjudication
    "zuschlag": "award",
    "aggiudicazione": "award",
    "adjudication": "award",
    "award": "award",
    # Abbruch / interruzione
    "abbruch": "abandonment",
    "interruzione": "abandonment",
    "interruption": "abandonment",
    # Widerruf / revoca
    "widerruf": "revocation",
    "revoca": "revocation",
    "revocation": "revocation",
}

_TRANSIENT_STATUS = frozenset({502, 503, 504})
GAZETTE_MAX_RETRIES = int(os.environ.get("GAZETTE_MAX_RETRIES", "3"))
GAZETTE_RETRY_BACKOFF = float(os.environ.get("GAZETTE_RETRY_BACKOFF", "0.5"))

RUBRICS_TTL_SECONDS = float(os.environ.get("RUBRICS_TTL", "86400"))

CANTON_CODES = [
    "AG", "AI", "AR", "BE", "BL", "BS", "FR", "GE", "GL", "GR",
    "JU", "LU", "NE", "NW", "OW", "SG", "SH", "SO", "SZ", "TG",
    "TI", "UR", "VD", "VS", "ZG", "ZH",
]

# ---------------------------------------------------------------------------
# Public procurement (Submissionen) mapping
# ---------------------------------------------------------------------------
# Procurement is NOT a federal SHAB rubric. It exists only as a per-canton
# rubric `OB-<canton>`, and only a handful of cantons publish it in this portal
# — most (incl. Zürich) route procurement through simap.ch, a SEPARATE platform
# outside amtsblattportal.ch. `SB` is Schuldbetreibungen (debt collection), not
# Submissionen — a common confusion this map exists to prevent.
#
# `active` is a MEASURED fact, not a read one. Three of the six rubric labels
# announce their own retirement ("über Simap importiert", "I N A K T I V"), but
# OB-BS does not — its label is a plain "Öffentliches Beschaffungswesen" while
# the volume has collapsed. Deriving activity from the label would therefore
# have missed it, exactly as it missed OB-ZG before v0.1.3. Re-measure with
# `scripts/measure_procurement_coverage.py` before trusting these flags; the
# figures behind them are in docs/procurement-coverage.md.
PROCUREMENT_RUBRICS: dict[str, dict[str, Any]] = {
    "AR": {"rubric": "OB-AR", "active": True, "note": ""},
    "TI": {"rubric": "OB-TI", "active": True, "note": ""},
    # Measured 2026-07-27: 504 (2021) → 1149 → 1058 → 319 (2024) → 15 (2025) →
    # 2 (2026 YTD). Phased out in the course of 2024; the rubric label carries
    # no inactive marker, so only the volume reveals it.
    "BS": {
        "rubric": "OB-BS",
        "active": False,
        "note": "ausgelaufen im Lauf von 2024 (Wechsel zu simap.ch) — nur noch Einzelfälle",
    },
    "BL": {"rubric": "OB-BL", "active": False, "note": "inaktiv — nur historische Daten"},
    "VS": {"rubric": "OB-VS", "active": False, "note": "inaktiv seit Ende 2023 (simap.ch)"},
    "ZG": {
        "rubric": "OB-ZG",
        "active": False,
        "note": "leer — Rubrik nie befüllt, Wechsel zu simap.ch Ende Februar 2024",
    },
}
PROCUREMENT_ACTIVE_CANTONS = [c for c, v in PROCUREMENT_RUBRICS.items() if v["active"]]
PROCUREMENT_INACTIVE_CANTONS = [
    c for c, v in PROCUREMENT_RUBRICS.items() if not v["active"]
]

# Non-simap procurement that lives in a sub-rubric of an otherwise blocked
# parent. Kept separate because these must be sent as `subRubrics`, never as
# `rubrics` — sending the parent would open a blocked rubric.
# These are the only procurement publications in this portal that are NOT a
# second publication of a simap tender — which makes them the one part of the
# gazette's procurement coverage that `swiss-procurement-mcp` cannot reach.
#
# Established by resolving every publication's XML `<simapPublicationNumber>`
# (measured 2026-07-27, see docs/simap-overlap.md):
#
#   OB-AR   sample 25/25 carry a simap reference     -> mirror
#   OB-BS   sample 24/25                             -> mirror
#   OB-BL   sample 25/25                             -> mirror
#   OB-VS   sample 25/25                             -> mirror
#   AR-VS40        0/25                              -> gazette-native
#   AR-OW40        0/7                               -> gazette-native
#   BA-SH40        0/2                               -> gazette-native
#
# `AR-NW40` is deliberately absent: it holds 0 publications, so searching it
# only costs a filter slot. It stays on the green allow-list — emptiness is a
# coverage fact, not a data-protection one — it is merely not worth querying.
PROCUREMENT_SUB_RUBRICS: dict[str, dict[str, Any]] = {
    "VS": {"sub_rubric": "AR-VS40", "active": True, "note": "Zuschläge (nicht über simap.ch)"},
    "OW": {"sub_rubric": "AR-OW40", "active": True, "note": "nicht über simap.ch"},
    "SH": {"sub_rubric": "BA-SH40", "active": True, "note": "nicht über simap.ch"},
}
PROCUREMENT_SUB_RUBRIC_CODES = frozenset(
    v["sub_rubric"] for v in PROCUREMENT_SUB_RUBRICS.values()
)


class GazetteFilterIgnored(RuntimeError):
    """Raised when the upstream silently ignored a filter (Silent Ignore)."""


class GazetteInvalidCode(ValueError):
    """Raised when a rubric/subRubric code is not in the taxonomy (Silent Empty)."""


class RubricBlocked(PermissionError):
    """Raised when a requested rubric is not on the green allow-list.

    Carries the full explanatory message; the tool layer returns it verbatim.
    """


class EgressDenied(httpx.RequestError):
    """Raised when an outbound request targets a host outside ALLOWED_HOSTS."""


class ResponseFormat(StrEnum):
    MARKDOWN = "markdown"
    JSON = "json"


class RubricClass(StrEnum):
    GREEN = "green"
    ALL = "all"


# ---------------------------------------------------------------------------
# HTTP plumbing
# ---------------------------------------------------------------------------


async def _enforce_egress_allowlist(request: httpx.Request) -> None:
    """httpx event hook: reject requests to hosts outside ALLOWED_HOSTS.

    Runs before send AND on each redirect (httpx fires a `request` event per
    hop when `follow_redirects=True`), so an unexpected 3xx Location cannot
    exfiltrate the request.
    """
    host = (request.url.host or "").lower()
    if host not in ALLOWED_HOSTS:
        log_event(
            logging.ERROR,
            "egress_denied",
            host=host,
            url=str(request.url),
            allowed=sorted(ALLOWED_HOSTS),
        )
        raise EgressDenied(
            f"Egress to host {host!r} is not in ALLOWED_HOSTS", request=request
        )


def _make_client() -> httpx.AsyncClient:
    """Create an async HTTP client with the egress guard installed."""
    return httpx.AsyncClient(
        timeout=REQUEST_TIMEOUT,
        headers={
            "Accept": "application/json",
            "User-Agent": f"amtsblatt-mcp/{__version__} (Swiss Public Data MCP Portfolio)",
        },
        follow_redirects=True,
        event_hooks={"request": [_enforce_egress_allowlist]},
    )


# A single AsyncClient is shared across all requests so TCP connections and TLS
# sessions are pooled instead of re-established per call. Created lazily on
# first use (so direct tool invocation in tests works without the server
# lifespan) and closed on shutdown by the FastMCP lifespan below.
_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    """Return the shared AsyncClient, (re)creating it on first use or if closed."""
    global _client
    if _client is None or _client.is_closed:
        _client = _make_client()
    return _client


async def _close_client() -> None:
    """Close the shared client if open. Called on server shutdown."""
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
    _client = None


def _reset_client() -> None:
    """Test helper: drop the shared client between tests."""
    global _client
    _client = None


async def _get_json(path: str, params: dict | None = None) -> Any:
    """GET a JSON endpoint with retry on transient 5xx (502/503/504)."""
    client = _get_client()
    for attempt in range(1, GAZETTE_MAX_RETRIES + 1):
        r = await client.get(f"{GAZETTE_BASE}{path}", params=params)
        if r.status_code in _TRANSIENT_STATUS and attempt < GAZETTE_MAX_RETRIES:
            log_event(
                logging.WARNING, "gazette_retry",
                path=path, status=r.status_code, attempt=attempt,
            )
            await asyncio.sleep(GAZETTE_RETRY_BACKOFF * attempt)
            continue
        r.raise_for_status()
        return r.json()


async def _get_text(path: str, params: dict | None = None) -> str:
    """GET an endpoint returning raw text (XML), with the same retry policy."""
    client = _get_client()
    for attempt in range(1, GAZETTE_MAX_RETRIES + 1):
        r = await client.get(f"{GAZETTE_BASE}{path}", params=params)
        if r.status_code in _TRANSIENT_STATUS and attempt < GAZETTE_MAX_RETRIES:
            log_event(
                logging.WARNING, "gazette_retry",
                path=path, status=r.status_code, attempt=attempt,
            )
            await asyncio.sleep(GAZETTE_RETRY_BACKOFF * attempt)
            continue
        r.raise_for_status()
        return r.text


def _build_params(raw: dict[str, Any]) -> dict[str, Any]:
    """Build the query dict EXCLUSIVELY from the allow-list.

    `publicationStates` is mandatory upstream — omitting it yields HTTP 401,
    not 400 — so it is always injected.
    """
    params: dict[str, Any] = {"publicationStates": "PUBLISHED"}
    for key, value in raw.items():
        if value in (None, "", []):
            continue
        if key not in ALLOWED_GAZETTE_PARAMS:
            continue  # defensive: drop anything not explicitly allowed
        params[key] = value
    return params


def _assert_green_params(params: dict[str, Any]) -> None:
    """Last line of defence before the query string is built.

    Every rubric/subRubric value about to be sent is re-checked against the
    green allow-list. This duplicates the tool-level gate on purpose: it is a
    structural guarantee that no future code path can smuggle a blocked rubric
    into a request, independent of which tool constructed it.
    """
    for key in ("rubrics", "subRubrics"):
        value = params.get(key)
        if not value:
            continue
        codes = value if isinstance(value, list) else [value]
        for code in codes:
            if not is_green(code):
                log_event(
                    logging.ERROR, "green_gate_violation", param=key, code=code
                )
                raise RubricBlocked(explain_blocked(code, kind=key.rstrip("s")))


async def _search(raw_params: dict[str, Any]) -> dict:
    """Run a /publications search behind the green gate and the quirk guards."""
    params = _build_params(raw_params)
    _assert_green_params(params)
    data = await _get_json("/publications", params=params)
    if not isinstance(data, dict):
        return {"content": [], "total": 0}
    total = data.get("total")
    # Plausibility check: a filtered request still reporting the whole corpus
    # means the filter was silently dropped upstream. This is the only defence
    # against a silent parameter rename on the provider side.
    if isinstance(total, int) and total > GAZETTE_IGNORED_FILTER_THRESHOLD:
        log_event(
            logging.ERROR, "gazette_filter_ignored", total=total, params=sorted(params)
        )
        raise GazetteFilterIgnored(
            f"Filter wurde vom Upstream ignoriert — Ergebnis nicht vertrauenswürdig "
            f"(total={total:,}, erwartet < {GAZETTE_IGNORED_FILTER_THRESHOLD:,}). "
            "Ursache: Silent Ignore unbekannter Parameter."
        )
    return data


# ---------------------------------------------------------------------------
# Taxonomy cache
# ---------------------------------------------------------------------------

_rubrics_cache: tuple[float, list[dict]] | None = None


async def _fetch_rubrics(ttl: float | None = None) -> tuple[list[dict], bool]:
    """Fetch the rubric/subRubric taxonomy with a TTL cache (default 24 h).

    Returns (data, from_cache). This is *taxonomy*, not publication content —
    caching it does not conflict with the no-persistence rule.
    """
    global _rubrics_cache
    effective_ttl = RUBRICS_TTL_SECONDS if ttl is None else ttl
    now = monotonic()
    if _rubrics_cache and now - _rubrics_cache[0] < effective_ttl:
        return _rubrics_cache[1], True
    data = await _get_json("/rubrics")
    if not isinstance(data, list):
        data = []
    _rubrics_cache = (now, data)
    return data, False


def _reset_rubrics_cache() -> None:
    """Test helper: clear the rubrics cache between tests."""
    global _rubrics_cache
    _rubrics_cache = None


def _extract_rubric_codes(rubrics_data: list[dict]) -> tuple[set[str], set[str]]:
    """Return (rubric_codes, subRubric_codes) from the taxonomy, defensively."""
    rubric_codes: set[str] = set()
    sub_codes: set[str] = set()
    for r in rubrics_data:
        if not isinstance(r, dict):
            continue
        if r.get("code"):
            rubric_codes.add(r["code"])
        for s in r.get("subRubrics", []) or []:
            if isinstance(s, dict) and s.get("code"):
                sub_codes.add(s["code"])
    return rubric_codes, sub_codes


async def _validate_rubric_code(code: str, kind: str) -> None:
    """Validate a code against the live taxonomy (Silent Empty guard).

    An invalid code returns HTTP 200 with an empty result, indistinguishable
    from a legitimate no-hit. Validation therefore happens BEFORE any
    /publications call, and fails with the closest valid codes.

    Only *green* codes are ever suggested — proposing a blocked rubric as a
    "did you mean" would be a circumvention hint.
    """
    rubrics_data, _ = await _fetch_rubrics()
    rubric_codes, sub_codes = _extract_rubric_codes(rubrics_data)
    valid = rubric_codes if kind == "rubric" else sub_codes
    if code in valid:
        return
    green_valid = sorted(c for c in valid if is_green(c))
    suggestions = difflib.get_close_matches(code, green_valid, n=5, cutoff=0.0)
    hint = ", ".join(suggestions) if suggestions else "— (Taxonomie via list_rubrics)"
    raise GazetteInvalidCode(
        f"Ungültiger {kind}-Code «{code}». Nächstliegende erschlossene Codes: {hint}."
    )


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
# XML parsing (the only source of full publication text)
# ---------------------------------------------------------------------------


def _localname(tag: str) -> str:
    """Strip any XML namespace, returning the bare local element name."""
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else tag


_TAG_RE = re.compile(r"<[^>]+>")


def _clean_text(raw: str) -> str:
    """Unescape entity-encoded HTML and strip its markup.

    Procurement bodies arrive as HTML escaped into a text node
    (`&lt;p>Bezüglich…&lt;br/>`). Passing that through verbatim would put raw
    markup into the model's context, so it is unescaped, tags are dropped and
    block boundaries become newlines.
    """
    if "&lt;" in raw or "&amp;" in raw:
        raw = html.unescape(raw)
    raw = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>", "\n", raw)
    raw = _TAG_RE.sub("", raw)
    raw = html.unescape(raw)
    lines = [ln.strip() for ln in raw.splitlines()]
    return "\n".join(ln for ln in lines if ln).strip()


def _el_text(el: ET.Element) -> str:
    """Collapse an element's full text content, cleaned of inline markup."""
    return _clean_text("".join(el.itertext()).strip())


def _first_local(root: ET.Element, name: str) -> ET.Element | None:
    """First descendant (or self) whose local name matches — namespace-agnostic."""
    for c in root.iter():
        if _localname(c.tag) == name:
            return c
    return None


def _node_to_value(el: ET.Element) -> Any:
    """Leaf element -> text; container -> {localName: value} (best-effort)."""
    children = list(el)
    if not children:
        return _el_text(el)
    return {_localname(c.tag): _node_to_value(c) for c in children}


# Element names that carry the official body text, in preference order. The
# schema is per-subRubric: HR uses `publicationText`, procurement uses
# `publication`. Never hard-code a rubric-specific *path*.
_TEXT_ELEMENTS = ("publicationText", "publication", "text", "body")
# Element names that plausibly carry a submission deadline.
_DEADLINE_ELEMENTS = (
    "deadline", "submitDeadline", "offerDeadline", "applicationDeadline",
    "entryDeadline", "closingDate",
)


def _parse_publication_xml(xml_text: str) -> dict:
    """Defensively parse a single-publication XML.

    The schema is rubric-specific (`HR03-export`, `OB-BS70-export`, …) with a
    per-subRubric namespace whose middle path segment is the *tenant*, so no
    rubric-specific path is ever hard-coded. Only two things are reliably
    present and treated as mandatory: the meta block and a body-text element.
    Everything else lands best-effort in `additional_fields`. Malformed XML
    raises ET.ParseError to the caller.
    """
    root = ET.fromstring(xml_text)

    meta_el = _first_local(root, "meta")
    meta: dict[str, Any] = {}
    if meta_el is not None:
        for child in meta_el:
            meta[_localname(child.tag)] = _node_to_value(child)

    content_el = _first_local(root, "content")
    search_root = content_el if content_el is not None else root

    publication_text = None
    text_element_name = None
    for name in _TEXT_ELEMENTS:
        el = _first_local(search_root, name)
        if el is not None and _el_text(el):
            publication_text = _el_text(el)
            text_element_name = name
            break

    company: dict[str, Any] = {}
    comp_el = _first_local(search_root, "company")
    if comp_el is not None:
        for key in ("name", "uid", "seat", "legalForm", "address"):
            el = _first_local(comp_el, key)
            if el is not None:
                company[key] = _node_to_value(el)

    deadline = None
    for name in _DEADLINE_ELEMENTS:
        el = _first_local(search_root, name)
        if el is not None and _el_text(el):
            deadline = _el_text(el)
            break

    # Procurement publications that originate on simap.ch carry the simap
    # publication number, e.g. "#41510-01" (projectNumber-sequence). Its
    # presence is the only reliable way to tell a second publication from a
    # gazette-native one — measured over the whole 2026 OB-TI corpus, 92.1% of
    # records carry it and every record that lacks one sits in a sub-rubric
    # simap does not cover. Promoted out of `additional_fields` because that
    # distinction decides whether `swiss-procurement-mcp` has the same record.
    simap_ref = None
    simap_el = _first_local(search_root, "simapPublicationNumber")
    if simap_el is not None:
        simap_ref = _el_text(simap_el).lstrip("#").strip() or None
        # Some publishers fill the field with a placeholder rather than leaving
        # it out; treat that as absent rather than as an unresolvable id.
        if simap_ref in {"-", "--", "---", "n/a", "N/A"}:
            simap_ref = None

    additional: dict[str, Any] = {}
    if content_el is not None:
        for child in content_el:
            ln = _localname(child.tag)
            if ln in (text_element_name, "simapPublicationNumber"):
                continue
            additional[ln] = _node_to_value(child)

    return {
        "meta": meta,
        "publicationText": publication_text,
        "company": company,
        "deadline": deadline,
        "simap_publication_number": simap_ref,
        "additional_fields": additional,
    }


# ---------------------------------------------------------------------------
# Output envelope
# ---------------------------------------------------------------------------


def _md(lines: list[str], provenance: str) -> str:
    """Append the mandatory attribution + provenance footer (Markdown)."""
    return "\n".join(
        [*lines, "", "---", f"_{ATTRIBUTION}_", f"_provenance: {provenance}_"]
    )


def _json_out(payload: dict, provenance: str) -> str:
    """Wrap a JSON payload with the mandatory attribution + provenance fields."""
    enriched = {**payload, "attribution": ATTRIBUTION, "provenance": provenance}
    return json.dumps(enriched, ensure_ascii=False, indent=2)


def _handle_error(e: Exception) -> str:
    """Translate an exception into an actionable, human-readable message."""
    if isinstance(e, RubricBlocked):
        return str(e)
    if isinstance(e, (GazetteFilterIgnored, GazetteInvalidCode)):
        return str(e)
    if isinstance(e, EgressDenied):
        return f"Egress verweigert: {e}. Ziel-Host nicht in ALLOWED_HOSTS."
    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        if status == 400:
            return "Fehler 400: Ungültige Anfrage. Bitte Parameter prüfen."
        if status == 401:
            # Verified upstream behaviour: a missing `publicationStates` yields
            # 401/AccessDeniedException, NOT 400. It never means "credentials
            # required" — the read API is unauthenticated.
            return (
                "Fehler 401: Die Quelle hat die Anfrage abgelehnt. Das deutet auf "
                "einen fehlenden `publicationStates`-Parameter hin, nicht auf "
                "fehlende Zugangsdaten — die Lese-API ist unauthentifiziert."
            )
        if status == 404:
            return "Fehler 404: Publikation nicht gefunden. Bitte ID prüfen."
        if status == 429:
            return "Fehler 429: Rate-Limit überschritten. Bitte kurz warten."
        return f"Fehler {status}: Anfrage an das Amtsblattportal fehlgeschlagen."
    if isinstance(e, httpx.TimeoutException):
        return "Timeout: Das Amtsblattportal antwortet nicht. Bitte erneut versuchen."
    if isinstance(e, httpx.ConnectError):
        return (
            "Verbindungsfehler: Das Amtsblattportal ist nicht erreichbar. "
            "Dies ist KEIN leeres Ergebnis — es konnten keine Daten abgefragt werden."
        )
    return f"Unerwarteter Fehler: {type(e).__name__}: {e}"


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

@asynccontextmanager
async def _lifespan(_server: FastMCP):
    """Server lifespan: guarantee the shared HTTP client is closed on shutdown.

    The client itself is created lazily on first request (see `_get_client`),
    so nothing needs to be opened here — this exists to release pooled
    connections cleanly when the server stops.
    """
    try:
        yield {}
    finally:
        await _close_client()


mcp = FastMCP(
    "amtsblatt_mcp",
    lifespan=_lifespan,
    instructions=(
        "Read-only access to amtsblattportal.ch — the Swiss official gazette portal "
        "(SHAB plus 27 cantonal gazettes). Covers public procurement (Submissionen), "
        "cantonal and communal notices, enactments, spatial planning and the "
        "commercial register.\n\n"
        "IMPORTANT — scope: this server deliberately exposes ONLY rubrics without "
        "systematic natural-person data. Bankruptcies, debt collection, inheritance "
        "calls, civil status, court summons and building applications are NOT "
        "queryable, and no person-name search parameter exists in any tool. This is "
        "a data-protection decision, not a limitation to work around; do not attempt "
        "to reach those rubrics by other means. For publications about a specific "
        "COMPANY (a legal person, including its bankruptcy) use the UID join in the "
        "companion server `register-mcp`.\n\n"
        "Start with `list_rubrics` to see what is queryable, then "
        "`search_publications` or `search_gazette_procurement`, then `get_publication(id=…)` "
        "for the official full text — the list endpoint returns metadata only."
    ),
)

transport = os.environ.get("MCP_TRANSPORT", "stdio")
if transport == "sse":
    # Bind loopback by default; exposing on all interfaces requires an explicit
    # MCP_HOST=0.0.0.0. This prevents accidental NeighborJack exposure on shared
    # networks, on top of the mandatory bearer auth + rate limit enforced below.
    # Containers set MCP_HOST=0.0.0.0 deliberately (see compose.yaml).
    mcp.settings.host = os.environ.get("MCP_HOST", "127.0.0.1")
    mcp.settings.port = int(os.environ.get("PORT", "8000"))


# ---------------------------------------------------------------------------
# Input models
# ---------------------------------------------------------------------------


class SearchInput(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True, validate_assignment=True, extra="forbid"
    )

    keyword: str | None = Field(
        default=None,
        description=(
            "Volltext-Suchbegriff, z.B. 'Informatik', 'Zonenplan', 'Trambeschaffung'. "
            "Sucht über den Publikationstext, NICHT über Personennamen."
        ),
        min_length=2,
        max_length=200,
    )
    rubric: str | None = Field(
        default=None,
        description=(
            "Rubrik-Code, z.B. 'HR' (Handelsregister), 'OB-BS' (Beschaffung "
            "Basel-Stadt), 'RP-ZH' (Raumplanung Zürich). Nur freigegebene Rubriken "
            "sind zulässig — `list_rubrics` zeigt sie. Ohne Angabe wird über alle "
            "freigegebenen Rubriken gesucht."
        ),
        max_length=12,
    )
    sub_rubric: str | None = Field(
        default=None,
        description="Subrubrik-Code, z.B. 'HR01' oder 'AR-NW40'. Wird vorab validiert.",
        max_length=12,
    )
    canton: str | None = Field(
        default=None,
        description="Kantonskürzel, z.B. 'ZH'. Beispiel: 'BS'.",
        min_length=2,
        max_length=2,
    )
    date_start: str | None = Field(
        default=None,
        description="Zeitraum-Start (YYYY-MM-DD).",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    )
    date_end: str | None = Field(
        default=None,
        description="Zeitraum-Ende (YYYY-MM-DD).",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    )
    limit: int = Field(
        default=20,
        description="Maximale Anzahl Ergebnisse (1–100). Standard: 20.",
        ge=1,
        le=GAZETTE_MAX_LIMIT,
    )
    page: int = Field(
        default=0,
        description="Seitenzahl für Pagination, 0-basiert. Standard: 0.",
        ge=0,
    )
    language: str = Field(
        default="de",
        description="Bevorzugte Sprache für Titel und Deduplikation. Standard: 'de'.",
        pattern=r"^(de|fr|it|en)$",
    )
    only_language: bool = Field(
        default=False,
        description=(
            "Nur Publikationen in der unter `language` gewählten Sprache zurückgeben. "
            "Mehrsprachige Kantone (TI, teilweise AR) publizieren dieselbe "
            "Bekanntmachung je Sprache als eigenen Datensatz; True liefert genau "
            "eine Sprachfassung, kann aber Bekanntmachungen ausblenden, die es in "
            "dieser Sprache nicht gibt. Standard: False."
        ),
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Ausgabeformat: 'markdown' oder 'json'",
    )

    @field_validator("canton")
    @classmethod
    def validate_canton(cls, v: str | None) -> str | None:
        if v and v.upper() not in CANTON_CODES:
            raise ValueError(
                f"Ungültiges Kantonskürzel '{v}'. Gültig: {', '.join(CANTON_CODES)}"
            )
        return v.upper() if v else v


class ProcurementInput(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True, validate_assignment=True, extra="forbid"
    )

    keyword: str | None = Field(
        default=None,
        description=(
            "Freitext-Suchbegriff, z.B. 'Informatik', 'Schulmobiliar', 'Reinigung'. "
            "HINWEIS: Die Quelle kennt KEINE CPV-Codes — nur Volltextsuche."
        ),
        min_length=2,
        max_length=200,
    )
    canton: str | None = Field(
        default=None,
        description=(
            "Kantonskürzel, z.B. 'TI'. Beschaffungsrubriken gibt es nur für "
            "AR und TI (aktiv) sowie BS, BL, VS, ZG (inaktiv; ZG leer, BS/BL/VS "
            "nur Archiv). Andere Kantone — inklusive ZH — publizieren über "
            "simap.ch, nicht hier. Ohne Kanton wird über alle aktiven "
            "Beschaffungsrubriken gesucht."
        ),
        min_length=2,
        max_length=2,
    )
    date_start: str | None = Field(
        default=None,
        description="Zeitraum-Start (YYYY-MM-DD).",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    )
    date_end: str | None = Field(
        default=None,
        description="Zeitraum-Ende (YYYY-MM-DD).",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    )
    include_inactive: bool = Field(
        default=False,
        description=(
            "Auch inaktive Beschaffungsrubriken (BS, BL, VS) einbeziehen — nur "
            "historische Daten. Standard: False."
        ),
    )
    limit: int = Field(
        default=20,
        description="Maximale Anzahl Ergebnisse (1–100). Standard: 20.",
        ge=1,
        le=GAZETTE_MAX_LIMIT,
    )
    page: int = Field(
        default=0, description="Seitenzahl für Pagination, 0-basiert.", ge=0
    )
    language: str = Field(
        default="de",
        description="Bevorzugte Sprache. Standard: 'de'.",
        pattern=r"^(de|fr|it|en)$",
    )
    only_language: bool = Field(
        default=False,
        description=(
            "Nur Ausschreibungen in der unter `language` gewählten Sprache. "
            "Ticino publiziert überwiegend it/fr, Appenzell A.Rh. de/fr — je "
            "Sprache ein eigener Datensatz. True liefert genau eine Sprachfassung. "
            "Standard: False."
        ),
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Ausgabeformat: 'markdown' oder 'json'",
    )

    @field_validator("canton")
    @classmethod
    def validate_canton(cls, v: str | None) -> str | None:
        if v and v.upper() not in CANTON_CODES:
            raise ValueError(
                f"Ungültiges Kantonskürzel '{v}'. Gültig: {', '.join(CANTON_CODES)}"
            )
        return v.upper() if v else v


class PublicationInput(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True, validate_assignment=True, extra="forbid"
    )

    id: str = Field(
        ...,
        description=(
            "Publikations-ID (UUID) aus `search_publications` oder "
            "`search_gazette_procurement`. Beispiel: 'fbf0ff9e-3e28-4e09-8a1e-32a7aa4cea8f'."
        ),
        min_length=8,
        max_length=64,
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Ausgabeformat: 'markdown' oder 'json'",
    )


class RubricsInput(BaseModel):
    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    language: str = Field(
        default="de",
        description="Sprache der Rubrik-Namen: 'de', 'fr', 'it', 'en'. Standard: 'de'.",
        pattern=r"^(de|fr|it|en)$",
    )
    rubric_class: RubricClass = Field(
        default=RubricClass.GREEN,
        description=(
            "'green' zeigt nur die erschlossenen Rubriken (Standard). 'all' zeigt "
            "die vollständige Taxonomie mit Ampel-Klassierung — blockierte Rubriken "
            "erscheinen mit Begründung, bleiben aber nicht durchsuchbar."
        ),
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Ausgabeformat: 'markdown' oder 'json'",
    )


class StatusInput(BaseModel):
    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Ausgabeformat: 'markdown' oder 'json'",
    )


# ---------------------------------------------------------------------------
# Tool: search_publications
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


def _render_results(summaries: list[dict], heading: str, meta_line: str) -> list[str]:
    """Shared Markdown rendering for both search tools."""
    lines = [f"## {heading}", meta_line, ""]
    if not summaries:
        lines.append(
            "_Keine Treffer für diese Filter. Zeitraum, Stichwort oder Rubrik anpassen._"
        )
    for s in summaries:
        cantons = s.get("cantons")
        canton_str = (
            ", ".join(cantons) if isinstance(cantons, list) else (cantons or "—")
        )
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
    name="search_publications",
    annotations={
        "title": "Amtsblatt-Publikationen suchen (freigegebene Rubriken)",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
@logged_tool("search_publications")
async def search_publications(params: SearchInput) -> str:
    """Sucht amtliche Publikationen im Amtsblattportal (SHAB + kantonale Amtsblätter).

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
            return explain_blocked(code, kind=kind)

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
    summaries, mix, lang_note = _prepare_summaries(
        content, params.language, params.only_language
    )

    if params.response_format == ResponseFormat.JSON:
        return _json_out(
            {
                "count": len(summaries),
                "total": total,
                "page": params.page,
                "scope": "green_rubrics_only",
                "language_mix": mix,
                "warnings": [lang_note] if lang_note else [],
                "results": summaries,
            },
            "live_api",
        )

    scope = params.rubric or params.sub_rubric or "alle freigegebenen Rubriken"
    meta_line = f"Gefunden: **{len(summaries)}** (total: {total}) | Bereich: {scope}"
    lines = _render_results(summaries, "Amtsblatt-Suche", meta_line)
    if lang_note:
        lines = lines[:2] + ["", f"> ⚠️ {lang_note}"] + lines[2:]
    if isinstance(total, int) and total > len(summaries):
        lines += ["", f"_Weitere Treffer vorhanden — `page={params.page + 1}` abrufen._"]
    lines += ["", "_Volltext einer Publikation via `get_publication(id=…)`._"]
    return _md(lines, "live_api")


# ---------------------------------------------------------------------------
# Tool: search_gazette_procurement
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
    name="search_gazette_procurement",
    annotations={
        "title": "Öffentliche Ausschreibungen / Submissionen suchen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
@logged_tool("search_gazette_procurement")
async def search_gazette_procurement(params: ProcurementInput) -> str:
    """Sucht öffentliche Ausschreibungen (Beschaffungswesen/Submissionen).

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
    rubrics, sub_rubrics, warnings = _procurement_scope(
        params.canton, params.include_inactive
    )

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
                    "count": 0, "total": 0, "rubrics": [],
                    "warnings": all_warnings, "results": [],
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
    summaries, mix, lang_note = _prepare_summaries(
        content, params.language, params.only_language
    )
    # Upstream sorting is silently ignored (default is newest-first); sort
    # client-side so the order is guaranteed rather than assumed.
    summaries.sort(key=lambda s: s.get("publicationDate") or "", reverse=True)

    all_warnings = warnings + ([cpv_warning] if cpv_warning else [])
    if lang_note:
        all_warnings = all_warnings + [lang_note]

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
        summaries, f"Öffentliche Ausschreibungen · {scope}", meta_line
    )
    if all_warnings:
        lines = lines[:2] + [""] + [f"> ⚠️ {w}" for w in all_warnings] + lines[2:]
    if isinstance(total, int) and total > len(summaries):
        lines += ["", f"_Weitere Treffer vorhanden — `page={params.page + 1}` abrufen._"]
    lines += [
        "",
        "_Detail inkl. Eingabefrist via `get_publication(id=…)`._",
    ]
    return _md(lines, "live_api")


# ---------------------------------------------------------------------------
# Tool: get_publication
# ---------------------------------------------------------------------------


@mcp.tool(
    name="get_publication",
    annotations={
        "title": "Einzelpublikation inkl. amtlichem Volltext",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
@logged_tool("get_publication")
async def get_publication(params: PublicationInput) -> str:
    """Einzelne Publikation inkl. amtlichem Volltext (aus dem XML, defensiv geparst).

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
    try:
        xml_text = await _get_text(f"/publications/{params.id}/xml")
    except Exception as e:
        return _handle_error(e)

    try:
        parsed = _parse_publication_xml(xml_text)
    except ET.ParseError as e:
        return f"Fehler: XML der Publikation {params.id} konnte nicht geparst werden ({e})."

    meta = parsed["meta"]
    # Post-fetch green gate: an ID is opaque, so the rubric can only be checked
    # once the document is in hand. Content from a blocked rubric is discarded
    # here and never rendered.
    rubric = meta.get("rubric")
    sub_rubric = meta.get("subRubric")
    if rubric and not (is_green(rubric) or (sub_rubric and is_green(sub_rubric))):
        log_event(
            logging.WARNING, "blocked_publication_requested",
            rubric=rubric, publication_id=params.id,
        )
        return explain_blocked(rubric, kind="rubric")

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
            lines.append(
                f"- **address:** {' '.join(str(v) for v in addr.values() if v)}"
            )
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
    elif rubric and (rubric.startswith("OB-") or (sub_rubric or "") in PROCUREMENT_SUB_RUBRIC_CODES):
        lines += [
            "",
            "_Diese Beschaffungspublikation trägt keine simap-Nummer, existiert also "
            "nur im Amtsblattportal und ist über `swiss-procurement-mcp` nicht "
            "auffindbar._",
        ]

    return _md(lines, "live_api")


# ---------------------------------------------------------------------------
# Tool: list_rubrics
# ---------------------------------------------------------------------------

_CLASS_ICON = {"green": "🟢", "yellow": "🟡", "red": "🔴", "unclassified": "⚪"}


@mcp.tool(
    name="list_rubrics",
    annotations={
        "title": "Rubriken auflisten (mit Ampel-Klassierung)",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
@logged_tool("list_rubrics")
async def list_rubrics(params: RubricsInput) -> str:
    """Rubrik-Taxonomie des Amtsblattportals mit Ampel-Klassierung.

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

    heading = (
        "Erschlossene Rubriken" if green_only else "Rubriken (vollständige Taxonomie)"
    )
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
# ---------------------------------------------------------------------------


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
    """Status des Amtsblattportals, Cache-Alter und Umfang der Freigabe-Liste.

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
        "rubrics_cache_age": _cache_age(_rubrics_cache),
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
        f"| **Taxonomie-Cache** | {_cache_age(_rubrics_cache)} |",
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


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

DEFAULT_RATE_LIMIT = int(os.environ.get("MCP_RATE_LIMIT", "60"))
DEFAULT_RATE_WINDOW = float(os.environ.get("MCP_RATE_WINDOW", "60"))


def _build_sse_app():
    """Build the SSE Starlette app with auth + rate-limit middleware.

    Requires `MCP_API_KEY`. Fails loud at startup otherwise — no implicit
    "auth disabled" mode is supported for SSE.
    """
    from ._middleware import BearerAuthMiddleware, RateLimitMiddleware

    api_key = os.environ.get("MCP_API_KEY", "").strip()
    if not api_key:
        raise SystemExit(
            "MCP_API_KEY must be set when MCP_TRANSPORT=sse. "
            "Generate a random key (e.g. `openssl rand -hex 32`) and pass it via env."
        )

    app = mcp.sse_app()
    # Middleware added later runs first → add rate-limit first, then auth, so
    # the rate-limit bucket key is the authenticated token hash.
    app.add_middleware(
        RateLimitMiddleware, limit=DEFAULT_RATE_LIMIT, window=DEFAULT_RATE_WINDOW
    )
    app.add_middleware(BearerAuthMiddleware, expected_key=api_key)
    log_event(
        logging.INFO, "sse_app_built",
        rate_limit=DEFAULT_RATE_LIMIT, rate_window=DEFAULT_RATE_WINDOW,
    )
    return app


def main() -> None:
    from ._otel import init_otel

    init_otel()
    if transport == "stdio":
        log_event(
            logging.INFO, "starting",
            transport="stdio", green_rubrics=len(GREEN_RUBRICS),
        )
        mcp.run(transport="stdio")
        return
    if transport == "sse":
        import uvicorn

        app = _build_sse_app()
        log_event(
            logging.INFO, "starting",
            transport="sse", host=mcp.settings.host, port=mcp.settings.port,
        )
        uvicorn.run(
            app,
            host=mcp.settings.host,
            port=mcp.settings.port,
            log_level=mcp.settings.log_level.lower(),
        )
        return
    raise SystemExit(
        f"Unsupported MCP_TRANSPORT={transport!r} (expected 'stdio' or 'sse')"
    )


if __name__ == "__main__":
    main()
