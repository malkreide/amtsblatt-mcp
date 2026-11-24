"""Tests fuer die Schritte in publish.yml, die Werte zur Laufzeit ueberschreiben.

Ein Wert, den die Pipeline beim Veroeffentlichen ersetzt, wird sonst nie geprueft
(IDENT-003): `check_version_sync.py` haelt die *committete* `server.json`, aber
was der jq-Ausdruck im Publish *schreibt*, sah kein Test. Der Ausdruck setzte nur
`packages[0].version` — bei einem zweiten Package-Eintrag waere das publizierte
Manifest still desynchron gewesen (Audit 2026-11-21).

Dazu der Download von `mcp-publisher`: `curl | tar` ohne `pipefail` laesst den
Exit-Code von `tar` entscheiden (OPS-005). Dass ein Download-Fehler heute trotzdem
auffaellt, verdankt sich nur `tar`, das an der Fehlerseite scheitert.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

PUBLISH = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "publish.yml"


def _step(name: str) -> str:
    """Text eines Schritts in publish.yml, von `- name: <name>` bis zum naechsten Schritt."""
    text = PUBLISH.read_text(encoding="utf-8")
    match = re.search(
        rf"^\s+- name: {re.escape(name)}\n(.*?)(?=^\s+- (?:name|uses):|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    assert match, f"Schritt {name!r} nicht in publish.yml gefunden"
    return match.group(1)


def _jq_expression() -> str:
    step = _step("Sync server.json version to the published artifact")
    match = re.search(r"""jq --arg v "\$VERSION" '([^']+)'""", step)
    assert match, "jq-Aufruf im Sync-Schritt nicht gefunden"
    return match.group(1)


def test_jq_ausdruck_setzt_jeden_package_eintrag() -> None:
    expr = _jq_expression()
    assert ".packages[0]" not in expr, (
        f"publish.yml setzt nur den ersten Package-Eintrag: {expr!r}. "
        "Ein zweiter Eintrag bliebe im publizierten Manifest auf der alten Version."
    )
    assert ".packages[].version = $v" in expr, expr


@pytest.mark.skipif(
    shutil.which("jq") is None, reason="jq nicht installiert (ubuntu-latest hat es)"
)
def test_jq_ausdruck_ergibt_ein_durchgehend_synchrones_manifest(tmp_path: Path) -> None:
    """Den Ausdruck ausfuehren, nicht nur lesen — jq ist still bei Pfaden, die fehlen."""
    manifest = {
        "version": "0.0.1",
        "packages": [{"registryType": "pypi", "version": "0.0.1"}, {"version": "0.0.2"}],
    }
    source = tmp_path / "server.json"
    source.write_text(json.dumps(manifest), encoding="utf-8")
    done = subprocess.run(
        ["jq", "--arg", "v", "9.9.9", _jq_expression(), str(source)],
        capture_output=True,
        text=True,
        check=True,
    )
    out = json.loads(done.stdout)
    assert out["version"] == "9.9.9"
    assert [p["version"] for p in out["packages"]] == ["9.9.9", "9.9.9"]


def test_publisher_download_kann_nicht_still_scheitern() -> None:
    step = _step("Install mcp-publisher")
    assert "set -o pipefail" in step, "curl | tar ohne pipefail: tar bestimmt den Exit-Code"
    curl = re.search(r"curl\s+(-\S+)", step)
    assert curl and "f" in curl.group(1), (
        "curl ohne --fail liefert bei HTTP 404 die Fehlerseite mit Exit 0 an tar weiter"
    )
