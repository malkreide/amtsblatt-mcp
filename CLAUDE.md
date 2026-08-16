# CLAUDE.md

## Teil 1 — Portfolio-Konventionen

### Vor der Arbeit

Klon-Aktualität prüfen: `git fetch origin main && git rev-list --count HEAD..origin/main`
Ein veralteter Klon erzeugt eine rote CI, deren Ursache nicht im Diff steht.
Am 3.8.2026 zweimal passiert — beide Male fehlten genau die Commits, die
das Gate einführten, an dem der Branch scheiterte.

Gates lokal fahren, mit der GEPINNTEN ruff-Version aus der CI. Eine andere
Version meldet Abweichungen, die niemand verursacht hat.

### Tests

Gegenprobe ist Pflicht. Ein Test, der grün bleibt, wenn man die
Implementierung entfernt, prüft nichts. Jede neue Zusicherung einzeln
neutralisieren und zeigen, dass genau die zugehörigen Tests fallen.

Zwei Fallen, die beide grün blieben:

- Eine Fake-Uhr, die nur beim Schlafen vorrückt, kann eine Zusicherung über
  echte Zeit nicht widerlegen.
- `monkeypatch.setattr(modul.asyncio, "sleep", ...)` greift ins Modul
  `asyncio` selbst und entschärft die Mechanik im ganzen Prozess. Patche
  einen Modul-Alias (`_sleep = asyncio.sleep`), nicht das fremde Modul.

Handgeschriebene Fixtures kodieren die Annahme des Autors und können sie
nicht widerlegen. Mindestens eine aufgezeichnete Antwort pro externem
Endpunkt, mit Aufnahmedatum.

### Wenn etwas rot ist

Roter Live-Test: erst die Quelle abfragen, dann einordnen. Nicht aus der
Fehlermeldung schliessen. Am 3.8.2026 hiess "nicht gefunden" nicht, dass der
Datensatz weg war, sondern dass die Quelle die Schreibweise ihrer Kopfzeile
gewechselt hatte — vier von sechs Datensätzen produktiv kaputt, alle
Unit-Tests grün.

PR ohne jeden Check ist selten ein Repo ohne CI, meistens ein
Merge-Konflikt: GitHub berechnet dafür keinen Merge-Commit und startet nichts.

Ein Codex-Review auf einem PR wird beantwortet oder behoben, nie ignoriert.

## Teil 2 — Dieses Repo

**ruff: eine Quelle.** Der Pin `0.16.1` steht in `pyproject.toml` — und
**nicht** mehr als eigener Install-Schritt in der CI.

Der CI-Schritt lief nach dem Install der Abhängigkeiten und überschrieb sie.
Eine Abweichung im Pin konnte deshalb in der CI gar nicht auffallen, sondern
nur lokal — wo niemand sie erwartet. Ein manuelles Nachinstallieren von ruff
vor den Gates ist damit nicht mehr nötig und wäre schädlich: Es würde eine
spätere Anhebung hier stillschweigend überstimmen.

**Gates, wörtlich aus `ci.yml`** — Python 3.11/3.12/3.13:

```bash
pip install -e ".[dev]"
PYTHONPATH=src pytest tests/ -m "not live"
ruff check src/ tests/ scripts/
ruff format --check src/ tests/ scripts/
python scripts/check_version_sync.py
PYTHONPATH=src pytest tests/test_allowlist.py -m "not live" -v   # eigener Job
```

Dazu Job `docker`: Image bauen und UID ≥ 10000, seccomp-Modus 2, Read-only-Root,
Start-Verweigerung ohne `MCP_API_KEY`, UID löst auf `mcp` auf.

**Live-Tests:** geplanter Workflow vorhanden — `ci.yml` hat
`schedule: cron "17 3 * * *"` plus Job `live` (`pytest tests/ -m live -v`,
nur bei `schedule`/`workflow_dispatch`). DRIFT-005 ist damit erfüllt; PR-Läufe
schliessen Live-Tests über `-m "not live"` aus, ohne sie fallen zu lassen.

### Wo dieselbe Angabe mehrfach steht

Diese Stellen müssen zusammen geändert werden — sie sind schon einmal
auseinandergelaufen:

- **ruff-Version:** `.github/workflows/ci.yml` und `pyproject.toml` (dev-Extra).
- **Gate-Befehle:** `README.md`, `README.de.md`, `CONTRIBUTING.md`,
  `CONTRIBUTING.de.md` — alle vier nennen dieselben Befehle wie `ci.yml`.
  Nennt die Doku weniger als die CI prüft, ist man lokal grün und in der CI rot.
- **Version:** `pyproject.toml` ↔ `server.json` / README / `src` — dafür gibt es
  ein Gate (`scripts/check_version_sync.py`), das die Divergenz selbst findet.

### Fixtures: aufgezeichnet

`tests/fixtures/` hält sieben echte Antworten, eine je Abfrageform. Herkunft,
Datum, Auswahlregel und SHA-256 je Datei stehen in
`tests/fixtures/PROVENANCE.md`; neu aufzeichnen mit
`PYTHONPATH=src python scripts/record_fixtures.py`, geladen wird über
`tests/fixture_data.py`.

**Nicht zu verwechseln mit `tests/fixtures.py`.** Das sind die gekürzten,
anonymisierten Stubs, und sie bleiben: sie tragen die Fehlerpfade und die
gesperrten Rubriken. Beides lässt sich nicht aufzeichnen — der Server holt es
gerade nicht ab — und beides ist als Erfindung in Ordnung. Was die Stubs nicht
können, ist die Form einer Erfolgs-Antwort belegen.

**Personendaten.** Der Ordner enthält keine, und das ist kein Zufall: der
Recorder fährt ausschliesslich durch die Werkzeuge und damit durch das
Green-Gate, und die Volltexte sind bewusst aus einer Beschaffungsrubrik
gewählt — eine Ausschreibung nennt Vergabestelle und Projekt, ein
HR-Detaileintrag dagegen die Organe mit Namen. Trefferlisten aus HR sind in
Ordnung: sie führen Firmen und Amtsstellen.
`test_keine_aufzeichnung_traegt_eine_gesperrte_rubrik` und
`test_die_volltexte_stammen_aus_der_beschaffung` prüfen das Ergebnis, statt dem
Verfahren zu vertrauen. Wer den Plan erweitert, prüft beides erneut — eine
Aufzeichnung ist eine Datei im Repository, kein flüchtiger Abruf.

**Was nicht gekürzt werden darf.** Kürzen ist nur dort harmlos, wo der Server
die Liste ganz liest. `gazette_list_rubrics` klassiert *jede* Rubrik gegen die
Freigabeliste; auf die ersten Zeilen geschnitten meldete die Taxonomie eine
Drift, die es nicht gibt. Sie liegt deshalb ungekürzt da (152 Rubriken, 825
Subrubriken, rund 930 KB) — und genau das ist ihr Zweck:
`test_jede_freigegebene_rubrik_gibt_es_in_der_taxonomie` hält die 49 Codes der
Freigabeliste gegen die Quelle. `total` bleibt beim Kürzen ebenfalls stehen: die
Quelle meint damit den ganzen Korpus, nicht die Zeilen der Seite.

**Die Publikations-ID des Volltexts wird beim Aufzeichnen gesucht**, nicht fest
verdrahtet. Publikationen laufen ab; eine feste UUID wäre beim nächsten Lauf ein
404. Der Test liest sie aus `PROVENANCE.md` — derselben Quelle, aus der auch der
Dispatcher die Zuordnung Anfrage → Datei nimmt. Der Nachweis trägt hier den
Abspielbetrieb, statt Prosa neben den Dateien zu sein.

Messung vom 15.08.2026, für die Feldbeschreibung von `ProcurementInput.canton`:
OB-AR 387 Publikationen (6 in 30 Tagen), OB-TI 2943 (69), OB-BS 2986 (0),
OB-VS 1053 (0), OB-BL 74 (0), OB-ZG 0 (0). Die Beschreibung nennt AR und TI
aktiv und BS/BL/VS als Archiv — das stimmt inhaltlich, obwohl die Taxonomie
OB-BS und OB-ZG als `active` führt. Das Flag sagt hier nichts über Inhalt.
