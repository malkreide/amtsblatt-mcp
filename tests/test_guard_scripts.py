"""Tests fuer die beiden Guard-Skripte, die zwischen den Portfolio-Repos kopiert werden.

`scripts/check_version_sync.py` und `scripts/check_ruff_pin.py` laufen in der CI
als Gates und hatten selbst keinen Test (Audit 2026-11-21, OPS-005): ein Gate,
das man nicht kaputtmachen kann, ohne dass etwas rot wird, ist kein belegtes
Gate.

Drei Dinge werden hier festgehalten:

- **Formatstabilitaet ueber alle Portfolio-Breiten.** Beide Dateien werden
  kopiert, und im Portfolio stehen line-length 88, 100, 110 und 120 nebeneinander.
  `ruff format --check` in der CI prueft nur die Breite dieses Repos (100) und
  hat deshalb nie gemeldet, dass `check_version_sync.py` bei 88 umbricht —
  obwohl ihr Docstring genau das zusicherte.
- **`check_version_sync.py` schlaegt an**, wenn irgendein `packages[*]` abweicht,
  nicht nur der erste Eintrag.
- **`check_ruff_pin.py` schlaegt an**, wenn ein erreichbares ruff nicht dem Pin
  entspricht, und verweigert ohne Pin.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"

# Die im Portfolio konfigurierten Breiten (88 = ruff-Default, schmalster Wert).
PORTFOLIO_WIDTHS = (88, 100, 110, 120)
COPIED_GUARDS = ("check_version_sync.py", "check_ruff_pin.py")


def _load(name: str) -> ModuleType:
    """Skript als frisches Modul laden, ohne `main()` zu rufen."""
    spec = importlib.util.spec_from_file_location(f"_guard_{name}", SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------
# Formatstabilitaet
# --------------------------------------------------------------------------


@pytest.mark.parametrize("width", PORTFOLIO_WIDTHS)
@pytest.mark.parametrize("script", COPIED_GUARDS)
def test_kopierte_guards_sind_bei_jeder_portfolio_breite_formatgerecht(
    script: str, width: int
) -> None:
    done = subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "format",
            "--no-cache",
            "--check",
            "--line-length",
            str(width),
            str(SCRIPTS / script),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert done.returncode == 0, (
        f"scripts/{script} ist bei line-length {width} nicht formatgerecht und "
        f"faellt beim Kopieren in ein Repo mit dieser Breite um:\n{done.stdout}{done.stderr}"
    )


# --------------------------------------------------------------------------
# check_version_sync.py
# --------------------------------------------------------------------------


def _version_sync_in(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, server: dict) -> ModuleType:
    """Das Skript gegen einen Wegwerf-Baum richten: pyproject, server.json, src/."""
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo-mcp"\nversion = "1.2.3"\n', encoding="utf-8"
    )
    (tmp_path / "server.json").write_text(json.dumps(server), encoding="utf-8")
    (tmp_path / "src").mkdir()
    module = _load("check_version_sync")
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "PYPROJECT", tmp_path / "pyproject.toml")
    monkeypatch.setattr(module, "SERVER_JSON", tmp_path / "server.json")
    monkeypatch.setattr(module, "SRC", tmp_path / "src")
    return module


def _server(*package_versions: str, version: str = "1.2.3") -> dict:
    return {
        "version": version,
        "packages": [{"identifier": "demo-mcp", "version": v} for v in package_versions],
    }


def test_version_sync_besteht_bei_gleichem_stand(tmp_path, monkeypatch, capsys) -> None:
    module = _version_sync_in(tmp_path, monkeypatch, _server("1.2.3", "1.2.3"))
    module.main()
    assert "Versions-Sync OK" in capsys.readouterr().out


def test_version_sync_faellt_bei_abweichender_server_version(tmp_path, monkeypatch) -> None:
    module = _version_sync_in(tmp_path, monkeypatch, _server("1.2.3", version="1.2.2"))
    with pytest.raises(SystemExit) as exc:
        module.main()
    assert exc.value.code == 1


def test_version_sync_faellt_auch_beim_zweiten_package(tmp_path, monkeypatch, capsys) -> None:
    """Der Fall, den der jq-Ausdruck in publish.yml lange nicht abdeckte."""
    module = _version_sync_in(tmp_path, monkeypatch, _server("1.2.3", "0.0.2"))
    with pytest.raises(SystemExit) as exc:
        module.main()
    assert exc.value.code == 1
    assert "packages[1].version" in capsys.readouterr().err


# --------------------------------------------------------------------------
# check_ruff_pin.py
# --------------------------------------------------------------------------


def _ruff_pin_with(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, deps: str) -> ModuleType:
    (tmp_path / "pyproject.toml").write_text(
        f"[project.optional-dependencies]\ndev = [{deps}]\n", encoding="utf-8"
    )
    module = _load("check_ruff_pin")
    monkeypatch.setattr(module, "PYPROJECT", tmp_path / "pyproject.toml")
    return module


def test_ruff_pin_liest_den_exakten_pin(tmp_path, monkeypatch) -> None:
    module = _ruff_pin_with(tmp_path, monkeypatch, '"ruff==1.2.3"')
    assert module.pinned_version() == "1.2.3"


def test_ruff_pin_verweigert_eine_spanne(tmp_path, monkeypatch) -> None:
    module = _ruff_pin_with(tmp_path, monkeypatch, '"ruff>=1.2"')
    with pytest.raises(SystemExit):
        module.pinned_version()


def test_ruff_pin_verweigert_zwei_pins(tmp_path, monkeypatch) -> None:
    module = _ruff_pin_with(tmp_path, monkeypatch, '"ruff==1.2.3", "ruff==1.2.4"')
    with pytest.raises(SystemExit):
        module.pinned_version()


def test_ruff_pin_besteht_wenn_jeder_weg_den_pin_meldet(tmp_path, monkeypatch) -> None:
    module = _ruff_pin_with(tmp_path, monkeypatch, '"ruff==1.2.3"')
    monkeypatch.setattr(module, "reachable", lambda: [("ruff", "1.2.3"), ("py -m ruff", "1.2.3")])
    assert module.main() == 0


def test_ruff_pin_faellt_wenn_ein_weg_abweicht(tmp_path, monkeypatch, capsys) -> None:
    module = _ruff_pin_with(tmp_path, monkeypatch, '"ruff==1.2.3"')
    monkeypatch.setattr(module, "reachable", lambda: [("ruff", "0.9.0"), ("py -m ruff", "1.2.3")])
    assert module.main() == 1
    assert "ruff meldet 0.9.0" in capsys.readouterr().err


def test_ruff_pin_faellt_ohne_erreichbares_ruff(tmp_path, monkeypatch) -> None:
    module = _ruff_pin_with(tmp_path, monkeypatch, '"ruff==1.2.3"')
    monkeypatch.setattr(module, "reachable", lambda: [])
    with pytest.raises(SystemExit):
        module.main()
