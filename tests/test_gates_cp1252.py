"""Jedes Gate endet unter cp1252 wie unter UTF-8 (OPS-005, Modus 5).

Unter Windows mit umgeleiteter Ausgabe (Pipe, Agent, Hook) schreibt Python
stdout in cp1252. Ein Zeichen ausserhalb davon bricht das Gate dann mit
`UnicodeEncodeError` ab, auch wenn die Pruefung bestanden hat. Im interaktiven
Fenster und auf dem Linux-Runner faellt das nicht auf; deshalb wird die
Kodierung hier erzwungen.

Der Test kennt keine Meldung: Er vergleicht jedes Gate mit seinem Lauf unter
UTF-8. Er gilt damit fuer ein gruenes wie fuer ein rotes Gate und ueberlebt
jede Umformulierung.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# Was Hook und Workflows aufrufen und hier ohne Argumente und Netz laeuft,
# ohne etwas zu schreiben.
GATES = ["scripts/check_ruff_pin.py", "scripts/check_version_sync.py"]

# Erwaehnt, aber hier nicht gefahren. Der Grund ist Pflicht. Eine Ausnahme
# entlastet nicht: Das Skript ist sichtbar ungeprueft, nicht geprueft.
_LIVE = "braucht JUnit-Bericht und --pytest-exit, schreibt nach $GITHUB_OUTPUT"
NICHT_GEFAHREN = {
    "scripts/classify_live_run.py": _LIVE,
}

# Wo ein Gate aufgerufen werden kann. Der SessionStart-Hook ruft heute kein
# Skript auf; er steht hier, damit ein neuer Aufruf dort nicht ungeprueft bleibt.
QUELLEN = [
    ".pre-commit-config.yaml",
    ".claude/hooks/*.sh",
    ".github/workflows/*.yml",
    ".github/workflows/*.yaml",
]


def _lauf(gate: str, kodierung: str) -> subprocess.CompletedProcess[str]:
    # os.environ kopieren statt neu bauen: Ohne SYSTEMROOT scheitert unter
    # Windows schon der Subprozess (WinError 10106), nicht das Gate.
    env = {**os.environ, "PYTHONIOENCODING": kodierung, "PYTHONUTF8": "0"}
    return subprocess.run(
        [sys.executable, gate],
        cwd=ROOT,
        env=env,
        capture_output=True,
        encoding=kodierung,
        errors="replace",
        timeout=120,
    )


@pytest.mark.parametrize("gate", GATES)
def test_gate_endet_unter_cp1252_wie_unter_utf8(gate: str) -> None:
    # Ohne Datei enden beide Laeufe mit 2 und ohne Traceback: gruen, nichts geprueft.
    assert (ROOT / gate).is_file(), gate
    soll = _lauf(gate, "utf-8")
    ist = _lauf(gate, "cp1252")
    assert "Traceback (most recent call last)" not in ist.stderr, ist.stderr
    assert ist.returncode == soll.returncode, ist.stderr


def test_jedes_erwaehnte_skript_ist_eingeordnet() -> None:
    erwaehnt: set[str] = set()
    for muster in QUELLEN:
        for quelle in ROOT.glob(muster):
            text = quelle.read_text(encoding="utf-8")
            erwaehnt |= set(re.findall(r"scripts/[\w-]+\.py", text))
    gefahren, ausgenommen = set(GATES), set(NICHT_GEFAHREN)
    offen = erwaehnt - gefahren - ausgenommen
    assert not offen, f"weder gefahren noch ausgenommen: {sorted(offen)}"
    veraltet = ausgenommen - erwaehnt
    assert not veraltet, f"Ausnahme ohne Skript: {sorted(veraltet)}"
    assert not gefahren & ausgenommen, sorted(gefahren & ausgenommen)
    assert all(grund.strip() for grund in NICHT_GEFAHREN.values())
