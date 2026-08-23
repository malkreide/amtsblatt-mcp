"""ARCH-012: die beiden Spec-Revisionen, gegen die dieser Server geprueft ist.

`mcp` 2.x bedient ZWEI Protokoll-Aeren ueber denselben Server; die erste
Anfrage einer Verbindung entscheidet, welche gilt:

* die **Legacy-Aera** mit `initialize`-Handshake — was heutige Clients
  sprechen. Sie deckelt bei `LATEST_HANDSHAKE_VERSION`.
* die **Modern-Aera** mit Pro-Request-Envelope, die `LATEST_MODERN_VERSION`
  erreicht.

`MCP_PROTOCOL_VERSION` beschreibt die MODERNE Aera. Das war bisher nicht gesagt,
und die Zusicherung daneben zeigte auf `LATEST_PROTOCOL_VERSION` — ein Alias
auf genau diese Version. Derselbe Wert, aber der Name verschweigt, dass es eine
zweite Aera gibt, und die konnte damit frei wandern. Sie steht jetzt daneben.

**Der Wert der Konstante aendert sich nicht.** Er war richtig, nur
unvollstaendig beschrieben — anders als in `bag-epl-mcp` und `parlament-mcp`,
wo eine Konstante drei Revisionen hinterherhinkte und korrigiert werden musste.

Nachgemessen statt aus Konstantennamen geschlossen: der Teil unten faehrt einen
echten `initialize` durch den zusammengebauten ASGI-Stack.
"""

from __future__ import annotations

import json
import pathlib
import re

import httpx
import pytest
from mcp.types.version import (
    LATEST_HANDSHAKE_VERSION,
    LATEST_MODERN_VERSION,
    LATEST_PROTOCOL_VERSION,
)

from amtsblatt_mcp._app import MCP_PROTOCOL_VERSION
from amtsblatt_mcp.server import build_http_app

REPO = pathlib.Path(__file__).resolve().parents[1]

# Datei und Ueberschrift, unter der die Revisionen dokumentiert stehen.
README_SECTIONS = (
    ("README.md", "## MCP Protocol Version"),
    ("README.de.md", "## MCP Protocol Version"),
)

# Derselbe Schluessel wie in `tests/test_cors.py`: der Server weist ohne ihn
# jede Anfrage mit 401 ab, und beide Dateien sollen dieselbe Verdrahtung fahren.
API_KEY = "test-key-not-a-real-secret"


@pytest.fixture(autouse=True)
def _api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_API_KEY", API_KEY)


# Die Obergrenze der Handshake-Aera. Sie steht hier und nicht im `src/`: der
# Server setzt sie nicht, das SDK bestimmt sie. Eine zweite Konstante im
# Auslieferungspfad waere eine zweite Wahrheit, die driften kann.
DOCUMENTED_HANDSHAKE_VERSION = "2025-11-25"


def test_der_pin_nennt_die_moderne_revision_des_installierten_sdk() -> None:
    """Wie bisher, nur gegen die benannte Konstante statt gegen den Alias.

    Faellt das hier, ist die Loesung nicht, den Wert blind nachzuziehen: erst
    das Spec-Changelog zwischen den beiden Revisionen lesen, das
    Serververhalten pruefen, dann Konstante, READMEs und `CHANGELOG.md` in
    einem Commit anheben.
    """
    assert MCP_PROTOCOL_VERSION == LATEST_MODERN_VERSION, (
        f"gepinnt {MCP_PROTOCOL_VERSION}, das SDK erreicht modern {LATEST_MODERN_VERSION}"
    )


def test_die_handshake_aera_steht_wo_die_readmes_sie_nennen() -> None:
    """Die Aera, die bestehende Clients sprechen — und die bisher niemand hielt.

    Ein Client, der ueber den `initialize`-Handshake nach der modernen Revision
    fragt, bekommt diese Obergrenze zurueck, nicht das, wonach er gefragt hat.
    """
    assert LATEST_HANDSHAKE_VERSION == DOCUMENTED_HANDSHAKE_VERSION, (
        f"das SDK deckelt den Handshake jetzt bei {LATEST_HANDSHAKE_VERSION}, "
        f"die READMEs sagen {DOCUMENTED_HANDSHAKE_VERSION}"
    )


def test_latest_protocol_version_ist_der_alias_auf_die_moderne_aera() -> None:
    """Die Falle, gegen die dieses Repo abgesichert wird, benannt.

    Die urspruengliche Zusicherung lautete `PIN == LATEST_PROTOCOL_VERSION` und
    las sich vollstaendig. Sie war es nicht, und man sieht es dem Namen nicht
    an. Faellt dieser Test, hat das SDK die Bedeutung des Alias geaendert —
    dann ist die Aufteilung oben neu zu bewerten, nicht nur eine Zahl.
    """
    assert LATEST_PROTOCOL_VERSION == LATEST_MODERN_VERSION
    assert LATEST_PROTOCOL_VERSION != LATEST_HANDSHAKE_VERSION


def test_die_beiden_aeren_sind_verschieden() -> None:
    """Sagt, wann die Aufteilung oben wieder verschwinden darf: legt das SDK
    die Aeren eines Tages zusammen, ist sie redundant und gehoert zurueckgebaut.
    """
    assert LATEST_MODERN_VERSION > LATEST_HANDSHAKE_VERSION


def test_die_pins_sind_datierte_revisionen_und_keine_beweglichen_ziele() -> None:
    """«latest» oder eine Spanne waeren keine Festlegung."""
    for value in (MCP_PROTOCOL_VERSION, DOCUMENTED_HANDSHAKE_VERSION):
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", value), value


def test_beide_readmes_nennen_beide_revisionen() -> None:
    """Ein Pin, den die Doku anders angibt, ist kein Pin.

    Jede Sprache einzeln geprueft: im Portfolio sind EN und DE desselben Repos
    schon dreimal auseinandergelaufen, weil nur eine Fassung nachgezogen wurde
    und niemand die andere daneben gelegt hat.
    """
    for name, anchor in README_SECTIONS:
        text = (REPO / name).read_text(encoding="utf-8")
        parts = text.split(anchor, 1)
        assert len(parts) > 1, f"{name} hat keinen Abschnitt «{anchor}»"
        body = parts[1][:2500]
        for value in (MCP_PROTOCOL_VERSION, DOCUMENTED_HANDSHAKE_VERSION):
            assert value in body, f"{name} nennt {value} nicht im Abschnitt «{anchor}»"


_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
    "Host": "127.0.0.1:8000",
    "Authorization": f"Bearer {API_KEY}",
}


async def _initialize(requested: str) -> str | None:
    """Ein Legacy-`initialize` durch den echten ASGI-Stack, Antwort-Revision."""
    app = build_http_app("streamable-http")
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://127.0.0.1:8000"
        ) as client:
            response = await client.post(
                "/mcp",
                headers=_HEADERS,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": requested,
                        "capabilities": {},
                        "clientInfo": {"name": "legacy-client", "version": "1"},
                    },
                },
            )
    body = response.text
    for line in body.splitlines():  # SSE-Rahmen abstreifen, falls vorhanden
        if line.startswith("data: "):
            body = line[len("data: ") :]
    return json.loads(body).get("result", {}).get("protocolVersion")


@pytest.mark.parametrize("requested", ["2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25"])
async def test_aeltere_clients_behalten_ihre_revision(requested: str) -> None:
    """Ohne diesen Fall waere der Test unten auch gegen einen Server gruen, der
    jedem dieselbe Antwort gibt."""
    assert await _initialize(requested) == requested


async def test_der_handshake_deckelt_bei_der_dokumentierten_revision() -> None:
    """Der lasttragende Fall, und der Grund fuer die Aufteilung ueberhaupt.

    Ein Client, der ueber den Handshake nach der modernen Revision fragt,
    bekommt die Obergrenze zurueck. Damit ist `DOCUMENTED_HANDSHAKE_VERSION`
    gemessen und nicht aus einem Konstantennamen abgeleitet.
    """
    assert await _initialize(MCP_PROTOCOL_VERSION) == DOCUMENTED_HANDSHAKE_VERSION


def _sdk_requirement() -> str:
    """The `mcp[cli]` requirement, read out of `pyproject.toml`."""
    import tomllib

    data = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    matches = [d for d in data["project"]["dependencies"] if d.startswith("mcp[")]
    assert len(matches) == 1, f"expected exactly one mcp requirement, found {matches}"
    return matches[0]


def test_both_readmes_name_the_sdk_requirement_pyproject_actually_declares() -> None:
    """The row said `mcp[cli]>=1.28.1` for the 90 commits between the migration
    to `mcp` 2.x (which bounded the requirement to `>=2.0.0,<3`) and the commit
    that fixed it. Nothing compared the two, so the drift could only be found by
    reading both files side by side — the one thing nobody does. This is that
    comparison."""
    requirement = _sdk_requirement()
    for name, anchor in README_SECTIONS:
        section = (REPO / name).read_text(encoding="utf-8").split(anchor, 1)[1][:2500]
        assert requirement in section, (
            f"{name} does not name the declared SDK requirement `{requirement}`"
        )


def test_both_readmes_point_at_the_file_that_defines_the_pin() -> None:
    """`MCP_PROTOCOL_VERSION` moved to `_app.py` in the ARCH-011 split while both
    READMEs kept linking `server.py`. A link to the wrong file is worse than
    none: it is checked once and then trusted."""
    module = REPO / "src" / "amtsblatt_mcp" / "_app.py"
    assert "MCP_PROTOCOL_VERSION = " in module.read_text(encoding="utf-8"), (
        "the pin is no longer defined in _app.py — update the READMEs with it"
    )
    for name, anchor in README_SECTIONS:
        section = (REPO / name).read_text(encoding="utf-8").split(anchor, 1)[1][:2500]
        assert "_app.py" in section, f"{name} points elsewhere for the pin"


def test_both_readmes_state_an_update_policy() -> None:
    """A pin with no stated policy for moving it invites a blind bump."""
    for name, anchor in README_SECTIONS:
        section = (REPO / name).read_text(encoding="utf-8").split(anchor, 1)[1][:2500].lower()
        assert "update" in section or "policy" in section, (
            f"{name} states versions but no update policy"
        )
