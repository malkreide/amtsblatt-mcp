"""Spec 2026-07-28, gefahren statt behauptet.

`test_protocol_version.py` misst die Handshake-Aera durch den echten
ASGI-Stack und fuer die moderne Aera nur die Konstante. Ob ein
2026-07-28-Client ueberhaupt eine Antwort bekommt — durch Bearer-Gate,
Rate-Limit und CORS hindurch — hat bisher kein Test gezeigt. Das holt diese
Datei nach, auf beiden Wegen, die ein Client nehmen kann:

* **roh**, eine JSON-RPC-Anfrage mit Routing-Headern und `_meta`-Envelope, so
  wie sie auf dem Draht steht. Damit sind Statuscodes und Fehlercodes sichtbar,
  die ein SDK-Client wegabstrahiert;
* **ueber `mcp.Client`**, der mit `mode="auto"` erst `server/discover` probt
  und nur bei einem Legacy-Server auf `initialize` zurueckfaellt. Das ist der
  Weg, den heutige Clients gehen.

Ohne Netz: die aufgerufenen Werkzeuge sind entweder statisch
(`tools/list`) oder werden von der Freigabeliste abgewiesen, bevor eine
Anfrage an amtsblattportal.ch hinausgeht.
"""

from __future__ import annotations

import json
import os
import sys

import httpx
import httpx2
import pytest
from mcp import Client, StdioServerParameters
from mcp.client.streamable_http import streamable_http_client
from mcp.types.version import LATEST_HANDSHAKE_VERSION

from amtsblatt_mcp import __version__
from amtsblatt_mcp._app import LIST_CACHE_TTL_MS, MCP_PROTOCOL_VERSION
from amtsblatt_mcp.server import build_http_app

API_KEY = "test-key-not-a-real-secret"
BASE = "http://127.0.0.1:8000"

META = {
    "io.modelcontextprotocol/protocolVersion": MCP_PROTOCOL_VERSION,
    "io.modelcontextprotocol/clientInfo": {"name": "modern-probe", "version": "1"},
    "io.modelcontextprotocol/clientCapabilities": {},
}
SERVER_INFO = "io.modelcontextprotocol/serverInfo"


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_API_KEY", API_KEY)
    monkeypatch.delenv("MCP_CORS_ORIGINS", raising=False)
    monkeypatch.delenv("MCP_STATELESS", raising=False)


def _headers(method: str, name: str | None = None, **extra: str) -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "Host": "127.0.0.1:8000",
        "Authorization": f"Bearer {API_KEY}",
        "MCP-Protocol-Version": MCP_PROTOCOL_VERSION,
        "Mcp-Method": method,
    }
    if name is not None:
        headers["Mcp-Name"] = name
    headers.update(extra)
    return headers


def _body(response: httpx.Response) -> dict:
    """JSON oder ein einzelner SSE-Rahmen — beides ist spec-konform."""
    text = response.text
    for line in text.splitlines():
        if line.startswith("data: "):
            text = line[len("data: ") :]
    return json.loads(text)


async def _post(
    method: str,
    params: dict | None = None,
    *,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    """Eine einzelne moderne Anfrage durch den vollstaendigen ASGI-Stack."""
    app = build_http_app("streamable-http")
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": {**(params or {}), "_meta": META},
    }
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=BASE) as client:
            return await client.post(
                "/mcp",
                headers=headers if headers is not None else _headers(method),
                json=payload,
            )


# --- roh: was auf dem Draht steht ------------------------------------------


async def test_server_discover_antwortet_ohne_handshake() -> None:
    """Der Einstieg jedes 2026-07-28-Clients. Kein `initialize` davor."""
    response = await _post("server/discover")
    assert response.status_code == 200
    result = _body(response)["result"]
    assert MCP_PROTOCOL_VERSION in result["supportedVersions"]
    assert result["capabilities"]["tools"] is not None
    assert result["instructions"].startswith("Read-only access to amtsblattportal.ch")


async def test_server_discover_traegt_die_cache_hinweise() -> None:
    """SEP-2549 auf dem Draht, nicht nur im Konstruktor-Argument."""
    result = _body(await _post("server/discover"))["result"]
    assert result["ttlMs"] == LIST_CACHE_TTL_MS
    assert result["cacheScope"] == "public"


async def test_jedes_resultat_nennt_die_ausgelieferte_version() -> None:
    """Ohne Handshake reist `serverInfo` in jedem Resultat mit.

    Vor der Umstellung stand dort `"version": ""`: der Server nannte seinen
    Namen und verschwieg den Build. Gegen `__version__` statt gegen ein Literal
    geprueft, damit ein Release-Bump diesen Test nicht anfassen muss.
    """
    # Der Werkzeugaufruf nimmt eine gesperrte Rubrik: er geht nicht ins Netz
    # und traegt trotzdem den vollen Envelope.
    blocked = {"name": "gazette_search_publications", "arguments": {"params": {"rubric": "KK"}}}
    for method, params, name in (
        ("server/discover", None, None),
        ("tools/list", None, None),
        ("tools/call", blocked, blocked["name"]),
    ):
        response = await _post(method, params, headers=_headers(method, name))
        assert response.status_code == 200, (method, response.text)
        info = _body(response)["result"]["_meta"][SERVER_INFO]
        assert info == {"name": "amtsblatt_mcp", "version": __version__}, method


async def test_tools_list_liefert_alle_sechs_werkzeuge() -> None:
    result = _body(await _post("tools/list"))["result"]
    assert len(result["tools"]) == 6
    assert result["ttlMs"] == LIST_CACHE_TTL_MS


async def test_die_freigabeliste_gilt_auch_in_der_modernen_aera() -> None:
    """Die Datenschutz-Grenze haengt am Werkzeug, nicht an der Protokoll-Aera.

    Eine neue Aera ist ein neuer Eintrittsweg; genau dort waere eine Umgehung
    zu suchen.
    """
    name = "gazette_search_publications"
    response = await _post(
        "tools/call",
        {"name": name, "arguments": {"params": {"rubric": "KK"}}},
        headers=_headers("tools/call", name),
    )
    result = _body(response)["result"]
    text = result["content"][0]["text"]
    assert "bewusst nicht erschlossen" in text


async def test_initialize_gibt_es_in_der_modernen_aera_nicht() -> None:
    """2026-07-28 hat keinen Handshake. Wer ihn trotzdem schickt, bekommt
    «Methode unbekannt» — nicht eine stillschweigend geoeffnete Legacy-Session."""
    response = await _post(
        "initialize",
        {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "confused", "version": "1"},
        },
    )
    assert response.status_code == 404
    assert _body(response)["error"]["code"] == -32601


async def test_ein_widerspruechlicher_routing_header_wird_abgewiesen() -> None:
    """Header und Body muessen dasselbe sagen — sonst routet ein Proxy anders,
    als der Server ausfuehrt. `-32020` ist der Code, den die Spec dafuer
    reserviert, und er kommt als HTTP 400, nicht als Werkzeugfehler."""
    response = await _post(
        "tools/call",
        {"name": "gazette_list_rubrics", "arguments": {}},
        headers=_headers("tools/call", "gazette_get_publication"),
    )
    assert response.status_code == 400
    assert _body(response)["error"]["code"] == -32020


async def test_das_bearer_gate_steht_vor_der_aera_weiche() -> None:
    """Die moderne Aera ist ein eigener Codepfad im SDK. Er darf kein
    Seiteneingang am Schluessel vorbei sein."""
    headers = _headers("server/discover")
    del headers["Authorization"]
    response = await _post("server/discover", headers=headers)
    assert response.status_code == 401


async def test_eine_unbekannte_revision_wird_benannt_abgewiesen() -> None:
    """Kein stilles Zurueckfallen auf eine Revision, die niemand verlangt hat."""
    response = await _post(
        "server/discover",
        headers=_headers("server/discover", **{"MCP-Protocol-Version": "2099-01-01"}),
    )
    assert response.status_code == 400
    assert "error" in _body(response)


# --- zustandslos: was der Default aendert ----------------------------------


@pytest.mark.parametrize(("stateless", "status"), [(None, 200), ("0", 400)])
async def test_ohne_versions_header_haengt_die_antwort_am_session_modus(
    monkeypatch: pytest.MonkeyPatch, stateless: str | None, status: int
) -> None:
    """Warum `MCP_STATELESS` nun standardmaessig an ist, gemessen.

    Das SDK waehlt die Aera ueber den `MCP-Protocol-Version`-Header. Fehlt er,
    landet eine moderne Anfrage im Handshake-Pfad; der zustandsbehaftete
    Betrieb weist sie dort mit «Missing session ID» ab, der zustandslose
    beantwortet sie. Beide Zweige gefahren, damit der Test nicht den Tag prueft.
    """
    if stateless is not None:
        monkeypatch.setenv("MCP_STATELESS", stateless)
    headers = _headers("tools/list")
    del headers["MCP-Protocol-Version"]
    response = await _post("tools/list", headers=headers)
    assert response.status_code == status, response.text


# --- ueber den SDK-Client: der Weg heutiger Clients -------------------------


async def _negotiate(mode: str) -> tuple[str, int, str]:
    app = build_http_app("streamable-http")
    async with app.router.lifespan_context(app):
        http = httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=app),
            base_url=BASE,
            headers={"Authorization": f"Bearer {API_KEY}"},
        )
        async with http:
            transport = streamable_http_client(f"{BASE}/mcp", http_client=http)
            async with Client(transport, mode=mode) as client:
                tools = await client.list_tools()
                version = client.server_info.version if client.server_info else ""
                return client.protocol_version, len(tools.tools), version


async def test_ein_auto_client_landet_in_der_modernen_aera() -> None:
    """Der lasttragende Fall: `mode="auto"` probt `server/discover` und bleibt
    nur dann modern, wenn der Server es durch den ganzen Stack beantwortet."""
    assert await _negotiate("auto") == (MCP_PROTOCOL_VERSION, 6, __version__)


async def test_ein_legacy_client_bekommt_weiterhin_den_handshake() -> None:
    """Die Gegenprobe: ohne sie waere der Test oben auch gegen einen Server
    gruen, der jedem die moderne Aera aufzwingt."""
    assert await _negotiate("legacy") == (LATEST_HANDSHAKE_VERSION, 6, __version__)


async def test_stdio_spricht_die_moderne_aera() -> None:
    """stdio ist der Default-Transport — und hat keinen Header, ueber den das
    SDK die Aera waehlen koennte. Deshalb als echter Unterprozess gefahren."""
    env = {k: v for k, v in os.environ.items() if k != "MCP_TRANSPORT"}
    env["MCP_TRANSPORT"] = "stdio"
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "amtsblatt_mcp.server"], env=env
    )
    async with Client(params, mode="auto") as client:
        tools = await client.list_tools()
        assert client.protocol_version == MCP_PROTOCOL_VERSION
        assert len(tools.tools) == 6
        assert client.server_info is not None
        assert client.server_info.version == __version__
