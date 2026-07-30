"""Source constants, the egress allow-list, and the domain error types.

Extracted from `server.py` for `ARCH-011`. Nothing here imports from the rest of
the package, which is what makes it safe to import from anywhere — the
allow-list in particular is depended on by `_http` and asserted directly by
`tests/test_allowlist.py` as its own CI job.

`ALLOWED_HOSTS` is a literal `frozenset` with no environment override, and that
is `SEC-021` rather than an oversight: an override that *replaced* the default
set would let a misconfigured deployment redirect egress wholesale, so changing
it is deliberately a code change.
"""

from __future__ import annotations

import logging
import os
import re
from datetime import UTC, timezone
from enum import StrEnum
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx

from ._log import log_event

# ---------------------------------------------------------------------------
# Source constants
# ---------------------------------------------------------------------------

GAZETTE_BASE = "https://amtsblattportal.ch/api/v1"
GAZETTE_WEB = "https://www.amtsblattportal.ch/#!/search/publications/detail"

# CH-004: attribution names the source *and* the terms it is reused under.
# Naming only the operator left the licence position implicit, which a reader
# has to guess at — and guessing wrong in either direction is a problem:
# assuming CC BY invents a grant that was never made, assuming "all rights
# reserved" blocks a reuse the Confederation permits.
ATTRIBUTION = (
    "Data: amtsblattportal.ch (SHAB and cantonal gazettes) — "
    "SECO / Swiss Confederation. Licence: no explicit open-data licence is "
    "published; reuse follows the amtsblattportal.ch terms of use "
    "(www.amtsblattportal.ch). No liability for content "
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
# Second-layer defence: even if a dependency follows a redirect to an unexpected
# host, the request is rejected before it leaves the process.
#
# SEC-021: a literal frozenset with no environment override. This used to be
# populated from MCP_ALLOWED_HOSTS, which the check disallows — a config-mutable
# allow-list lets a misconfigured deployment redirect egress wholesale, and the
# guard is only worth having if it cannot be widened from outside the code.
#
# Removing the override costs nothing real. `GAZETTE_BASE` is a hardcoded
# constant, so nothing in this server ever builds a URL for another host:
# adding one to the allow-list could never cause a request to go there. The
# override's only reachable effects were widening what a *followed redirect*
# may reach, and disabling the server outright if an override omitted the
# gazette host. Both are downside.
#
# To add a genuine second upstream, change this set and `GAZETTE_BASE` together
# in code, where the change is reviewed — see docs/network-egress.md.
ALLOWED_HOSTS: frozenset[str] = frozenset({"amtsblattportal.ch", "www.amtsblattportal.ch"})

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
# ARCH-007: cap how many hits the aggregated tool expands to full text, so one
# call fans out to a bounded number of parallel upstream requests.
GAZETTE_MAX_DETAIL_N = 5

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
    "AG",
    "AI",
    "AR",
    "BE",
    "BL",
    "BS",
    "FR",
    "GE",
    "GL",
    "GR",
    "JU",
    "LU",
    "NE",
    "NW",
    "OW",
    "SG",
    "SH",
    "SO",
    "SZ",
    "TG",
    "TI",
    "UR",
    "VD",
    "VS",
    "ZG",
    "ZH",
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
PROCUREMENT_INACTIVE_CANTONS = [c for c, v in PROCUREMENT_RUBRICS.items() if not v["active"]]

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
PROCUREMENT_SUB_RUBRIC_CODES = frozenset(v["sub_rubric"] for v in PROCUREMENT_SUB_RUBRICS.values())


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
