"""SDK-004: CORS must expose and accept `Mcp-Session-Id` — in front of auth.

This server is cloud-deployed over SSE behind a bearer key, which makes the
middleware *order* load-bearing: a browser never sends `Authorization` on a
preflight `OPTIONS`. If auth ran ahead of CORS every preflight would 401 and
browser clients would be locked out entirely, with a symptom that points at the
wrong layer. `test_preflight_succeeds_without_the_bearer_key` is the test for
that, and it is the one worth keeping if any are ever dropped.

The requests are real ones against the assembled app rather than an inspection
of the middleware stack — asserting a `CORSMiddleware` object is present would
pass with an empty `expose_headers`, which is precisely the defect.
"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from amtsblatt_mcp import _cors
from amtsblatt_mcp.server import _build_sse_app

ORIGIN = "https://client.example"
API_KEY = "test-key-not-a-real-secret"


def _client(monkeypatch: pytest.MonkeyPatch, origins: str | None) -> TestClient:
    monkeypatch.setenv("MCP_API_KEY", API_KEY)
    if origins is None:
        monkeypatch.delenv("MCP_CORS_ORIGINS", raising=False)
    else:
        monkeypatch.setenv("MCP_CORS_ORIGINS", origins)
    return TestClient(_build_sse_app())


def _preflight(client: TestClient, origin: str = ORIGIN, method: str = "GET"):
    return client.options(
        "/sse",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": "mcp-session-id",
        },
    )


def test_preflight_succeeds_without_the_bearer_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ordering guard: CORS must answer the preflight before auth rejects it.

    No Authorization header is sent, exactly as a browser would behave. A 401
    here means the middleware order regressed and browser clients are broken.
    """
    resp = _preflight(_client(monkeypatch, ORIGIN))
    assert resp.status_code == 200, "preflight must not require the bearer key"
    assert resp.headers["access-control-allow-origin"] == ORIGIN


def test_preflight_allows_the_session_header(monkeypatch: pytest.MonkeyPatch) -> None:
    resp = _preflight(_client(monkeypatch, ORIGIN))
    assert "mcp-session-id" in resp.headers["access-control-allow-headers"].lower()


def test_preflight_allows_the_authorization_header(monkeypatch: pytest.MonkeyPatch) -> None:
    """The real request does carry the bearer key, so it must be allow-listed."""
    resp = _preflight(_client(monkeypatch, ORIGIN))
    assert "authorization" in resp.headers["access-control-allow-headers"].lower()


def test_preflight_allows_delete_for_session_termination(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resp = _preflight(_client(monkeypatch, ORIGIN), method="DELETE")
    assert resp.status_code == 200
    assert "DELETE" in resp.headers["access-control-allow-methods"]


def test_actual_response_exposes_the_session_header(monkeypatch: pytest.MonkeyPatch) -> None:
    """`Access-Control-Expose-Headers` only ever appears on a real response.

    Auth rejects this unauthenticated GET, which is fine and in fact useful: it
    proves the CORS layer still annotates responses produced by inner
    middleware, not just ones from the app itself.
    """
    client = _client(monkeypatch, ORIGIN)
    resp = client.get("/sse", headers={"Origin": ORIGIN})
    assert resp.status_code == 401
    assert "mcp-session-id" in resp.headers["access-control-expose-headers"].lower()
    assert resp.headers["access-control-allow-origin"] == ORIGIN


def test_unconfigured_origin_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    resp = _preflight(_client(monkeypatch, ORIGIN), origin="https://evil.example")
    assert "access-control-allow-origin" not in resp.headers


def test_default_is_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """MCP_CORS_ORIGINS unset must not mean 'any origin'."""
    resp = _preflight(_client(monkeypatch, None))
    assert "access-control-allow-origin" not in resp.headers


def test_wildcard_disables_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    resp = _preflight(_client(monkeypatch, "*"))
    assert resp.headers["access-control-allow-origin"] == "*"
    assert "access-control-allow-credentials" not in resp.headers


def test_explicit_origin_keeps_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    resp = _preflight(_client(monkeypatch, ORIGIN))
    assert resp.headers.get("access-control-allow-credentials") == "true"


def test_second_origin_in_the_list_also_works(monkeypatch: pytest.MonkeyPatch) -> None:
    """A list honouring only its first entry would pass every test above."""
    resp = _preflight(_client(monkeypatch, f"https://a.example,{ORIGIN}"))
    assert resp.headers["access-control-allow-origin"] == ORIGIN


def test_origins_are_parsed_as_a_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_CORS_ORIGINS", " https://a.example , https://b.example ,, ")
    assert _cors.configured_origins() == ["https://a.example", "https://b.example"]


def test_auth_still_rejects_a_real_request_without_the_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CORS must not have become a hole in the bearer gate.

    Putting CORS in front of auth is only safe because it short-circuits
    preflights and nothing else; a non-OPTIONS request must still hit auth.
    """
    client = _client(monkeypatch, ORIGIN)
    assert client.get("/sse", headers={"Origin": ORIGIN}).status_code == 401
    assert client.post("/messages/", headers={"Origin": ORIGIN}).status_code == 401
