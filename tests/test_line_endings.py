"""Zeilenenden: alles mit Shebang muss LF behalten.

Am 19.08.2026 war der SessionStart-Hook auf einem frisch geklonten
Windows-Rechner tot. Git checkt dort standardmaessig mit CRLF aus
(`core.autocrlf=true`), und ein `#!/bin/sh`-Skript mit CRLF scheitert an jeder
Zeile — `$'\\r': command not found`.

Der Fehler war deshalb so teuer, weil er sich versteckt: der Hook ist so
gebaut, dass er nie blockiert und bei nichts zu melden schweigt. Startet er
wegen CRLF gar nicht erst, sieht das exakt aus wie ein aktueller Klon. Eine
stille Pruefung, die gar nicht laeuft, ist schlimmer als keine — man verlaesst
sich auf sie.

Diese Tests laufen auf Linux trivial durch. Ihr Zweck ist die andere
Plattform: auf einem Windows-Klon ohne `.gitattributes` faellt der erste Test,
und zwar bevor jemand dem schweigenden Hook glaubt.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
GITATTRIBUTES = REPO_ROOT / ".gitattributes"


def _tracked_files() -> list[str]:
    done = subprocess.run(
        ("git", "ls-files", "-z"),
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [name for name in done.stdout.split("\0") if name]


def _hat_shebang(pfad: Path) -> bool:
    try:
        with pfad.open("rb") as fh:
            return fh.read(2) == b"#!"
    except OSError:  # pragma: no cover - im Repo liest sich jede Datei
        return False


def _dateien_mit_shebang() -> list[Path]:
    treffer = [REPO_ROOT / name for name in _tracked_files()]
    return [p for p in treffer if p.is_file() and _hat_shebang(p)]


def test_es_gibt_ueberhaupt_dateien_mit_shebang() -> None:
    """Vorbedingung: sonst prueft der naechste Test eine leere Liste."""
    assert _dateien_mit_shebang(), "keine ausfuehrbaren Skripte gefunden"


def test_kein_skript_mit_shebang_traegt_crlf() -> None:
    kaputt = [
        p.relative_to(REPO_ROOT).as_posix()
        for p in _dateien_mit_shebang()
        if b"\r\n" in p.read_bytes()
    ]
    assert not kaputt, (
        "CRLF in Skripten mit Shebang: "
        + ", ".join(kaputt)
        + " — der Klon wurde ohne .gitattributes-Wirkung ausgecheckt. "
        "Reparieren mit: git rm --cached -r . && git reset --hard"
    )


def test_gitattributes_existiert() -> None:
    assert GITATTRIBUTES.is_file(), "ohne .gitattributes checkt git auf Windows mit CRLF aus"


@pytest.mark.parametrize(
    "pfad",
    [".claude/hooks/session-start.sh", "scripts/record_fixtures.py"],
)
def test_git_erzwingt_lf_fuer_skripte(pfad: str) -> None:
    """Nicht der Dateiinhalt, sondern die Regel wird geprueft.

    `git check-attr` beantwortet genau die Frage, die auf Windows falsch
    ausging: womit checkt git diese Datei aus?
    """
    done = subprocess.run(
        ("git", "check-attr", "eol", "--", pfad),
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert done.stdout.strip().endswith(": eol: lf"), (
        f"{pfad} ist nicht auf LF festgelegt: {done.stdout.strip()!r}"
    )
