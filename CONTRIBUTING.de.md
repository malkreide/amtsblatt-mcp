# Mitwirken an amtsblatt-mcp

[🇬🇧 English Version](CONTRIBUTING.md)

Vielen Dank für dein Interesse an einer Mitwirkung! Dieser Server ist Teil des [Swiss Public Data MCP Portfolios](https://github.com/malkreide).

## Probleme melden

Öffne ein GitHub-Issue mit dem Tool-Call, den Parametern und dem erwarteten
Ergebnis. Für alles, was die Rubrik-Allow-List betrifft, zuerst
[SECURITY.md](SECURITY.md) lesen — einiges davon gehört in ein privates Advisory.

## Pull Requests

1. Forken und einen Branch von `main` erstellen.
2. `pip install -e ".[dev]"`
3. Die Änderung vornehmen.
4. `PYTHONPATH=src pytest tests/ -m "not live"` — alles grün.
5. `ruff check src/ tests/ scripts/` und `ruff format --check src/ tests/ scripts/`
   — sauber. Beide laufen über dieselben drei Verzeichnisse wie in der CI; die
   gepinnte ruff-Version kommt aus dem `dev`-Extra in Schritt 2.
6. `python scripts/check_version_sync.py` — besteht.
7. [Conventional Commits](https://www.conventionalcommits.org/) verwenden (`feat:`,
   `fix:`, `docs:`, `refactor:`, `test:`, `chore:`).

## Änderungen an der Rubrik-Allow-List

**Das ist die eine Änderung, die mehr braucht als eine bestandene Testsuite.**

`src/amtsblatt_mcp/rubrics.py` entscheidet, welche Personendaten ein KI-Agent
systematisch abfragen kann. Eine Rubrik freizugeben ist ein
Datenschutz-Entscheid, kein Feature. Ein PR, der `GREEN_RUBRICS` oder
`GREEN_SUB_RUBRICS` berührt, muss:

- Den Rubrik-Code und seinen deutschen Titel aus der Live-Taxonomie nennen.
- Angeben, welche Art von Person darin vorkommt und in welcher Rolle.
  «Institutionell» ist eine Schlussfolgerung, kein Beleg — die Struktur einer
  echten Publikation zitieren.
- [`docs/rubric-classification.md`](docs/rubric-classification.md) im selben
  Commit aktualisieren.
- Die Menge **literal** halten. Nie Präfix- oder Glob-Matching einführen; ein
  Glob gibt künftige Rubriken der Quelle ohne Prüfung frei — genau das, was die
  Fail-closed-Regel verbietet. `test_green_set_is_literal_codes_not_globs`
  erzwingt das.

Wenn die Taxonomie der Quelle wächst, schlägt
`test_every_live_rubric_is_explicitly_classified` fehl. Das ist beabsichtigt:
die neue Rubrik ist bereits gesperrt, und der fehlschlagende Test ist die
Aufforderung, sie bewusst zu klassifizieren, statt sie auf dem impliziten
Standard zu belassen.

## Code-Stil

- Python 3.11+, Type Hints erforderlich.
- Ruff, Zeilenlänge 100.
- Den bestehenden MCPServer-/Pydantic-v2-Mustern in `server.py` folgen: ein
  Pydantic-Input-Modell pro Tool, deutsche Docstrings im Google-Stil, Tools
  geben `str` zurück und werfen nie — Fehler kommen als erklärende Meldungen
  zurück.
- Neue Tools brauchen Tests. Tools, die Rubriken berühren, brauchen
  Allow-List-Tests.

## Test-Konventionen

- `respx` mockt httpx; Fixtures liegen in `tests/fixtures.py` als Python-Literale.
- Tools werden direkt aufgerufen (`await gazette_search_publications(SearchInput(...))`),
  nicht über einen MCP-Client.
- Auf die ausgehende Query mit `route.calls[0].request.url.params` prüfen.
- Für alles Gesperrte `route.call_count == 0` prüfen — der Punkt ist, dass kein
  Request gestellt wurde, nicht bloss, dass keine Daten zurückkamen.
- Live-Tests tragen `@pytest.mark.live` und sind in der CI ausgeschlossen.
- Fixtures dürfen **keine echten Personendaten** enthalten, konsistent
  anonymisiert.

## Datenquellen

**No-Auth-First:** Dieser Server zielt auf die frei zugängliche Lese-API von
amtsblattportal.ch. Funktionen, die Zugangsdaten brauchen (Publizieren, Abruf
unveröffentlichter Datensätze), sind ausserhalb des Scopes.

## Die Live-Suite: wann sie läuft, und wer ein rotes Ergebnis sieht

**Kadenz:** täglich 03:17 UTC, dazu jederzeit von Hand über *Actions → CI → Run
workflow*. Siehe [`.github/workflows/ci.yml`](.github/workflows/ci.yml).

**Wer es sieht:** Ein roter Lauf öffnet ein Issue mit dem Titel `Live-Tests gegen amtsblattportal.ch
rot …` und dem Label `upstream` — und kommentiert das bestehende, statt ein
zweites aufzumachen. Wird die Suite wieder grün, wird es geschlossen. Die
Live-Suite steckt im `live`-Job von `ci.yml`; bei Pull Requests wird er
übersprungen.

**Drei Antworten, nicht zwei.** `scripts/classify_live_run.py` liest das JUnit-XML statt des
Exit-Codes und unterscheidet: `clear` (gelaufen, grün), `finding` (gelaufen,
etwas gefallen) und `unknown` (nicht gelaufen — Installation gescheitert, null
Tests eingesammelt, alle übersprungen). Ein `unknown` schliesst nie ein Issue:
Zuzumachen hiesse zu behaupten, der Vergleich sei gelaufen.

**Ein roter Live-Lauf heisst nicht zwingend «unser Fehler».** Er heisst: Der
Vertrag mit der Quelle hat sich geändert, oder die Quelle ist gerade aus. Beides
gehört gesehen, nur das Erste gehört gefixt. Bitte den Lauf lesen, bevor der Job
deaktiviert wird — so stirbt dieser Check, und er ist der einzige im Repo, der
einer falschen Grundannahme über amtsblattportal.ch widersprechen kann. Jeder andere Test
prüft gegen eine Fixture, und die Fixture ist aus derselben Annahme geschrieben
wie der Code.

## Lizenz

Mit deinem Beitrag erklärst du dich einverstanden, dass deine Beiträge unter der
MIT-Lizenz dieses Projekts lizenziert werden.
