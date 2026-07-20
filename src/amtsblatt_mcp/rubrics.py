"""Fail-closed rubric classification for amtsblatt-mcp.

This module is the data-protection heart of the server. The Amtsblattportal
systematically publishes rubrics containing personal data of **natural**
persons (bankruptcies, debt collection, inheritance calls, civil status).
Public though those publications are, making them *systematically queryable*
through an AI agent is a repurposing the publication never intended and would
be a profiling instrument under the revised Swiss FADP (revDSG).

Therefore this server operates a **green allow-list, never a block-list**:

1. A rubric that is not *explicitly* listed in ``GREEN_RUBRICS`` is not
   queryable. New rubrics appearing upstream are closed by default.
2. The green set is an explicit literal ``frozenset`` — **never** a prefix or
   glob match. The source proposal's table uses glob notation (``KA-*``,
   ``RS-*``, …) for readability, but transcribing globs into code would
   silently auto-green any future upstream rubric matching the prefix, which
   is exactly what requirement 1 forbids.
3. ``RED_RUBRICS`` exists only to produce a *better error message* — it is
   never consulted to decide access. Access is decided solely by absence from
   the green set. A rubric that is in neither set is blocked just as firmly as
   an explicitly red one.

Classification snapshot: live ``/rubrics`` taxonomy of 2026-07-20
(152 top-level rubrics). See ``docs/rubric-classification.md`` for the full
audit trail, including the rubrics deliberately left unclassified.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# 🟢 GREEN — explicitly released top-level rubrics
# ---------------------------------------------------------------------------
# Grouped by the row of the source traffic-light table they implement, so a
# reviewer can diff this set against the proposal line by line.

# Handelsregister + Bekanntmachungen nach Handelsregisterverordnung.
# Legal persons only — no natural-person data by construction.
_GREEN_COMMERCIAL_REGISTER = frozenset({"HR", "BH"})

# Öffentliches Beschaffungswesen (Submissionen). Contracting authorities and
# bidding companies are legal persons. BL/VS are inactive (historical data
# only) but remain green — inactivity is a coverage fact, not a privacy fact.
_GREEN_PROCUREMENT = frozenset({"OB-AR", "OB-BS", "OB-TI", "OB-ZG", "OB-BL", "OB-VS"})

# Weitere kantonale Bekanntmachungen — institutional notices.
_GREEN_CANTONAL_NOTICES = frozenset({"KA-AR", "KA-BE", "KA-BS", "KA-TI", "KA-ZG", "KA-ZH"})

# Weitere kommunale Bekanntmachungen — the municipal twin of KA-*.
# Not spelled out in the source table, whose prose nonetheless reads
# "Kantonale/kommunale Bekanntmachungen". Released as a documented extension.
_GREEN_COMMUNAL_NOTICES = frozenset({"KO-AR", "KO-BE", "KO-BS", "KO-TI", "KO-ZG", "KO-ZH"})

# Beschlüsse, Erlasse, Rechtsetzung — statutory texts, institutional.
_GREEN_ENACTMENTS = frozenset(
    {
        "RS-AR", "RS-BE", "RS-BL", "RS-BS", "RS-ZG", "RS-ZH", "RS-DA",
        "RE-NW", "RE-OW", "RE-SH", "RE-SO", "RE-SZ", "RE-VS",
    }
)

# Politische Rechte. `PL-BL` is Basel-Landschaft's spelling of the same thing;
# the source table only lists `PR-*`, so BL would silently fall out.
_GREEN_POLITICAL_RIGHTS = frozenset({"PR-BS", "PR-TI", "PL-BL"})

# Raumplanung — zoning and land-use planning. Concerns parcels, not persons.
_GREEN_SPATIAL_PLANNING = frozenset(
    {"RP-AR", "RP-BE", "RP-BL", "RP-BS", "RP-TI", "RP-ZG", "RP-ZH"}
)

# Umwelt, Verkehr und Energie — institutional infrastructure notices.
# Released as a documented extension for the same reason as KO-*.
_GREEN_ENVIRONMENT = frozenset({"VE-AR", "VE-BE", "VE-BS", "VE-TI", "VE-ZG", "VE-ZH"})

GREEN_RUBRICS: frozenset[str] = (
    _GREEN_COMMERCIAL_REGISTER
    | _GREEN_PROCUREMENT
    | _GREEN_CANTONAL_NOTICES
    | _GREEN_COMMUNAL_NOTICES
    | _GREEN_ENACTMENTS
    | _GREEN_POLITICAL_RIGHTS
    | _GREEN_SPATIAL_PLANNING
    | _GREEN_ENVIRONMENT
)

# ---------------------------------------------------------------------------
# 🟢 GREEN — sub-rubrics whose PARENT rubric is blocked
# ---------------------------------------------------------------------------
# Non-simap procurement lives in sub-rubrics of parent rubrics that also carry
# Baugesuche or Zivilstand entries. The parent stays blocked; only these exact
# sub-rubrics are released. A search on one of them must therefore NEVER have
# its parent rubric injected alongside it.
GREEN_SUB_RUBRICS: frozenset[str] = frozenset(
    {"AR-NW40", "AR-OW40", "AR-VS40", "BA-SH40"}
)

# ---------------------------------------------------------------------------
# 🔴 RED — documented rationale, used ONLY for error messages
# ---------------------------------------------------------------------------
# Never consulted for access decisions. Its sole purpose is turning
# "not in the green set" into an explanation the user can act on.

_REASON_INSOLVENCY = (
    "Konkurse, Schuldbetreibungen und Schuldenrufe nennen systematisch "
    "natürliche Personen mit Wohnadresse"
)
_REASON_ESTATE = (
    "Erbschafts-, Testaments- und Ablebensbekanntmachungen nennen systematisch "
    "natürliche Personen und deren Angehörige"
)
_REASON_CIVIL_STATUS = (
    "Bürgerrecht und Zivilstandswesen betreffen ausschliesslich natürliche Personen"
)
_REASON_COURT = (
    "Gerichtliche Vorladungen und Entscheide nennen systematisch natürliche Personen"
)
_REASON_BUILDING = (
    "Baugesuche nennen regelmässig Grundeigentümer:innen mit Namen und Adresse"
)
_REASON_LAND_REGISTRY = (
    "Grundbuch-/Handänderungspublikationen nennen Eigentümer:innen namentlich"
)

RED_RUBRICS: dict[str, str] = {
    # Insolvency / debt collection
    "KK": _REASON_INSOLVENCY,
    "SB": _REASON_INSOLVENCY,
    "LS": _REASON_INSOLVENCY,
    "SR": _REASON_INSOLVENCY,
    "NA": _REASON_INSOLVENCY,
    # Estate / death
    "ES": _REASON_ESTATE,
    "TE-AR": _REASON_ESTATE, "TE-BE": _REASON_ESTATE, "TE-BL": _REASON_ESTATE,
    "TE-BS": _REASON_ESTATE, "TE-TI": _REASON_ESTATE, "TE-ZG": _REASON_ESTATE,
    "TE-ZH": _REASON_ESTATE,
    "VA-NW": _REASON_ESTATE, "VA-SH": _REASON_ESTATE, "VA-SO": _REASON_ESTATE,
    "VA-SZ": _REASON_ESTATE, "VA-VS": _REASON_ESTATE,
    # Family / civil status / citizenship
    "FZ-AR": _REASON_CIVIL_STATUS, "FZ-BE": _REASON_CIVIL_STATUS,
    "FZ-BS": _REASON_CIVIL_STATUS, "FZ-ZH": _REASON_CIVIL_STATUS,
    "BV-BE": _REASON_CIVIL_STATUS, "BV-BS": _REASON_CIVIL_STATUS,
    "BV-ZH": _REASON_CIVIL_STATUS,
    # `BU-*` merges Bürgerrecht + Steuer- + Zivilstandswesen into one rubric in
    # NW/OW/SH/SO/SZ/VS. Matched by no prefix in the source table — six
    # cantons' civil-status data would otherwise have no explicit rationale.
    "BU-NW": _REASON_CIVIL_STATUS, "BU-OW": _REASON_CIVIL_STATUS,
    "BU-SH": _REASON_CIVIL_STATUS, "BU-SO": _REASON_CIVIL_STATUS,
    "BU-SZ": _REASON_CIVIL_STATUS, "BU-VS": _REASON_CIVIL_STATUS,
    # Courts / summons
    "UV": _REASON_COURT,
    "GB-AR": _REASON_COURT, "GB-BE": _REASON_COURT, "GB-BL": _REASON_COURT,
    "GB-BS": _REASON_COURT, "GB-TI": _REASON_COURT, "GB-ZG": _REASON_COURT,
    "GB-ZH": _REASON_COURT,
    "GE-NW": _REASON_COURT, "GE-OW": _REASON_COURT, "GE-SH": _REASON_COURT,
    "GE-SO": _REASON_COURT, "GE-SZ": _REASON_COURT, "GE-VS": _REASON_COURT,
    "SJ-BE": _REASON_COURT,
    # Building applications
    "BP-AR": _REASON_BUILDING, "BP-BE": _REASON_BUILDING, "BP-BL": _REASON_BUILDING,
    "BP-BS": _REASON_BUILDING, "BP-TI": _REASON_BUILDING, "BP-ZG": _REASON_BUILDING,
    "BP-ZH": _REASON_BUILDING,
    # Land registry
    "GR-BL": _REASON_LAND_REGISTRY,
    "GR-BS": _REASON_LAND_REGISTRY,
    # `AA-GR` (Graubünden «Meldungskatalog») bundles Testamentseröffnung,
    # Erbenaufruf, Gerichtsvorladung AND Baugesuch under one code that matches
    # none of the red prefixes in the source table. Highest-priority explicit
    # entry: fail-closed already blocks it, but silently.
    "AA-GR": (
        "der Meldungskatalog GR bündelt Testamentseröffnungen, Erbenaufrufe, "
        "gerichtliche Vorladungen und Baugesuche in einer einzigen Rubrik"
    ),
}

# 🟡 YELLOW — context-dependent, deferred until explicitly released.
# Also error-message-only. Kept distinct from red so the explanation can say
# "noch nicht erschlossen" rather than "bewusst ausgeschlossen".
YELLOW_RUBRICS: dict[str, str] = {
    "AZ": "Anzeigen mit gemischtem Inhalt",
    "AB": "Arbeit — kann natürliche Personen nennen",
    "FM": "Finanzmarkt — kann natürliche Personen nennen",
    "AI-AR": "Anzeigen und Inserate", "AI-BS": "Anzeigen und Inserate",
    "AI-TI": "Anzeigen und Inserate", "AI-ZH": "Anzeigen und Inserate",
    "SW-AR": "Steuerwesen", "SW-BL": "Steuerwesen", "SW-BS": "Steuerwesen",
    "SW-TI": "Steuerwesen", "SW-ZG": "Steuerwesen", "SW-ZH": "Steuerwesen",
    "AL-NW": "allgemeine Sammelrubrik mit gemischtem Inhalt",
    "AL-OW": "allgemeine Sammelrubrik mit gemischtem Inhalt",
    "AL-SH": "allgemeine Sammelrubrik mit gemischtem Inhalt",
    "AL-SO": "allgemeine Sammelrubrik mit gemischtem Inhalt",
    "AL-SZ": "allgemeine Sammelrubrik mit gemischtem Inhalt",
    "AL-VS": "allgemeine Sammelrubrik mit gemischtem Inhalt",
    "WB-BL": "allgemeine Sammelrubrik mit gemischtem Inhalt",
    "AM-DA": "kommunale Sammelrubrik mit 26 Subrubriken",
    "AR-NW": "Sammelrubrik — nur die Subrubrik AR-NW40 (Beschaffung) ist erschlossen",
    "AR-OW": "Sammelrubrik — nur die Subrubrik AR-OW40 (Beschaffung) ist erschlossen",
    "AR-VS": "Sammelrubrik — nur die Subrubrik AR-VS40 (Beschaffung) ist erschlossen",
    "AR-SH": "Sammelrubrik Wirtschaft, Arbeit und Bildung",
    "AR-SO": "Sammelrubrik Wirtschaft, Arbeit und Bildung",
    "AR-SZ": "Sammelrubrik Wirtschaft, Arbeit und Bildung",
    "BA-SH": "Sammelrubrik — nur die Subrubrik BA-SH40 (Beschaffung) ist erschlossen",
    "BA-NW": "Sammelrubrik Bau/Raum/Verkehr — enthält Baugesuche",
    "BA-OW": "Sammelrubrik Bau/Raum/Verkehr — enthält Baugesuche",
    "BA-SO": "Sammelrubrik Bau/Raum/Verkehr — enthält Baugesuche",
    "BA-SZ": "Sammelrubrik Bau/Raum/Verkehr — enthält Baugesuche",
    "BA-VS": "Sammelrubrik Bau/Raum/Verkehr — enthält Baugesuche",
    "BE-BS": "Bewilligungen — können natürliche Personen nennen",
    "BE-ZG": "Bewilligungen — können natürliche Personen nennen",
    "EG-BE": "Entsendegesetz — kann natürliche Personen nennen",
    "BW-BS": "Bildungswesen", "BW-TI": "Bildungswesen", "BW-ZG": "Bildungswesen",
    "KW-BL": "Kirchenwesen", "KW-BS": "Kirchenwesen",
    "AW": "abhandengekommene Wertpapiere",
    "BB": "weitere Register und Bekanntmachungen Bund",
    "EK": "Edelmetallkontrolle",
    "UP": "Mitteilungen an Gesellschafter",
    "OR-DA": "ePublikation öffentlich-rechtlicher Körperschaften (inaktiv)",
    "RK-DA": "ePublikation Rechtssammlung (inaktiv)",
}


def classify(code: str) -> str:
    """Return the traffic-light class of a rubric or sub-rubric code.

    Returns one of ``"green"``, ``"red"``, ``"yellow"`` or ``"unclassified"``.
    Only ``"green"`` grants access; the other three are equally blocked and
    differ solely in the explanation the user receives.
    """
    if code in GREEN_RUBRICS or code in GREEN_SUB_RUBRICS:
        return "green"
    if code in RED_RUBRICS:
        return "red"
    if code in YELLOW_RUBRICS:
        return "yellow"
    return "unclassified"


def is_green(code: str) -> bool:
    """True only if the code is on the explicit green allow-list."""
    return code in GREEN_RUBRICS or code in GREEN_SUB_RUBRICS


def explain_blocked(code: str, kind: str = "rubric") -> str:
    """Explain why a rubric is not queryable — clearly, and without a workaround.

    Never returns a silent empty result and never hints at a circumvention
    (requirement 4 of the data-protection rule). The message names the scope
    decision, gives the reason, and points at what the user *can* do instead.
    """
    klass = classify(code)
    label = "Subrubrik" if kind == "subRubric" else "Rubrik"

    if klass == "red":
        why = RED_RUBRICS[code]
        headline = (
            f"Die {label} «{code}» ist in diesem Server bewusst nicht erschlossen: {why}."
        )
    elif klass == "yellow":
        why = YELLOW_RUBRICS[code]
        headline = (
            f"Die {label} «{code}» ist noch nicht freigegeben ({why}) und daher "
            "nicht durchsuchbar."
        )
    else:
        headline = (
            f"Die {label} «{code}» steht nicht auf der Freigabe-Liste dieses Servers "
            "und ist daher nicht durchsuchbar."
        )

    return (
        f"{headline}\n\n"
        "Grund: amtsblatt-mcp erschliesst ausschliesslich Rubriken ohne systematische "
        "Personendaten. Amtliche Publikationen sind zwar öffentlich, aber eine "
        "namentliche Durchsuchbarkeit per KI-Agent wäre eine Zweckentfremdung und "
        "nach revidiertem DSG ein Profiling-Instrument. Die Freigabe-Liste ist "
        "fail-closed: Was nicht ausdrücklich freigegeben ist, bleibt geschlossen.\n\n"
        "Was stattdessen möglich ist:\n"
        "- `list_rubrics(rubric_class='green')` zeigt alle erschlossenen Rubriken.\n"
        "- Für Publikationen zu einer **Firma** (juristische Person, inkl. Konkurs "
        "und Schuldbetreibung) gibt es den UID-Join in `register-mcp` — dort ist "
        "der Einstieg die Firmen-UID, nicht ein Personenname.\n"
        "- Amtliche Publikationen bleiben über die Weboberfläche "
        "amtsblattportal.ch im Einzelfall zugänglich."
    )
