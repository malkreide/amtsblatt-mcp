"""Inbound Host/Origin validation on the network transport (SEC-005, inbound).

Under mcp 2.x ``transport_security`` is a per-app kwarg. Left unset the SDK
auto-enables protection only for a loopback bind — a 0.0.0.0 bind, which is how
this server ships, gets nothing. These tests pin the explicit allow-list and
fail if it is dropped again.
"""

from __future__ import annotations

import pytest

from amtsblatt_mcp.server import build_transport_security


def test_loopback_bind_enables_protection(monkeypatch):
    monkeypatch.delenv("MCP_ALLOWED_HOSTS", raising=False)
    sec = build_transport_security("127.0.0.1", 8000)
    assert sec is not None
    assert sec.enable_dns_rebinding_protection is True
    assert "127.0.0.1:8000" in sec.allowed_hosts
    assert "localhost:8000" in sec.allowed_hosts


def test_non_local_bind_without_allowlist_stays_off(monkeypatch):
    """0.0.0.0 with no allow-list: the reachable name is unknowable here, so a
    guess would reject every real request. Falls back to the SDK default."""
    monkeypatch.delenv("MCP_ALLOWED_HOSTS", raising=False)
    assert build_transport_security("0.0.0.0", 8000) is None


def test_non_local_bind_with_allowlist_enables_protection(monkeypatch):
    monkeypatch.setenv("MCP_ALLOWED_HOSTS", "mcp.example.ch,mcp.example.ch:443")
    sec = build_transport_security("0.0.0.0", 8000)
    assert sec is not None
    assert "mcp.example.ch" in sec.allowed_hosts
    # Loopback stays in, otherwise container health checks break.
    assert "127.0.0.1:8000" in sec.allowed_hosts


def test_port_is_honoured(monkeypatch):
    monkeypatch.delenv("MCP_ALLOWED_HOSTS", raising=False)
    sec = build_transport_security("127.0.0.1", 9443)
    assert "127.0.0.1:9443" in sec.allowed_hosts
    assert "127.0.0.1:8000" not in sec.allowed_hosts


def test_configured_origins_pass_and_wildcard_is_not_copied(monkeypatch):
    """Configured origins must also pass the transport check, or the server
    refuses exactly the browser clients CORS permits. "*" is matched literally
    by the SDK, so copying it would look like a wildcard while doing nothing."""
    monkeypatch.delenv("MCP_ALLOWED_HOSTS", raising=False)
    sec = build_transport_security("127.0.0.1", 8000, ["https://claude.ai", "*"])
    assert "https://claude.ai" in sec.allowed_origins
    assert "*" not in sec.allowed_origins


def test_derived_loopback_origins_are_present(monkeypatch):
    """An empty allowed_origins would refuse a same-host browser request: the
    SDK only skips the Origin check when the header is absent entirely."""
    monkeypatch.delenv("MCP_ALLOWED_HOSTS", raising=False)
    sec = build_transport_security("127.0.0.1", 8000)
    assert "http://127.0.0.1:8000" in sec.allowed_origins


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1"])
def test_all_loopback_forms_are_local(host, monkeypatch):
    monkeypatch.delenv("MCP_ALLOWED_HOSTS", raising=False)
    assert build_transport_security(host, 8000) is not None
