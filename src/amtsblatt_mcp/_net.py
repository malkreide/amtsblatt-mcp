"""DNS resolution with an IP blocklist and connection pinning (SEC-004, SEC-005).

The host allow-list in `server.py` answers "is this the name we meant?". It
cannot answer "is this the *machine* we meant?" — a name resolves to an address,
and nothing about an allow-listed hostname prevents that address from being
`169.254.169.254` or `127.0.0.1`. DNS is controlled by whoever runs the zone,
not by us.

Two controls, and they only work together:

**Blocklist.** The resolved address is checked against loopback, private,
link-local, unique-local and unspecified ranges, in both IPv4 and IPv6. The
cloud metadata endpoint `169.254.169.254` falls under link-local, but it is
named explicitly in the tests because it is the address that turns an SSRF into
a credential leak.

**Pinning.** Validating an address and then connecting *by hostname* is a
time-of-check/time-of-use bug: the second lookup can return a different answer
than the first. That is DNS rebinding, and it defeats a blocklist entirely. So
the connection is made to the address that was checked.

The pinning happens in a custom network backend, not by rewriting the request
URL to the literal IP. Both approaches connect to the checked address, but the
rewrite changes what every layer above the socket sees — the response's own
`request.url`, anything that logs it, and route matching in tests. Substituting
only the address the socket is opened to leaves the hostname intact all the way
down, so `Host` and TLS SNI are derived from the name as usual and certificate
validation runs against it. The check catalogue names a "custom resolver" as an
accepted implementation for exactly this reason.

Applied at the connection layer rather than per call, so it also covers
redirects: every hop opens its own connection and passes through here.
"""

from __future__ import annotations

import ipaddress
import socket
from typing import Any

import httpx
from httpcore import AnyIOBackend

# Ranges an outbound request from this server has no business reaching. Kept as
# networks rather than addresses so a range cannot be half-covered.
BLOCKED_NETWORKS = (
    ipaddress.ip_network("0.0.0.0/8"),  # "this network"
    ipaddress.ip_network("10.0.0.0/8"),  # RFC 1918
    ipaddress.ip_network("100.64.0.0/10"),  # CGNAT
    ipaddress.ip_network("127.0.0.0/8"),  # loopback
    ipaddress.ip_network("169.254.0.0/16"),  # link-local, incl. cloud metadata
    ipaddress.ip_network("172.16.0.0/12"),  # RFC 1918
    ipaddress.ip_network("192.0.0.0/24"),  # IETF protocol assignments
    ipaddress.ip_network("192.168.0.0/16"),  # RFC 1918
    ipaddress.ip_network("198.18.0.0/15"),  # benchmarking
    ipaddress.ip_network("::/128"),  # unspecified
    ipaddress.ip_network("::1/128"),  # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),  # unique-local
    ipaddress.ip_network("fe80::/10"),  # IPv6 link-local
)


class BlockedAddressError(RuntimeError):
    """The hostname resolved to an address outside the permitted range."""


def is_blocked(address: str) -> bool:
    """True when `address` falls in a range this server must not reach."""
    ip = ipaddress.ip_address(address)
    # `is_private` alone is not enough: it misses 0.0.0.0/8 and treats some
    # ranges inconsistently across Python versions. The explicit table is the
    # contract; the property is a belt-and-braces addition.
    return any(ip in net for net in BLOCKED_NETWORKS) or ip.is_loopback or ip.is_link_local


def resolve_checked(host: str, port: int) -> str:
    """Resolve `host` **once** and return an address that passed the blocklist.

    Raises `BlockedAddressError` if the name does not resolve, or if every
    address it resolves to is blocked. A name that resolves to a mix is treated
    as blocked rather than "use the good one": a zone returning one public and
    one private address is not a configuration this server should paper over.
    """
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise BlockedAddressError(f"Cannot resolve {host!r}: {exc}") from exc

    addresses = [info[4][0] for info in infos]
    if not addresses:
        raise BlockedAddressError(f"{host!r} resolved to no addresses.")

    blocked = [a for a in addresses if is_blocked(a)]
    if blocked:
        raise BlockedAddressError(
            f"{host!r} resolves to a non-routable or internal address {blocked[0]!r}; "
            "refusing to connect."
        )
    return addresses[0]


class _PinnedBackend(AnyIOBackend):
    """Network backend that resolves through `resolve_checked` before connecting.

    Pinning is done here rather than by rewriting `request.url` to the literal
    IP. Both connect to the checked address, but rewriting the URL changes what
    every layer above sees — including the response's own `request.url`, any
    logging of it, and route matching in tests. The check catalogue permits a
    "custom resolver" for exactly this reason, and it is the less invasive of
    the two: the hostname stays the hostname all the way down, and only the
    address the socket is opened to is substituted.

    `connect_tcp` receives the hostname httpcore parsed from the URL, so `Host`
    and SNI are derived from the name as usual and certificate validation runs
    against it.
    """

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Any = None,
    ) -> Any:
        try:
            ipaddress.ip_address(host)
        except ValueError:
            address = resolve_checked(host, port)
        else:
            if is_blocked(host):
                raise BlockedAddressError(f"Refusing to connect to {host!r}.")
            address = host

        return await super().connect_tcp(
            address,
            port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )


class PinnedResolverTransport(httpx.AsyncHTTPTransport):
    """Transport whose connections resolve through the checked resolver.

    `httpx.AsyncHTTPTransport` exposes no `network_backend` argument, so the
    pool's backend is replaced after construction. Asserted in tests rather than
    assumed, because a private attribute rename upstream would silently disable
    the control — which is the failure mode this whole module exists to prevent.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._pool._network_backend = _PinnedBackend()
