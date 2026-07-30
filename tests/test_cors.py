"""SDK-004: CORS must expose and accept `Mcp-Session-Id` — in front of auth.

This server is cloud-deployed behind a bearer key, which makes the middleware
*order* load-bearing: a browser never sends `Authorization` on a preflight
`OPTIONS`. If auth ran ahead of CORS every preflight would 401 and browser
clients would be locked out entirely, with a symptom that points at the wrong
layer. `test_preflight_succeeds_without_the_bearer_key` is the test for that,
and it is the one worth keeping if any are ever dropped.

The requests are real ones against the assembled app rather than an inspection
of the middleware stack — asserting a `CORSMiddleware` object is present would
pass with an empty `expose_headers`, which is precisely the defect.

**Every test here runs against both HTTP transports.** Since 0.18.0 the server
offers streamable-http alongside the deprecated SSE, and a control that holds on
one transport but not the other is worse than a missing one: it looks enforced.
Parametrising costs nothing and makes the guarantee transport-independent, which
is what the bearer gate and the CORS layer are actually claimed to be.
"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from amtsblatt_mcp import _cors
from amtsblatt_mcp.server import build_http_app

ORIGIN = "https://client.example"
API_KEY = "test-key-not-a-real-secret"

# The endpoint each transport serves, and a second path that must also sit
# behind auth. Streamable-http has only one; SSE splits stream and messages.
ENDPOINTS = {
    "streamable-http": ("/mcp", "/mcp"),
    "sse": ("/sse", "/messages/"),
}


@pytest.fixture(params=["streamable-http", "sse"])
def kind(request) -> str:
    return request.param


def _client(monkeypatch: pytest.MonkeyPatch, origins: str | None, kind: str) -> TestClient:
    monkeypatch.setenv("MCP_API_KEY", API_KEY)
    if origins is None:
        monkeypatch.delenv("MCP_CORS_ORIGINS", raising=False)
    else:
        monkeypatch.setenv("MCP_CORS_ORIGINS", origins)
    return TestClient(build_http_app(kind))


def _preflight(client: TestClient, path: str, origin: str = ORIGIN, method: str = "GET"):
    return client.options(
        path,
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": "mcp-session-id",
        },
    )


def test_preflight_succeeds_without_the_bearer_key(
    monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    """Ordering guard: CORS must answer the preflight before auth rejects it.

    No Authorization header is sent, exactly as a browser would behave. A 401
    here means the middleware order regressed and browser clients are broken.
    """
    resp = _preflight(_client(monkeypatch, ORIGIN, kind), ENDPOINTS[kind][0])
    assert resp.status_code == 200, "preflight must not require the bearer key"
    assert resp.headers["access-control-allow-origin"] == ORIGIN


def test_preflight_allows_the_session_header(monkeypatch: pytest.MonkeyPatch, kind: str) -> None:
    resp = _preflight(_client(monkeypatch, ORIGIN, kind), ENDPOINTS[kind][0])
    assert "mcp-session-id" in resp.headers["access-control-allow-headers"].lower()


def test_preflight_allows_the_authorization_header(
    monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    """The real request does carry the bearer key, so it must be allow-listed."""
    resp = _preflight(_client(monkeypatch, ORIGIN, kind), ENDPOINTS[kind][0])
    assert "authorization" in resp.headers["access-control-allow-headers"].lower()


def test_preflight_allows_delete_for_session_termination(
    monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    resp = _preflight(_client(monkeypatch, ORIGIN, kind), ENDPOINTS[kind][0], method="DELETE")
    assert resp.status_code == 200
    assert "DELETE" in resp.headers["access-control-allow-methods"]


def test_actual_response_exposes_the_session_header(
    monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    """`Access-Control-Expose-Headers` only ever appears on a real response.

    Auth rejects this unauthenticated GET, which is fine and in fact useful: it
    proves the CORS layer still annotates responses produced by inner
    middleware, not just ones from the app itself.
    """
    client = _client(monkeypatch, ORIGIN, kind)
    resp = client.get(ENDPOINTS[kind][0], headers={"Origin": ORIGIN})
    assert resp.status_code == 401
    assert "mcp-session-id" in resp.headers["access-control-expose-headers"].lower()
    assert resp.headers["access-control-allow-origin"] == ORIGIN


def test_unconfigured_origin_is_refused(monkeypatch: pytest.MonkeyPatch, kind: str) -> None:
    resp = _preflight(
        _client(monkeypatch, ORIGIN, kind), ENDPOINTS[kind][0], origin="https://evil.example"
    )
    assert "access-control-allow-origin" not in resp.headers


def test_default_is_fail_closed(monkeypatch: pytest.MonkeyPatch, kind: str) -> None:
    """MCP_CORS_ORIGINS unset must not mean 'any origin'."""
    resp = _preflight(_client(monkeypatch, None, kind), ENDPOINTS[kind][0])
    assert "access-control-allow-origin" not in resp.headers


def test_wildcard_disables_credentials(monkeypatch: pytest.MonkeyPatch, kind: str) -> None:
    resp = _preflight(_client(monkeypatch, "*", kind), ENDPOINTS[kind][0])
    assert resp.headers["access-control-allow-origin"] == "*"
    assert "access-control-allow-credentials" not in resp.headers


def test_explicit_origin_keeps_credentials(monkeypatch: pytest.MonkeyPatch, kind: str) -> None:
    resp = _preflight(_client(monkeypatch, ORIGIN, kind), ENDPOINTS[kind][0])
    assert resp.headers.get("access-control-allow-credentials") == "true"


def test_second_origin_in_the_list_also_works(monkeypatch: pytest.MonkeyPatch, kind: str) -> None:
    """A list honouring only its first entry would pass every test above."""
    resp = _preflight(_client(monkeypatch, f"https://a.example,{ORIGIN}", kind), ENDPOINTS[kind][0])
    assert resp.headers["access-control-allow-origin"] == ORIGIN


def test_origins_are_parsed_as_a_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_CORS_ORIGINS", " https://a.example , https://b.example ,, ")
    assert _cors.configured_origins() == ["https://a.example", "https://b.example"]


def test_auth_still_rejects_a_real_request_without_the_key(
    monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    """CORS must not have become a hole in the bearer gate.

    Putting CORS in front of auth is only safe because it short-circuits
    preflights and nothing else; a non-OPTIONS request must still hit auth.
    """
    client = _client(monkeypatch, ORIGIN, kind)
    stream, messages = ENDPOINTS[kind]
    assert client.get(stream, headers={"Origin": ORIGIN}).status_code == 401
    assert client.post(messages, headers={"Origin": ORIGIN}).status_code == 401


def test_the_api_key_is_required_on_every_http_transport(
    monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    """No transport may quietly ship an unauthenticated HTTP endpoint.

    The check that matters when a *new* transport is added: the loud failure has
    to be a property of building any HTTP app, not something the SSE branch
    happened to do.
    """
    monkeypatch.delenv("MCP_API_KEY", raising=False)
    with pytest.raises(SystemExit) as exc:
        build_http_app(kind)
    assert "MCP_API_KEY" in str(exc.value)
