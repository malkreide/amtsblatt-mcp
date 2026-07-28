"""SEC-004 / SEC-005: resolved-address blocklist and DNS pinning.

The host allow-list and HTTPS check answer "is this the name we meant?". These tests cover the
question it cannot answer — "is this the *machine* we meant?" — because DNS is
controlled by whoever runs the zone.

`test_rebinding_second_lookup_is_never_used` is the one that matters most: it is
the only test here that fails if the address is validated and the connection is
then made by hostname anyway, which is the shape of the bug DNS pinning exists
to prevent.
"""

from __future__ import annotations

import socket

import pytest

from amtsblatt_mcp import _net
from amtsblatt_mcp._net import (
    BlockedAddressError,
    PinnedResolverTransport,
    _PinnedBackend,
    is_blocked,
    resolve_checked,
)


def _addrinfo(*addresses: str):
    """Shape `socket.getaddrinfo` returns: (family, type, proto, canon, sockaddr)."""
    return [
        (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (a, 443)) for a in addresses
    ]


@pytest.mark.parametrize(
    "address",
    [
        "169.254.169.254",  # cloud metadata — the one that turns SSRF into a leak
        "127.0.0.1",
        "127.1.2.3",
        "0.0.0.0",
        "10.0.0.1",
        "172.16.0.1",
        "192.168.1.1",
        "100.64.0.1",  # CGNAT
        "198.18.0.1",  # benchmarking
        "::1",  # IPv6 loopback
        "fe80::1",  # IPv6 link-local
        "fc00::1",  # IPv6 unique-local
    ],
)
def test_internal_addresses_are_blocked(address: str) -> None:
    assert is_blocked(address)


@pytest.mark.parametrize("address", ["1.1.1.1", "93.184.216.34", "2606:2800:220:1::1"])
def test_public_addresses_are_allowed(address: str) -> None:
    assert not is_blocked(address)


def test_resolution_to_an_internal_address_is_refused(monkeypatch) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: _addrinfo("169.254.169.254"))
    with pytest.raises(BlockedAddressError, match="non-routable or internal"):
        resolve_checked("metadata.example", 443)


def test_a_mixed_answer_is_refused_rather_than_filtered(monkeypatch) -> None:
    """A zone returning one public and one private address is not a
    configuration to paper over by picking the good one."""
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: _addrinfo("1.1.1.1", "127.0.0.1"))
    with pytest.raises(BlockedAddressError):
        resolve_checked("mixed.example", 443)


def test_public_resolution_returns_the_address(monkeypatch) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: _addrinfo("93.184.216.34"))
    assert resolve_checked("example.test", 443) == "93.184.216.34"


def test_unresolvable_name_is_refused(monkeypatch) -> None:
    def boom(*a, **k):
        raise socket.gaierror("nope")

    monkeypatch.setattr(socket, "getaddrinfo", boom)
    with pytest.raises(BlockedAddressError, match="Cannot resolve"):
        resolve_checked("nx.example", 443)


def test_resolution_happens_exactly_once_per_connect(monkeypatch) -> None:
    """SEC-005 asks for one DNS call per request; two is where rebinding lives."""
    calls: list[str] = []

    def counting(host, port, **kwargs):
        calls.append(host)
        return _addrinfo("93.184.216.34")

    monkeypatch.setattr(socket, "getaddrinfo", counting)
    connected: list[str] = []

    async def fake_connect(self, host, port, **kwargs):
        connected.append(host)
        return object()

    monkeypatch.setattr(_net.AnyIOBackend, "connect_tcp", fake_connect)

    import asyncio

    asyncio.run(_PinnedBackend().connect_tcp("example.test", 443))
    assert calls == ["example.test"], f"expected one lookup, got {calls}"
    assert connected == ["93.184.216.34"], "connected by name instead of by checked address"


def test_rebinding_second_lookup_is_never_used(monkeypatch) -> None:
    """The core of SEC-005.

    A zone that answers public once and internal immediately after is the
    classic rebind. Because the address handed to `connect_tcp` is the one that
    was checked, the second answer is never consulted — there is no second
    lookup to consult.
    """
    answers = iter([_addrinfo("93.184.216.34"), _addrinfo("169.254.169.254")])
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: next(answers))
    connected: list[str] = []

    async def fake_connect(self, host, port, **kwargs):
        connected.append(host)
        return object()

    monkeypatch.setattr(_net.AnyIOBackend, "connect_tcp", fake_connect)

    import asyncio

    asyncio.run(_PinnedBackend().connect_tcp("rebind.example", 443))
    assert connected == ["93.184.216.34"]
    assert "169.254.169.254" not in connected


def test_literal_internal_ip_is_refused_without_a_lookup(monkeypatch) -> None:
    def boom(*a, **k):
        raise AssertionError("a literal IP must not be resolved")

    monkeypatch.setattr(socket, "getaddrinfo", boom)

    import asyncio

    with pytest.raises(BlockedAddressError):
        asyncio.run(_PinnedBackend().connect_tcp("169.254.169.254", 80))


def test_transport_installs_the_pinned_backend() -> None:
    """The backend is attached to a private attribute of the pool.

    Asserted rather than assumed: an upstream rename would silently disable the
    control, which is the exact failure mode this module exists to prevent.
    """
    transport = PinnedResolverTransport()
    assert isinstance(transport._pool._network_backend, _PinnedBackend)


def test_the_shared_client_uses_the_pinned_transport() -> None:
    """A control installed on a transport nobody uses is not a control."""
    from amtsblatt_mcp.server import _make_client

    client = _make_client()
    assert isinstance(client._transport, PinnedResolverTransport)


def test_the_egress_hook_is_still_installed() -> None:
    """The two controls are complementary, not alternatives.

    The transport answers "is this the machine we meant?"; the event hook
    answers "is this the name we meant?" and enforces HTTPS. Replacing the
    transport must not have displaced the hook.
    """
    from amtsblatt_mcp.server import _enforce_egress_allowlist, _make_client

    client = _make_client()
    assert _enforce_egress_allowlist in client.event_hooks["request"]
