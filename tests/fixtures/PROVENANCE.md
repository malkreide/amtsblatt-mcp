# Herkunft der Fixtures

Aufgezeichnet am **2026-08-15** mit `PYTHONPATH=src python scripts/record_fixtures.py`.

Eine Antwort je **Abfrage**, nicht je Endpunkt: drei Endpunkte, aber mehrere
Abfrageformen (Suche nach Rubrik, nach Stichwort, nach Beschaffungskanton;
Volltext; Taxonomie; Erreichbarkeitsprobe).

Die Antworten stammen aus dem geteilten Client (gleicher User-Agent, gleiches
Timeout, gleiche Egress-Allowlist wie im Betrieb), abgegriffen ueber einen
httpx-Response-Hook. Ausgeloest hat sie jeweils das Werkzeug selbst — und damit
durch das Green-Gate.

## Personendaten

Das Amtsblatt-Korpus enthaelt Personendaten. Dieser Server erschliesst sie
nicht, und dieser Ordner deshalb auch nicht: aufgezeichnet wurde
ausschliesslich durch die Werkzeuge, also durch die Freigabeliste in
`rubrics.py`.

Die **Volltexte** stammen bewusst aus einer Beschaffungsrubrik und nicht aus
dem Handelsregister: eine Ausschreibung nennt Vergabestelle und Projekt, ein
HR-Detaileintrag dagegen die Organe mit Namen. Die Trefferlisten fuehren Firmen
und Amtsstellen.

Die Publikations-ID des Volltexts (`43c64030-697b-44f6-a15f-98133daba05e`) wird beim Aufzeichnen
gesucht und nicht fest verdrahtet — Publikationen laufen ab, und eine feste
UUID waere beim naechsten Lauf ein 404.

## Was hier *nicht* steht

`tests/fixtures.py` bleibt daneben bestehen. Es traegt die Fehlerpfade und die
gesperrten Rubriken — beides laesst sich nicht aufzeichnen, weil der Server sie
gerade nicht abholt, und beides ist als Erfindung in Ordnung.

Neu gesetzt ist die Einrueckung; gekuerzt ist allein die **Zahl** der
Listeneintraege. Kein Feld eines behaltenen Eintrags ist angetastet, und `total`
steht wie geliefert — die Quelle meint damit die Gesamtzahl der Treffer.

## `rubrics_1.json`

- **Werkzeuge:** `gazette_list_rubrics`, `gazette_source_status`
- **Schluessel:** `https://amtsblattportal.ch/api/v1/rubrics`
- **Auswahl:** ungekuerzt — der Server filtert *in* dieser Liste, ein Schnitt auf die ersten Zeilen erfaende einen Negativbefund
- **Groesse:** 930548 Bytes
- **SHA-256:** `42abb10bf2bed4a6ac3148c8ba3890bd4aba839a904ee0a009c8befae08e51fa`

## `search_detailed_1.json`

- **Werkzeuge:** `gazette_search_detailed`
- **Schluessel:** `https://amtsblattportal.ch/api/v1/publications?publicationStates=PUBLISHED&rubrics=OB-TI&publicationDate.start=2026-08-01&publicationDate.end=2026-08-14&pageRequest.size=2`
- **Auswahl:** ungekuerzt
- **Groesse:** 3958 Bytes
- **SHA-256:** `34bdfc9b360830d0692c5dc1437819ee99df4c62a7dc9ed1e7a582db1978443f`

## `search_detailed_2.xml`

- **Werkzeuge:** `gazette_get_publication`, `gazette_search_detailed`
- **Schluessel:** `https://amtsblattportal.ch/api/v1/publications/43c64030-697b-44f6-a15f-98133daba05e/xml`
- **Auswahl:** ungekuerzt
- **Groesse:** 10289 Bytes
- **SHA-256:** `e8d8d799e3f554e07b8ee701286c58176d5dd8d93d96d91520cab7324fd6d1be`

## `search_detailed_3.xml`

- **Werkzeuge:** `gazette_search_detailed`
- **Schluessel:** `https://amtsblattportal.ch/api/v1/publications/9d8bb880-120a-4262-a8f3-55ef6334bb31/xml`
- **Auswahl:** ungekuerzt
- **Groesse:** 10241 Bytes
- **SHA-256:** `815bdf1d840c2a0debefe45ac441174f1ccc8b9469e190069b3ec45667ccf741`

## `search_hr_1.json`

- **Werkzeuge:** `gazette_search_publications`
- **Schluessel:** `https://amtsblattportal.ch/api/v1/publications?publicationStates=PUBLISHED&rubrics=HR&publicationDate.start=2026-08-01&publicationDate.end=2026-08-14&pageRequest.size=5`
- **Auswahl:** 6 von 8 Listeneintraegen (je Liste die ersten 3), aus 6116 Bytes Rohantwort
- **Groesse:** 5192 Bytes
- **SHA-256:** `e5eb6884de1d3796bebeabec25f0d14b28cc448d228d99b353b15490f6f5d97c`

## `search_keyword_1.json`

- **Werkzeuge:** `gazette_search_publications`
- **Schluessel:** `https://amtsblattportal.ch/api/v1/publications?publicationStates=PUBLISHED&keyword=Informatik&rubrics=BH&rubrics=HR&rubrics=KA-AR&rubrics=KA-BE&rubrics=KA-BS&rubrics=KA-TI&rubrics=KA-ZG&rubrics=KA-ZH&rubrics=KO-AR&rubrics=KO-BE&rubrics=KO-BS&rubrics=KO-TI&rubrics=KO-ZG&rubrics=KO-ZH&rubrics=OB-AR&rubrics=OB-BL&rubrics=OB-BS&rubrics=OB-TI&rubrics=OB-VS&rubrics=OB-ZG&rubrics=PL-BL&rubrics=PR-BS&rubrics=PR-TI&rubrics=RE-NW&rubrics=RE-OW&rubrics=RE-SH&rubrics=RE-SO&rubrics=RE-SZ&rubrics=RE-VS&rubrics=RP-AR&rubrics=RP-BE&rubrics=RP-BL&rubrics=RP-BS&rubrics=RP-TI&rubrics=RP-ZG&rubrics=RP-ZH&rubrics=RS-AR&rubrics=RS-BE&rubrics=RS-BL&rubrics=RS-BS&rubrics=RS-DA&rubrics=RS-ZG&rubrics=RS-ZH&rubrics=VE-AR&rubrics=VE-BE&rubrics=VE-BS&rubrics=VE-TI&rubrics=VE-ZG&rubrics=VE-ZH&publicationDate.start=2026-08-01&publicationDate.end=2026-08-14&pageRequest.size=5`
- **Auswahl:** 8 von 10 Listeneintraegen (je Liste die ersten 3), aus 6876 Bytes Rohantwort
- **Groesse:** 5777 Bytes
- **SHA-256:** `1969a5db3d00287d7ca5f36b15417d541c721903881ab60c849c21c625dff498`

## `search_procurement_1.json`

- **Werkzeuge:** `gazette_search_procurement`
- **Schluessel:** `https://amtsblattportal.ch/api/v1/publications?publicationStates=PUBLISHED&rubrics=OB-TI&publicationDate.start=2026-08-01&publicationDate.end=2026-08-14&pageRequest.size=5`
- **Auswahl:** 6 von 8 Listeneintraegen (je Liste die ersten 3), aus 6735 Bytes Rohantwort
- **Groesse:** 5655 Bytes
- **SHA-256:** `66d311f27116d9ae2e0262e9017a630a91232a5248784a5d830d260bbb601ea8`
