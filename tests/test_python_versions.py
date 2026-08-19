"""Die unterstuetzten Python-Versionen stehen an vier Stellen.

`CLAUDE.md` fuehrt eine Liste von Angaben, die schon einmal auseinandergelaufen
sind. Die Python-Version gehoert dazu: sie steht in der CI-Matrix, in den
Classifiers, im `requires-python`-Boden und im Dockerfile.

Beim Aufnehmen von 3.14 fiel auf, dass das ausgelieferte Image bereits
`python:3.14-slim` fuhr, waehrend die Matrix nur 3.11 bis 3.13 pruefte — der
Container lief also produktiv auf einer Version, die nie getestet wurde. Genau
diese Drift faengt `test_das_image_laeuft_auf_einer_getesteten_version`.

Geprueft wird gegen die Dateien, nicht gegen eine Kopie der Liste in diesem
Test: eine fest verdrahtete Erwartung hier waere eine fuenfte Stelle, die
mitwandern muesste.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CI = REPO_ROOT / ".github" / "workflows" / "ci.yml"
PYPROJECT = REPO_ROOT / "pyproject.toml"
DOCKERFILE = REPO_ROOT / "Dockerfile"


def _matrix_versionen() -> list[str]:
    """Die Matrix aus `ci.yml`, als Text gelesen — pyyaml ist keine Abhaengigkeit."""
    treffer = re.search(r"python-version:\s*\[([^\]]+)\]", CI.read_text(encoding="utf-8"))
    assert treffer, "python-version-Matrix in ci.yml nicht gefunden"
    return re.findall(r"\d+\.\d+", treffer.group(1))


def _pyproject() -> dict:
    with PYPROJECT.open("rb") as fh:
        return tomllib.load(fh)


def _classifier_versionen() -> list[str]:
    muster = re.compile(r"^Programming Language :: Python :: (\d+\.\d+)$")
    gefunden = []
    for eintrag in _pyproject()["project"]["classifiers"]:
        treffer = muster.match(eintrag)
        if treffer:
            gefunden.append(treffer.group(1))
    return gefunden


def _als_zahlen(versionen: list[str]) -> list[tuple[int, int]]:
    return sorted(tuple(int(teil) for teil in v.split(".")) for v in versionen)  # type: ignore[misc]


def test_die_matrix_ist_nicht_leer() -> None:
    """Vorbedingung: eine leere Matrix liesse jeden Vergleich unten trivial passieren."""
    assert len(_matrix_versionen()) >= 2


def test_matrix_und_classifiers_nennen_dieselben_versionen() -> None:
    matrix = set(_matrix_versionen())
    classifiers = set(_classifier_versionen())
    assert matrix == classifiers, (
        f"CI testet {sorted(matrix)}, die Classifiers nennen {sorted(classifiers)} — "
        "PyPI verspricht damit etwas anderes als die CI belegt"
    )


def test_der_requires_python_boden_ist_die_kleinste_getestete_version() -> None:
    boden = _pyproject()["project"]["requires-python"]
    treffer = re.fullmatch(r">=\s*(\d+\.\d+)", boden.strip())
    assert treffer, f"unerwartete Form von requires-python: {boden!r}"
    kleinste = _als_zahlen(_matrix_versionen())[0]
    assert tuple(int(t) for t in treffer.group(1).split(".")) == kleinste, (
        f"requires-python sagt {boden!r}, die kleinste getestete Version ist "
        f"{'.'.join(str(t) for t in kleinste)}"
    )


def test_das_ruff_ziel_ist_der_requires_python_boden() -> None:
    """Ein hoeheres Ziel wuerde Syntax durchlassen, die auf dem Boden nicht laeuft."""
    ziel = _pyproject()["tool"]["ruff"]["target-version"]
    boden = _pyproject()["project"]["requires-python"].strip().removeprefix(">=").strip()
    assert ziel == "py" + boden.replace(".", ""), (
        f"ruff target-version ist {ziel!r}, requires-python sagt {boden!r}"
    )


def test_das_image_laeuft_auf_einer_getesteten_version() -> None:
    """Der Fall, der diesen Test veranlasst hat.

    Das Dockerfile fuhr `python:3.14-slim`, waehrend die Matrix bei 3.13
    endete. Ein Image auf einer ungetesteten Version ist kein Detail: es ist
    das, was ausgeliefert wird.
    """
    gefunden = set(re.findall(r"FROM\s+python:(\d+\.\d+)", DOCKERFILE.read_text(encoding="utf-8")))
    assert gefunden, "keine python:-Basis im Dockerfile gefunden"
    matrix = set(_matrix_versionen())
    ungetestet = sorted(gefunden - matrix)
    assert not ungetestet, (
        f"das Image laeuft auf {ungetestet}, die CI testet aber nur {sorted(matrix)}"
    )
