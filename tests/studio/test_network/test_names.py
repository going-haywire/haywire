"""What this machine is reachable as — the SAN source for a studio certificate.

The two traps these tests pin down were both found by probing the dev machine
while planning this feature:

* ``socket.getaddrinfo(socket.gethostname())`` raises ``[Errno 8]`` on macOS,
  so the obvious enumeration idiom cannot be used.
* Every ``fe80::`` address on that machine carried a ``%zone`` suffix, which is
  invalid inside a certificate SAN.
"""

from unittest.mock import patch

import pytest

from haywire_studio.network.names import LocalNames, local_names, primary_address

pytestmark = pytest.mark.unit


def test_loopback_is_always_present():
    """A certificate that cannot serve localhost breaks the default case."""
    names = local_names()
    assert "localhost" in names.dns
    assert "127.0.0.1" in names.ip
    assert "::1" in names.ip


def test_mdns_local_name_is_offered():
    """The .local name is what survives a move between networks (D6)."""
    with patch("haywire_studio.network.names.socket.gethostname", return_value="MB-41545"):
        names = local_names()
    assert "MB-41545.local" in names.dns
    assert "MB-41545" in names.dns


def test_mdns_name_derived_from_short_hostname():
    """A dotted hostname must not yield 'host.domain.local'."""
    with patch("haywire_studio.network.names.socket.gethostname", return_value="box.example.com"):
        names = local_names()
    assert "box.local" in names.dns
    assert "box.example.com.local" not in names.dns


def test_link_local_addresses_are_excluded():
    """fe80:: addresses are not a useful way to reach a studio, and they are
    the ones that carry %zone suffixes."""
    fake = _addr_map({"en0": ["10.0.0.5", "fe80::c60:ad73:7442:c127%en0"]})
    with patch("haywire_studio.network.names.psutil.net_if_addrs", return_value=fake):
        names = local_names()
    assert "10.0.0.5" in names.ip
    assert not [entry for entry in names.ip if entry.startswith("fe80")]


def test_no_zone_suffix_ever_reaches_the_san_list():
    """A '%' in a SAN is invalid — nothing may carry one through."""
    fake = _addr_map({"en0": ["10.0.0.5", "fe80::1%en0"], "utun0": ["fe80::2%utun0"]})
    with patch("haywire_studio.network.names.psutil.net_if_addrs", return_value=fake):
        names = local_names()
    assert not [entry for entry in names.ip if "%" in entry]


def test_routable_ipv6_is_kept():
    """Excluding link-local must not exclude real IPv6 connectivity."""
    fake = _addr_map({"en0": ["2001:db8::1", "fe80::1%en0"]})
    with patch("haywire_studio.network.names.psutil.net_if_addrs", return_value=fake):
        names = local_names()
    assert "2001:db8::1" in names.ip


def test_unparseable_address_is_skipped_not_raised():
    """psutil reports MAC addresses and other families; none may crash this."""
    fake = _addr_map({"en0": ["not-an-ip", "10.0.0.5"]})
    with patch("haywire_studio.network.names.psutil.net_if_addrs", return_value=fake):
        names = local_names()
    assert "10.0.0.5" in names.ip


def test_addresses_are_deduplicated():
    """llw0 and awdl0 routinely report the same address on macOS."""
    fake = _addr_map({"en0": ["10.0.0.5"], "llw0": ["10.0.0.5"]})
    with patch("haywire_studio.network.names.psutil.net_if_addrs", return_value=fake):
        names = local_names()
    assert names.ip.count("10.0.0.5") == 1


def test_extra_names_are_classified_by_shape():
    """A user passing --also must not have to say which are IPs."""
    names = LocalNames.empty().extend(["10.9.9.9", "studio.example.com"])
    assert "10.9.9.9" in names.ip
    assert "studio.example.com" in names.dns


def test_extend_strips_a_port_suffix():
    """public_hostname may be 'host:443'; a SAN is a host, never a host:port."""
    names = LocalNames.empty().extend(["haywire.example.com:443"])
    assert "haywire.example.com" in names.dns
    assert not [entry for entry in names.dns if ":" in entry]


def test_primary_address_never_raises_without_a_route():
    """Status on an offline laptop must still print."""
    with patch("haywire_studio.network.names.socket.socket", side_effect=OSError("no route")):
        assert primary_address() is None


def _addr_map(spec: dict[str, list[str]]):
    """Build a psutil.net_if_addrs()-shaped mapping from {iface: [address]}."""
    import socket as _socket
    from collections import namedtuple

    snic = namedtuple("snic", ["family", "address", "netmask", "broadcast", "ptp"])
    out = {}
    for iface, addresses in spec.items():
        entries = []
        for address in addresses:
            family = _socket.AF_INET6 if ":" in address else _socket.AF_INET
            entries.append(snic(family, address, None, None, None))
        out[iface] = entries
    return out
