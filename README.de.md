> 🇨🇭 **Teil des [Swiss Public Data MCP Portfolio](https://github.com/malkreide)**

# 📰 amtsblatt-mcp

![Version](https://img.shields.io/badge/version-0.1.0-blue)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-Model%20Context%20Protocol-purple)](https://modelcontextprotocol.io/)
[![No Auth Required](https://img.shields.io/badge/auth-none%20required-brightgreen)](https://github.com/malkreide/amtsblatt-mcp)
![CI](https://github.com/malkreide/amtsblatt-mcp/actions/workflows/ci.yml/badge.svg)

> MCP-Server für **amtsblattportal.ch** — das Schweizer Amtsblattportal
> (SHAB + 27 kantonale Amtsblätter). Öffentliche Beschaffung und amtliche
> Bekanntmachungen, **Rubriken mit Personendaten bewusst ausgeschlossen**.

[🇬🇧 English version](README.md)

## Übersicht

Das Amtsblattportal publiziert rund **2,79 Millionen** amtliche Bekanntmachungen:
öffentliche Beschaffung, kantonale und kommunale Mitteilungen, Beschlüsse,
Raumplanung — aber auch Konkurse, Schuldbetreibungen, Schuldenrufe und
Zivilstandseinträge, die natürliche Personen namentlich nennen.

Dieser Server erschliesst nur die erste Gruppe. Rubriken mit systematischen
Personendaten sind **nicht durchsuchbar**, und kein Tool akzeptiert Namen,
Geburtsdatum oder Adresse einer Person. Das ist ein bewusster
Datenschutz-Entscheid, erläutert unter [Datenschutz & Scope](#datenschutz--scope).

**Anker-Demoabfrage:** *«Welche öffentlichen IT-Ausschreibungen wurden in den
letzten drei Monaten im Kanton Basel-Stadt publiziert?»*
→ `search_procurement(canton="BS", keyword="Informatik")` → `get_publication(id=…)`

## Funktionen

- **Fail-closed Freigabe-Liste** — 49 erschlossene von 152 Rubriken; alles
  andere ist standardmässig gesperrt, auch später hinzukommende Rubriken
- **Erklärende Absagen** — eine gesperrte Rubrik liefert das *Warum*, nie ein
  stilles leeres Ergebnis und nie einen Umgehungshinweis
- **Beschaffungs-Logik** — kennt die Tatsache, dass nur AR, BS, TI, ZG hier
  ausschreiben und ZH über simap.ch läuft, und erklärt das statt nichts zu liefern
- **Fristberechnung** in Europe/Zurich, der rechtlich relevanten Zeitzone
- **Sprach-Deduplikation** — eine de/fr/it-Publikation zählt einmal
- **Defensives XML-Parsing** — das Schema ist pro Subrubrik verschieden; kein
  rubrikspezifischer Pfad ist hartcodiert, HTML-escapte Texte werden bereinigt
- **Egress-Allow-List**, Retry mit Backoff, strukturiertes JSON-Logging
- **Markdown- oder JSON-Ausgabe** mit Attribution und `provenance`

## Voraussetzungen

- Python 3.11+
- **Kein API-Key.** Die Lese-API von amtsblattportal.ch ist frei zugänglich.

## Installation

```bash
pip install amtsblatt-mcp
# oder ohne Installation:
uvx amtsblatt-mcp
```

Aus dem Quellcode:

```bash
git clone https://github.com/malkreide/amtsblatt-mcp
cd amtsblatt-mcp
pip install -e ".[dev]"
```

## Konfiguration

### Claude Desktop

```json
{
  "mcpServers": {
    "amtsblatt": {
      "command": "uvx",
      "args": ["amtsblatt-mcp"]
    }
  }
}
```

### Cloud-Deployment (SSE)

```bash
export MCP_TRANSPORT=sse
export MCP_API_KEY="$(openssl rand -hex 32)"   # Pflicht — Start bricht sonst ab
export PORT=8000
amtsblatt-mcp
```

| Variable | Standard | Zweck |
|---|---|---|
| `MCP_TRANSPORT` | `stdio` | `stdio` oder `sse` |
| `MCP_API_KEY` | — | Bearer-Token; **Pflicht** bei SSE |
| `MCP_RATE_LIMIT` / `MCP_RATE_WINDOW` | `60` / `60` | Sliding-Window-Rate-Limit |
| `MCP_ALLOWED_HOSTS` | `amtsblattportal.ch,www.amtsblattportal.ch` | Egress-Allow-List. Ein Override ersetzt den Standard vollständig. |
| `RUBRICS_TTL` | `86400` | Cache-TTL der Taxonomie (Sekunden) |
| `LOG_LEVEL` | `INFO` | Strukturierte JSON-Logs auf stderr |

## Verfügbare Tools

| Tool | Signatur | Hinweise |
|---|---|---|
| `search_publications` | `(keyword?, rubric?, sub_rubric?, canton?, date_start?, date_end?, limit=20, page=0, language='de')` | Nur freigegebene Rubriken. Ohne `rubric` werden alle grünen Rubriken injiziert — eine reine Stichwortsuche erreicht nie eine gesperrte. |
| `search_procurement` | `(keyword?, canton?, date_start?, date_end?, include_inactive=False, limit=20, page=0)` | Nur `OB-*`. Ein Kanton ohne `OB-*`-Rubrik erhält die simap.ch-Erklärung und **keinen HTTP-Call**. Kein CPV — die Quelle kennt keines. |
| `get_publication` | `(id, response_format='markdown')` | Amtlicher Volltext aus dem XML. Prüft die Rubrik nach dem Abruf erneut; Inhalt einer gesperrten Rubrik wird verworfen. |
| `list_rubrics` | `(language='de', rubric_class='green', response_format='markdown')` | `rubric_class='all'` zeigt die vollständige Taxonomie mit Ampelklassen und Begründung — aufgeführt heisst nicht durchsuchbar. |
| `source_status` | `(response_format='markdown')` | Erreichbarkeit, Latenz, Cache-Alter, Scope-Kennzahlen. |

Alle Tools sind `readOnlyHint=True`.

### Anwendungsbeispiele

| Frage | Tool-Kette |
|---|---|
| IT-Ausschreibungen Basel-Stadt dieses Quartal | `search_procurement(canton="BS", keyword="Informatik")` |
| Was ist hier überhaupt abfragbar? | `list_rubrics()` |
| Warum kann ich keine Konkurse suchen? | `list_rubrics(rubric_class="all")` |
| Zonenplanänderungen in Zürich | `search_publications(rubric="RP-ZH")` |
| Volltext einer Bekanntmachung | `get_publication(id="fbf0ff9e-…")` |
| Alles zu einer bestimmten Firma | → [`register-mcp`](https://github.com/malkreide/register-mcp) |

## Datenschutz & Scope

Das Amtsblattportal publiziert systematisch Personendaten **natürlicher**
Personen. Diese Publikationen sind öffentlich — aber sie über einen KI-Agenten
*systematisch namentlich durchsuchbar* zu machen, ist eine Zweckentfremdung, die
die Publikation nie beabsichtigt hat, und nach revidiertem DSG (revDSG) ein
Profiling-Instrument.

Daraus folgen vier Regeln, durchgesetzt im Code, nicht in der Dokumentation:

1. **Allow-List, nie Block-List.** Nicht ausdrücklich grün ⇒ nicht abfragbar.
   Neue Rubriken der Quelle sind standardmässig geschlossen.
2. **Kein Personen-Sucheinstieg** in irgendeiner Tool-Signatur.
3. **Keine Persistenz.** Publikationen haben gesetzliche Löschfristen; ein
   Cache, der sie überdauert, würde sie aktiv unterlaufen. Nur die *Taxonomie*
   wird zwischengespeichert.
4. **Gesperrt ⇒ erklärt.** Nie ein stilles leeres Ergebnis, nie ein Hinweis auf
   eine Umgehung.

### Was ausgeschlossen ist

🔴 Konkurse (`KK`), Schuldbetreibungen (`SB`), Schuldenrufe (`LS`, `SR`),
Nachlass (`NA`), Erbschaft/Testament/Ableben (`ES`, `TE-*`, `VA-*`),
Familie & Zivilstand (`FZ-*`, `BV-*`, `BU-*`), gerichtliche Vorladungen
(`UV`, `GB-*`, `GE-*`, `SJ-BE`), Baugesuche (`BP-*`), Grundbuch (`GR-*`),
Meldungskatalog GR (`AA-GR`).

🟡 Zurückgestellt: Steuerwesen, Anzeigen, Bewilligungen, Bildungs- und
Kirchenwesen sowie die allgemeinen Sammelrubriken.

Der vollständige Audit-Trail — inklusive drei dokumentierter Erweiterungen
gegenüber der Ausgangsspezifikation — steht in
[`docs/rubric-classification.md`](docs/rubric-classification.md).

### Die Grenze zu `register-mcp`

Für Publikationen zu einer bestimmten **Firma** gibt es
[`register-mcp`](https://github.com/malkreide/register-mcp). Dort besteht voller
Rubrikzugriff — inklusive des eigenen Konkurses einer Firma — aber immer nur
über die Firmen-**UID**. Der Konkurs einer Firma ist Unternehmensdatum, kein
Profiling natürlicher Personen, und die UID-Bindung macht eine namentliche
Enumeration unmöglich.

`amtsblatt-mcp` hat die umgekehrte Form: breite Suche, enge Rubriken. Der
`uids`-Parameter der Quelle wird hier gar nicht erst angeboten.

## Architektur

```
   Claude / MCP-Client
            │
      amtsblatt-mcp
            │
   ┌────────┴────────┐
   │  Green Gate     │  ← rubrics.py: fail-closed Allow-List
   └────────┬────────┘     (geprüft im Tool UND im Query-Builder)
            │
   ┌────────┴────────┐
   │  Parameter-     │  ← Silent-Ignore-Schutz
   │  Allow-List     │  ← Silent-Empty-Schutz (Taxonomie-Validierung)
   └────────┬────────┘  ← Plausibilitätsprüfung (Korpusgrösse)
            │
   ┌────────┴────────┐
   │ Egress-Allow-   │
   │ List (httpx)    │
   └────────┬────────┘
            │
  amtsblattportal.ch/api/v1
   /publications · /publications/{id}/xml · /rubrics · /tenants
```

**Architektur A (nur Live-API).** Die Endpunkte antworten stabil ohne
Authentifizierung, daher wird kein Bulk-Dump gepflegt.

### Verifizierte Eigenheiten der Quelle (live geprüft 2026-07-20)

| Eigenheit | Verhalten | Schutz |
|---|---|---|
| **Silent Ignore** | Ein unbekannter Parameter*name* liefert HTTP 200 und den **vollen Korpus**. `canton=ZH` (Singular-Tippfehler) verwirft den Filter still. | Query-Parameter ausschliesslich aus `ALLOWED_GAZETTE_PARAMS`; Plausibilitätsprüfung verwirft Ergebnisse > 2 000 000. |
| **Silent Empty** | Ein unbekannter Rubrik*wert* liefert HTTP 200 mit `total: 0` — ununterscheidbar von einem echten Nulltreffer. | Jeder Code wird **vor** dem Call gegen die Taxonomie validiert. |
| **Nur Metadaten** | Listen-Endpunkt und `GET /publications/{id}` liefern beide `content: null`. | Volltext nur über `/publications/{id}/xml`. |
| **Sortierung ignoriert** | `pageRequest.sortOrders` wird mit 200 akzeptiert, bleibt aber wirkungslos; `sortOrders` kommt als `[]` zurück. | Clientseitig sortiert. |
| **Fehlendes `publicationStates`** | Liefert **401**, nicht 400 — bedeutet *nicht*, dass Zugangsdaten nötig sind. | Wird immer injiziert; die 401-Meldung sagt das. |
| **Keine Seitengrössen-Grenze** | `pageRequest.size=2000` liefert 2000 Einträge. | Clientseitige Grenze von 100. |
| **Inkonsistente Pluralformen** | `rubrics`/`cantons`/`subRubrics` sind Plural, `keyword`/`tenant` Singular. | Exakte Schreibweisen kodiert, keine Pluralisierungsregel. |

## Bekannte Einschränkungen

- **Ungleiche kantonale Abdeckung.** Nur 16 von 29 Mandanten publizieren eine
  eigene Rubriktaxonomie; AG, FR, GE, GL, JU, LU, NE, UR sind noch unvollständig.
- **Löschfristen.** Publikationen fallen mit der Zeit aus der API — daher nur
  Durchreichen, keine Persistenz.
- **Beschaffungsgrenze.** Die meisten Kantone, auch **Zürich**, publizieren
  Ausschreibungen über simap.ch ausserhalb dieses Portals. Es gibt kein
  `OB-ZH`, und CPV-Klassifikation existiert hier nicht.
- **Kein Push.** Nur Polling; kein Abo- oder Webhook-Mechanismus.
- **Rechtsverbindlich** ist das signierte PDF, nicht diese API.

## Tests

```bash
pip install -e ".[dev]"
PYTHONPATH=src pytest tests/ -m "not live"   # 75 Tests, ohne Netzwerk
PYTHONPATH=src pytest tests/ -m live         # gegen die echte API
ruff check src/ tests/
```

Die Suite deckt den verbindlichen Portfolio-Satz ab: Suche in grüner Rubrik mit
Quell-URL, **gesperrte Rubrik → Erklärung mit null HTTP-Calls**, Kantonsfilter,
Fristberechnung in Europe/Zurich gegen ein fixes «heute», Pagination über eine
Seitengrenze, Sprach-Deduplikation, Boolean-Normalisierung und Verhalten bei
nicht erreichbarer API. Die Fixtures sind gekürzte echte Antworten, konsistent
anonymisiert — keine echten Personendaten.

## Projektstruktur

```
amtsblatt-mcp/
├── src/amtsblatt_mcp/
│   ├── rubrics.py       # Fail-closed Freigabe-Liste — der Scope-Entscheid
│   ├── server.py        # FastMCP-Server, 5 Tools, Quirk-Schutz, XML-Parsing
│   ├── _log.py          # Strukturiertes JSON-Logging + Tool-Call-Events
│   ├── _middleware.py   # Bearer-Auth + Rate-Limit (nur SSE)
│   └── _otel.py         # Optionale OpenTelemetry-Anbindung
├── tests/
│   ├── test_allowlist.py    # Datenschutz-Invarianten (eigener CI-Job)
│   ├── test_search.py       # Suche, Beschaffung, Pagination, Dedup, Fehler
│   ├── test_publication.py  # XML-Parsing, Fristen, Egress-Allow-List
│   └── fixtures.py          # Anonymisierte echte Antworten
├── docs/
│   └── rubric-classification.md   # Warum jede der 152 Rubriken offen/zu ist
├── Dockerfile · compose.yaml      # Gehärteter Container, non-root, read-only
└── server.json                    # MCP-Registry-Manifest
```

## Changelog

Siehe [CHANGELOG.md](CHANGELOG.md).

## Mitwirken

Siehe [CONTRIBUTING.md](CONTRIBUTING.md). Änderungen an
[`src/amtsblatt_mcp/rubrics.py`](src/amtsblatt_mcp/rubrics.py) brauchen eine
explizite Begründung in der PR-Beschreibung: eine Rubrik freizugeben ist ein
Datenschutz-Entscheid, kein Feature.

## Sicherheit

Siehe [SECURITY.md](SECURITY.md) für Meldewege und Härtungshinweise.

## Lizenz

MIT — siehe [LICENSE](LICENSE).

Datenquelle: **amtsblattportal.ch**, betrieben durch das SECO /
Staatssekretariat für Wirtschaft im Auftrag des Bundes. Frei nutzbar, aber ohne
Gewähr für Vollständigkeit oder Richtigkeit. Rechtsverbindlich ist allein das
signierte PDF einer Publikation.

## Autor

Hayal Oezkan · [malkreide](https://github.com/malkreide)

## Credits & verwandte Projekte

Teil des **Swiss Public Data MCP Portfolio**:

- [`register-mcp`](https://github.com/malkreide/register-mcp) — Zefix
  Handelsregister mit UID-Join zu den Amtsblättern
