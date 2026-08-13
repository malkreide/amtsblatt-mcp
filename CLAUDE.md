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

**ruff:** CI pinnt `ruff==0.16.1` (`.github/workflows/ci.yml`). Eine
`.pre-commit-config.yaml` existiert nicht; die einzige zweite Quelle ist
`pyproject.toml` → `[project.optional-dependencies].dev` mit `ruff>=0.4.0`,
also ungepinnt. `pip install -e ".[dev]"` installiert lokal daher eine
beliebige neuere Version — **lokal vor dem Gate `pip install ruff==0.16.1`
nachziehen.** (Befund, siehe unten.)

**Gates, wörtlich aus `ci.yml`** — Python 3.11/3.12/3.13:

```bash
pip install -e ".[dev]" && pip install ruff==0.16.1
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

### Befunde

1. **ruff-Version divergiert.** CI: `0.16.1` gepinnt. `pyproject.toml` dev-Extra:
   `ruff>=0.4.0`. Keine `.pre-commit-config.yaml`, die den Pin lokal erzwingt.
2. **Gate-Umfang divergiert.** `README.md`, `README.de.md`, `CONTRIBUTING.md`,
   `CONTRIBUTING.de.md` nennen `ruff check src/ tests/`; die CI prüft zusätzlich
   `scripts/` und fährt `ruff format --check`. Wer der Doku folgt, ist lokal
   grün und in der CI rot.
