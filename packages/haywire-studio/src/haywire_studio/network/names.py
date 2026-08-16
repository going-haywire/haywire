"""What this machine is reachable as.

A certificate is only valid for the names baked into its SAN extension at
signing time, so this module answers one question: *which names and addresses
should a certificate for this studio cover?* It holds no crypto, touches no
files and prints nothing, which keeps it testable without generating a key.

**The mDNS name is the important one.** A LAN address changes when the machine
moves between networks — home to university and back — and a certificate that
lists only IPs stops matching the moment that happens. ``<host>.local``
resolves on any LAN with mDNS, so a certificate carrying it keeps working
across the move with no regeneration and no re-trust.

Two traps, both found by probing a real macOS machine rather than by reading
docs:

* ``socket.getaddrinfo(socket.gethostname())`` — the obvious way to enumerate
  local addresses — raises ``[Errno 8] nodename nor servname provided`` there.
  ``psutil.net_if_addrs()`` is used instead.
* Link-local addresses arrive with a zone suffix (``fe80::1%en0``). A ``%`` is
  invalid inside a SAN, and a link-local address is not a useful way to reach a
  studio anyway, so the whole ``fe80::/10`` range is dropped.
"""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Iterable
from dataclasses import dataclass

import psutil

# Probing this address picks a route; no packet is ever sent (SOCK_DGRAM
# connect is local-only). Any routable address would do.
_ROUTE_PROBE = ("8.8.8.8", 80)


@dataclass(frozen=True)
class LocalNames:
    """DNS names and IP addresses a certificate should cover.

    Kept apart because ``x509`` needs them as different SAN entry types —
    ``DNSName`` versus ``IPAddress`` — and conflating them produces a
    certificate that browsers reject for the address the user actually typed.
    """

    dns: tuple[str, ...]
    ip: tuple[str, ...]

    @classmethod
    def empty(cls) -> LocalNames:
        return cls(dns=(), ip=())

    def extend(self, extras: Iterable[str] | None) -> LocalNames:
        """Return a copy with *extras* merged in, each routed by its shape.

        Callers pass names the user typed (``--also``) or configured
        (``public_hostname``); making them declare which are addresses would be
        a question they cannot reliably answer. A ``host:port`` form is
        accepted and the port dropped — ``public_hostname`` is documented as
        allowing one, and a SAN is a host, never a host:port.
        """
        dns = list(self.dns)
        ip = list(self.ip)
        for raw in extras or ():
            entry = str(raw).strip()
            if not entry:
                continue
            entry = _strip_port(entry)
            parsed = _parse_address(entry)
            if parsed is not None:
                _append_unique(ip, str(parsed))
            else:
                _append_unique(dns, entry)
        return LocalNames(dns=tuple(dns), ip=tuple(ip))

    def covers(self, address: str) -> bool:
        """True when *address* would be accepted by a certificate over these
        names. Compared as parsed addresses so ``::1`` and ``0:0:...:1`` agree."""
        parsed = _parse_address(address)
        if parsed is None:
            return address in self.dns
        return any(_parse_address(entry) == parsed for entry in self.ip)

    def __bool__(self) -> bool:
        return bool(self.dns or self.ip)


def local_names() -> LocalNames:
    """Every name and address this machine can currently be reached at.

    Loopback is unconditional: a certificate that cannot serve ``localhost``
    breaks the default, loopback-only studio, which is the configuration most
    users are in.
    """
    dns: list[str] = ["localhost"]
    ip: list[str] = ["127.0.0.1", "::1"]

    hostname = socket.gethostname().strip()
    if hostname:
        _append_unique(dns, hostname)
        # Derive the mDNS name from the *short* host label, so a dotted
        # hostname yields 'box.local' rather than 'box.example.com.local'.
        short = hostname.split(".")[0]
        if short:
            _append_unique(dns, f"{short}.local")

    fqdn = socket.getfqdn().strip()
    if fqdn and "." in fqdn and fqdn != hostname:
        _append_unique(dns, fqdn)

    for address in _interface_addresses():
        _append_unique(ip, address)

    return LocalNames(dns=tuple(dns), ip=tuple(ip))


def primary_address() -> str | None:
    """The address this machine would use to reach the outside world.

    Answers "you are reachable here as X" for ``ssl status``. Returns ``None``
    rather than raising when there is no route — a status command on an offline
    laptop must still print.
    """
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    except OSError:
        return None
    try:
        probe.connect(_ROUTE_PROBE)
        return str(probe.getsockname()[0])
    except OSError:
        return None
    finally:
        probe.close()


def _interface_addresses() -> list[str]:
    """Non-loopback, non-link-local addresses across every interface."""
    found: list[str] = []
    try:
        interfaces = psutil.net_if_addrs()
    except OSError:
        # Enumeration is best-effort: loopback is already covered, so a
        # failure here degrades the certificate rather than breaking setup.
        return found

    for entries in interfaces.values():
        for entry in entries:
            if entry.family not in (socket.AF_INET, socket.AF_INET6):
                continue
            parsed = _parse_address(entry.address)
            if parsed is None:
                continue
            # Link-local is dropped whole: it is unusable for reaching a studio
            # and it is the source of the invalid %zone suffixes.
            if parsed.is_loopback or parsed.is_link_local:
                continue
            _append_unique(found, str(parsed))
    return found


def _parse_address(value: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    """Parse an address, tolerating a ``%zone`` suffix. ``None`` when *value*
    is not an address at all (a DNS name, a MAC, anything else psutil hands us)."""
    try:
        return ipaddress.ip_address(value.split("%")[0])
    except ValueError:
        return None


def _strip_port(entry: str) -> str:
    """Drop a trailing ``:port``, leaving bare IPv6 literals intact."""
    if entry.startswith("["):  # [::1]:8124
        host, _, _ = entry.partition("]")
        return host.lstrip("[")
    if entry.count(":") == 1:  # host:port — a bare IPv6 has several colons
        host, _, port = entry.partition(":")
        if port.isdigit():
            return host
    return entry


def _append_unique(target: list[str], value: str) -> None:
    """Append preserving order. Interfaces routinely report duplicates — on
    macOS ``llw0`` and ``awdl0`` mirror each other — and a SAN list with
    repeats is merely untidy, but the dedup keeps output readable."""
    if value not in target:
        target.append(value)
