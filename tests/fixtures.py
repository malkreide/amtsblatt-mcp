"""Shared test fixtures — shortened real responses, consistently anonymised.

All payloads are derived from real API responses (probed 2026-07-20) but
truncated and stripped of any real personal data. Where a blocked rubric has
to be represented at all, the names are invented placeholders — the point of
those fixtures is to prove the content is *never rendered*.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Taxonomy (/rubrics) — a representative slice across all traffic-light classes
# ---------------------------------------------------------------------------

MOCK_RUBRICS: list[dict] = [
    {
        "code": "HR",
        "name": {"de": "Handelsregistereintragungen", "fr": "Registre du commerce"},
        "active": True,
        "subRubrics": [
            {"code": "HR01", "name": {"de": "Neueintragungen"}},
            {"code": "HR03", "name": {"de": "Mutationen"}},
        ],
    },
    {
        "code": "BH",
        "name": {"de": "Bekanntmachungen nach Handelsregisterverordnung"},
        "active": True,
        "subRubrics": [{"code": "BH01", "name": {"de": "Bekanntmachungen"}}],
    },
    {
        "code": "OB-BS",
        "name": {"de": "Öffentliches Beschaffungswesen"},
        "active": True,
        "subRubrics": [
            {"code": "OB-BS10", "name": {"de": "Ausschreibung"}},
            {"code": "OB-BS70", "name": {"de": "Abbruch"}},
        ],
    },
    {
        "code": "OB-AR",
        "name": {"de": "Öffentliches Beschaffungswesen"},
        "active": True,
        "subRubrics": [{"code": "OB-AR10", "name": {"de": "Ausschreibung"}}],
    },
    {
        "code": "OB-TI",
        "name": {"de": "Öffentliches Beschaffungswesen", "it": "Appalti pubblici"},
        "active": True,
        "subRubrics": [{"code": "OB-TI10", "name": {"de": "Ausschreibung"}}],
    },
    {
        "code": "OB-ZG",
        "name": {"de": "Öffentliches Beschaffungswesen"},
        "active": True,
        "subRubrics": [{"code": "OB-ZG10", "name": {"de": "Ausschreibung"}}],
    },
    {
        "code": "OB-VS",
        "name": {"de": "Öffentliches Beschaffungswesen (inaktiv)"},
        "active": "false",
        "subRubrics": [{"code": "OB-VS10", "name": {"de": "Ausschreibung"}}],
    },
    {
        "code": "OB-BL",
        "name": {"de": "Öffentliches Beschaffungswesen über Simap (INAKTIV)"},
        # Deliberately a string, not a bool — the upstream is inconsistent and
        # `_to_bool` has to normalise it.
        "active": "false",
        "subRubrics": [{"code": "OB-BL10", "name": {"de": "Ausschreibung"}}],
    },
    {
        "code": "RP-ZH",
        "name": {"de": "Raumplanung"},
        "active": True,
        "subRubrics": [{"code": "RP-ZH10", "name": {"de": "Nutzungsplanung"}}],
    },
    {
        "code": "KO-ZH",
        "name": {"de": "Weitere kommunale Bekanntmachungen"},
        "active": True,
        "subRubrics": [{"code": "KO-ZH10", "name": {"de": "Bekanntmachung"}}],
    },
    # --- blocked below: must never appear in a green listing ---
    {
        "code": "KK",
        "name": {"de": "Konkurse"},
        "active": True,
        "subRubrics": [
            {"code": "KK01", "name": {"de": "Konkurseröffnung"}},
            {"code": "KK03", "name": {"de": "Konkursschluss"}},
        ],
    },
    {
        "code": "SB",
        "name": {"de": "Schuldbetreibungen"},
        "active": True,
        "subRubrics": [{"code": "SB01", "name": {"de": "Zahlungsbefehl"}}],
    },
    {
        "code": "SW-ZH",
        "name": {"de": "Steuerwesen"},
        "active": True,
        "subRubrics": [{"code": "SW-ZH10", "name": {"de": "Steuerdomizil"}}],
    },
    {
        "code": "AR-NW",
        "name": {"de": "Wirtschaft, Arbeit und Bildung"},
        "active": True,
        "subRubrics": [
            {"code": "AR-NW40", "name": {"de": "Öffentliche Beschaffung"}},
            {"code": "AR-NW10", "name": {"de": "Arbeitsvergaben"}},
        ],
    },
    # Blocked collector rubrics whose procurement sub-rubric is released. These
    # carry the gazette-native procurement — the publications that do NOT also
    # exist on simap.ch — so the search has to be able to reach the sub-rubric
    # without ever injecting its parent.
    {
        "code": "AR-VS",
        "name": {"de": "Wirtschaft, Arbeit und Bildung"},
        "active": True,
        "subRubrics": [
            {"code": "AR-VS40", "name": {"de": "Öffentliche Beschaffung"}},
            {"code": "AR-VS10", "name": {"de": "Arbeitsvergaben"}},
        ],
    },
    {
        "code": "AR-OW",
        "name": {"de": "Wirtschaft, Arbeit und Bildung"},
        "active": True,
        "subRubrics": [{"code": "AR-OW40", "name": {"de": "Öffentliche Beschaffung"}}],
    },
    {
        "code": "BA-SH",
        "name": {"de": "Bau, Raum und Verkehr"},
        "active": True,
        "subRubrics": [
            {"code": "BA-SH40", "name": {"de": "Öffentliche Beschaffung"}},
            {"code": "BA-SH10", "name": {"de": "Baugesuche"}},
        ],
    },
]


# ---------------------------------------------------------------------------
# Search results (/publications)
# ---------------------------------------------------------------------------


def pub_item(
    pub_id: str,
    rubric: str,
    sub: str,
    date: str,
    title: str,
    *,
    canton: str = "BS",
    language: str = "de",
    publication_number: str | None = None,
    office: str = "Bau- und Verkehrsdepartement",
) -> dict:
    """Build a publication list item in the exact upstream shape."""
    return {
        "meta": {
            "id": pub_id,
            "rubric": rubric,
            "subRubric": sub,
            "language": language,
            "registrationOffice": {"id": "ro-1", "displayName": office},
            "publicationNumber": publication_number or f"{sub}-{pub_id[:8]}",
            "publicationState": "PUBLISHED",
            "publicationDate": f"{date}T00:00:00.000Z",
            "expirationDate": "2031-05-20T00:00:00.000Z",
            "cantons": [canton],
            "title": {"de": title, "fr": title, "it": title, "en": title},
        },
        "links": [],
        "attachments": [],
        "content": None,
        "commented": False,
    }


MOCK_SEARCH: dict = {
    "content": [
        pub_item(
            "fbf0ff9e-3e28-4e09-8a1e-32a7aa4cea8f",
            "OB-BS", "OB-BS70", "2026-07-07",
            "Abbruch Ausschreibung Trambeschaffung Plus",
        ),
        pub_item(
            "aa11bb22-3e28-4e09-8a1e-32a7aa4cea01",
            "OB-BS", "OB-BS10", "2024-11-11",
            "Ausschreibung Informatik-Dienstleistungen",
        ),
    ],
    "total": 2,
    "pageRequest": {"sortOrders": [], "page": 0, "size": 20},
}

MOCK_SEARCH_EMPTY: dict = {
    "content": [],
    "total": 0,
    "pageRequest": {"sortOrders": [], "page": 0, "size": 20},
}

# Multilingual publication, in the shape the upstream really uses (verified
# 2026-07-27 against OB-TI/2026-07-24 and OB-AR/2026-05-22).
#
# A notice republished in another language is a SEPARATE record with its own id
# AND its own publicationNumber — the numbers are consecutive but never equal,
# which is why keying deduplication on publicationNumber collapsed nothing.
# Three shapes have to be told apart:
#
#   1. it/fr pair, byte-identical body, only the form prefix translated
#      -> collapsible by exact match
#   2. a correction of that same tender: same body, DIFFERENT form prefix
#      -> must NOT collapse into the tender, even on the same day
#   3. de/fr pair with a genuinely TRANSLATED body (the AR/Herisau shape)
#      -> not collapsible without fuzzy matching; reported, never guessed
MOCK_SEARCH_MULTILANG: dict = {
    "content": [
        # (1) collapsible pair
        pub_item(
            "aa000001-0000-0000-0000-000000000001", "OB-TI", "OB-TI10", "2026-07-24",
            "Bando - NUOVO CENTRO SPORTIVO, STABIO - OPERE PER IMPIANTI SPORTIVI",
            canton="TI", language="it", publication_number="OB-TI10-0000002892",
            office="Repubblica e Cantone del Ticino",
        ),
        pub_item(
            "aa000002-0000-0000-0000-000000000002", "OB-TI", "OB-TI10", "2026-07-24",
            "Appel d’offres - NUOVO CENTRO SPORTIVO, STABIO - OPERE PER IMPIANTI SPORTIVI",
            canton="TI", language="fr", publication_number="OB-TI10-0000002893",
            office="Repubblica e Cantone del Ticino",
        ),
        # (2) correction of the very same tender, same day, same body
        pub_item(
            "aa000003-0000-0000-0000-000000000003", "OB-TI", "OB-TI10", "2026-07-24",
            "Rettifica Bando - NUOVO CENTRO SPORTIVO, STABIO - OPERE PER IMPIANTI SPORTIVI",
            canton="TI", language="it", publication_number="OB-TI10-0000002896",
            office="Repubblica e Cantone del Ticino",
        ),
        # (3) translated pair — one notice, two records, two bodies
        pub_item(
            "bb000001-0000-0000-0000-000000000004", "OB-AR", "OB-AR10", "2026-05-22",
            "Ausschreibung - Muldenmiete, Muldentransport und Verwertung Chammerholz",
            canton="AR", language="de", publication_number="OB-AR10-0000000336",
            office="Kanton Appenzell Ausserrhoden",
        ),
        pub_item(
            "bb000002-0000-0000-0000-000000000005", "OB-AR", "OB-AR10", "2026-05-22",
            "Appel d’offres - Location et transport de bennes, valorisation",
            canton="AR", language="fr", publication_number="OB-AR10-0000000337",
            office="Kanton Appenzell Ausserrhoden",
        ),
    ],
    "total": 5,
    "pageRequest": {"sortOrders": [], "page": 0, "size": 20},
}

# Silent Ignore: a filtered request that still reports the whole corpus.
MOCK_SEARCH_CORPUS: dict = {
    "content": [],
    "total": 2_791_236,
    "pageRequest": {"sortOrders": [], "page": 0, "size": 20},
}

MOCK_SEARCH_PAGE_2: dict = {
    "content": [
        pub_item(
            "cc33dd44-3e28-4e09-8a1e-32a7aa4cea02",
            "OB-BS", "OB-BS10", "2024-03-03",
            "Ausschreibung Schulmobiliar Basel",
        ),
    ],
    "total": 3,
    "pageRequest": {"sortOrders": [], "page": 1, "size": 2},
}


# ---------------------------------------------------------------------------
# Single-publication XML
# ---------------------------------------------------------------------------

# Procurement: note the per-subRubric namespace whose middle segment is the
# TENANT (`kabbs`, not `shab`), the body element named `publication` rather
# than `publicationText`, and its entity-escaped HTML markup.
MOCK_XML_PROCUREMENT = """<?xml version='1.0' encoding='UTF-8'?>
<OB-BS70:publication xmlns:OB-BS70="https://shab.ch/kabbs/OB-BS70-export">
  <meta>
    <id>fbf0ff9e-3e28-4e09-8a1e-32a7aa4cea8f</id>
    <rubric>OB-BS</rubric>
    <subRubric>OB-BS70</subRubric>
    <language>de</language>
    <publicationNumber>OB-BS70-0000000332</publicationNumber>
    <publicationDate>2026-05-20</publicationDate>
    <registrationOffice>
      <displayName>Basler Verkehrs-Betriebe (BVB)</displayName>
    </registrationOffice>
    <cantons>BS</cantons>
    <title><de>Abbruch Ausschreibung Trambeschaffung Plus</de></title>
  </meta>
  <content>
    <title>Abbruch Ausschreibung Trambeschaffung Plus</title>
    <deadline>2026-08-15</deadline>
    <projectTitle>Trambeschaffung Plus</projectTitle>
    <publication>&lt;p>Bez&#252;glich der oben erw&#228;hnten Submission teilen wir mit, dass das Vergabeverfahren gem&#228;ss Art. 43 Abs. 1 Lit. b) IV&#246;B abgebrochen wird.&lt;br/>Eine Neuausschreibung ist vorgesehen.&lt;/p></publication>
  </content>
</OB-BS70:publication>
"""

# A gazette-native procurement publication: NO <simapPublicationNumber>, which
# is what distinguishes an original from a second publication of a simap tender.
MOCK_XML_NATIVE_PROCUREMENT = """<?xml version='1.0' encoding='UTF-8'?>
<AR-VS40:publication xmlns:AR-VS40="https://shab.ch/kabvs/AR-VS40-export">
  <meta>
    <id>cccc1111-0000-0000-0000-000000000009</id>
    <rubric>AR-VS</rubric>
    <subRubric>AR-VS40</subRubric>
    <language>fr</language>
    <publicationNumber>AR-VS40-0000000786</publicationNumber>
    <publicationDate>2026-06-26</publicationDate>
    <title><fr>Adjudication - travaux de genie-civil</fr></title>
  </meta>
  <content>
    <title>Adjudication - travaux de genie-civil</title>
    <publication>&lt;p>Le marche est adjuge.&lt;/p></publication>
  </content>
</AR-VS40:publication>
"""

# The mirror case: the same shape WITH the simap reference, as the OB-* rubrics
# carry it. Note the leading "#", which has to be stripped.
MOCK_XML_MIRRORED_PROCUREMENT = """<?xml version='1.0' encoding='UTF-8'?>
<OB-TI10:publication xmlns:OB-TI10="https://shab.ch/kabti/OB-TI10-export">
  <meta>
    <id>dddd2222-0000-0000-0000-000000000010</id>
    <rubric>OB-TI</rubric>
    <subRubric>OB-TI10</subRubric>
    <language>it</language>
    <publicationNumber>OB-TI10-0000002896</publicationNumber>
    <publicationDate>2026-07-27</publicationDate>
    <title><it>Bando - Percorso Ciclabile</it></title>
  </meta>
  <content>
    <title>Bando - Percorso Ciclabile</title>
    <publication>&lt;p>Oggetto della commessa.&lt;/p></publication>
    <simapPublicationNumber>#41510-01</simapPublicationNumber>
  </content>
</OB-TI10:publication>
"""

# Some publishers fill the field with a dash instead of omitting it; that must
# read as "no reference", not as an unresolvable id.
MOCK_XML_PLACEHOLDER_SIMAP_REF = MOCK_XML_MIRRORED_PROCUREMENT.replace(
    "#41510-01", "--"
)

# Commercial register: the other schema shape — `publicationText` plus a
# `company` block, under the `shab` tenant namespace.
MOCK_XML_HR03 = """<?xml version='1.0' encoding='UTF-8'?>
<HR03:publication xmlns:HR03="https://shab.ch/shab/HR03-export">
  <meta>
    <id>11112222-3333-4444-5555-666677778888</id>
    <rubric>HR</rubric>
    <subRubric>HR03</subRubric>
    <publicationNumber>HR03-1000000001</publicationNumber>
    <publicationDate>2026-07-07</publicationDate>
    <title><de>Musterfirma AG</de></title>
  </meta>
  <content>
    <publicationText>Musterfirma AG, in Basel, CHE-999.999.999, Aktiengesellschaft.</publicationText>
    <company>
      <name>Musterfirma AG</name>
      <uid>CHE-999.999.999</uid>
      <seat>Basel</seat>
      <legalForm>Aktiengesellschaft</legalForm>
    </company>
  </content>
</HR03:publication>
"""

# An unknown rubric shape: neither `publicationText` nor `company`, plus an
# exotic element that must land in additional_fields rather than raise.
MOCK_XML_UNKNOWN = """<?xml version='1.0' encoding='UTF-8'?>
<XX99:publication xmlns:XX99="https://shab.ch/kabxx/XX99-export">
  <meta>
    <id>99998888-7777-6666-5555-444433332222</id>
    <rubric>RP-ZH</rubric>
    <subRubric>RP-ZH10</subRubric>
    <publicationDate>2026-07-01</publicationDate>
  </meta>
  <content>
    <publicationText>Amtlicher Fliesstext einer unbekannten Rubrik.</publicationText>
    <someExoticField>Wert</someExoticField>
  </content>
</XX99:publication>
"""

# A blocked rubric's XML. Names are invented; the test asserts this text is
# NEVER rendered to the user.
MOCK_XML_BLOCKED_RUBRIC = """<?xml version='1.0' encoding='UTF-8'?>
<KK01:publication xmlns:KK01="https://shab.ch/shab/KK01-export">
  <meta>
    <id>abc12345-0000-0000-0000-000000000001</id>
    <rubric>KK</rubric>
    <subRubric>KK01</subRubric>
    <publicationDate>2026-07-01</publicationDate>
    <title><de>Konkurseröffnung</de></title>
  </meta>
  <content>
    <publicationText>Konkurseröffnung über Erika Mustermann, geb. 1970, Musterstrasse 1.</publicationText>
  </content>
</KK01:publication>
"""

MOCK_XML_MALFORMED = "<publication><meta><id>broken</id>"
