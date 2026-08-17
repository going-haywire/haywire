"""``Posture`` must agree with the middleware it mirrors.

``security.py`` re-implements the allowlist rule rather than calling
``IPAllowlistMiddleware``, because the CLI runs with the studio stopped and
there is no middleware instance to ask. That duplication is the risk: if
``_is_allowed`` ever grows a rule the report knows nothing about, the report
goes quietly stale and starts describing a studio that does not exist.

These tests drive **both** implementations over the same cases and assert they
reach the same verdict, so a divergence fails here instead of in a user's
terminal. They are the reason the ``allowlist_open`` docstring is allowed to
claim it mirrors the middleware.
"""

import asyncio
import ipaddress

import pytest

from haywire_studio.network.ip_filter import IPAllowlistMiddleware
from haywire_studio.network.names import LocalNames
from haywire_studio.network.tls_operations import TlsState, TlsStatus
from haywire_studio.security.document import NetworkPolicy, SecurityDocument
from haywire_studio.security.posture import Posture, assess_document

pytestmark = pytest.mark.unit


def _posture(ranges: str, *, exposed: bool = True, reachable_at: str | None = "10.0.0.5") -> Posture:
    """A Posture carrying only what the allowlist properties read."""
    tls = TlsStatus(
        state=TlsState.OFF_EXPOSED,
        certfile="",
        keyfile="",
        covered=LocalNames.empty(),
        reachable_at=reachable_at,
        exposed=exposed,
        expires=None,
        fingerprint=None,
        detail="",
    )
    doc = SecurityDocument(
        network=NetworkPolicy(
            exposed=exposed,
            allowed_ranges=tuple(e.strip() for e in ranges.split(",") if e.strip()),
        )
    )
    return assess_document(doc, tls)


def _middleware_allows(ranges: str, peer: str) -> bool:
    """What the real middleware does with *peer*, end to end.

    Drives ``__call__`` rather than ``_is_allowed`` so the loopback bypass and
    the 403 path are both exercised — those are part of the rule the report
    claims to mirror, and neither lives in ``_is_allowed``.
    """
    outcome: list[str] = []

    async def app(scope, receive, send):
        outcome.append("allowed")

    async def send(message):
        if message["type"] == "http.response.start":
            outcome.append(f"rejected:{message['status']}")

    parsed = [entry.strip() for entry in ranges.split(",") if entry.strip()]
    middleware = IPAllowlistMiddleware(app, allowed_ranges=parsed, trusted_proxies=[])
    scope = {"type": "http", "client": (peer, 5000), "headers": []}
    asyncio.run(middleware(scope, None, send))
    return outcome[0] == "allowed"


# ---------------------------------------------------------------------------
# The empty list — the case the report previously got backwards
# ---------------------------------------------------------------------------


def test_empty_allowlist_rejects_remote_peers_in_the_middleware():
    """The ground truth the report's wording rests on."""
    assert _middleware_allows("", "10.244.138.229") is False
    assert _middleware_allows("", "192.168.1.10") is False


def test_empty_allowlist_still_admits_loopback():
    assert _middleware_allows("", "127.0.0.1") is True


def test_posture_calls_an_empty_allowlist_closed():
    posture = _posture("")
    assert posture.allowlist_open is False
    assert posture.reachable_by_others is False


# ---------------------------------------------------------------------------
# Agreement across a spread of lists and peers
# ---------------------------------------------------------------------------


_CASES = [
    ("", "10.244.138.229"),
    ("", "127.0.0.1"),
    ("192.168.0.0/24", "192.168.0.7"),
    ("192.168.0.0/24", "10.244.138.229"),
    ("192.168.0.0/24, 10.21.136.0/21", "10.21.136.4"),
    ("192.168.0.0/24, 10.21.136.0/21", "10.244.138.229"),
    ("10.0.0.0/8", "10.244.138.229"),
    ("0.0.0.0/0", "203.0.113.9"),
]


@pytest.mark.parametrize(("ranges", "peer"), _CASES)
def test_report_and_middleware_agree_on_who_can_connect(ranges, peer):
    """``reachable_by_others`` is a statement about *somebody* getting through.

    Checked per-peer: whenever the middleware admits a non-loopback address,
    the report must not be claiming nobody can reach the studio.
    """
    posture = _posture(ranges)
    allowed = _middleware_allows(ranges, peer)
    is_loopback = ipaddress.ip_address(peer).is_loopback

    if allowed and not is_loopback:
        assert posture.reachable_by_others is True, (
            f"middleware admits {peer} under {ranges!r}, but the report says nobody can connect"
        )
    if not posture.allowlist_open:
        # A closed allowlist must admit nothing but loopback.
        assert allowed is is_loopback


@pytest.mark.parametrize(("ranges", "peer"), _CASES)
def test_covers_own_address_matches_the_middleware(ranges, peer):
    """``covers_own_address()`` must match the middleware for that address."""
    posture = _posture(ranges, reachable_at=peer)
    covered = posture.covers_own_address()
    if covered is None:
        assert not posture.ranges
        return
    if not ipaddress.ip_address(peer).is_loopback:
        assert covered is _middleware_allows(ranges, peer)


@pytest.mark.parametrize(
    "ranges",
    ["", "192.168.0.0/24", "192.168.0.0/24, 10.21.136.0/21", "10.0.0.0/8"],
)
def test_loopback_is_admitted_under_every_allowlist(ranges):
    """The fact the report kept getting wrong.

    Loopback is checked before any membership test, so the operator can ALWAYS
    reach the studio at 127.0.0.1 — however narrow the allowlist, and even when
    this machine's own LAN address is excluded. No output may claim the user is
    locked out of their own studio.
    """
    assert _middleware_allows(ranges, "127.0.0.1") is True


def test_own_address_excluded_does_not_mean_locked_out():
    """`covers_own_address() is False` and "operator can connect" are both true
    at once — they are statements about different addresses."""
    posture = _posture("192.168.0.0/24", reachable_at="10.244.138.229")
    assert posture.covers_own_address() is False
    assert _middleware_allows("192.168.0.0/24", "127.0.0.1") is True


# ---------------------------------------------------------------------------
# Exposure gates the whole thing
# ---------------------------------------------------------------------------


def test_loopback_bind_is_never_reachable_regardless_of_ranges():
    """A populated allowlist means nothing when the socket is on 127.0.0.1."""
    posture = _posture("192.168.0.0/24", exposed=False)
    assert posture.reachable_by_others is False
    assert posture.fenced is False


def test_fenced_means_bound_wide_but_closed():
    assert _posture("", exposed=True).fenced is True
    assert _posture("192.168.0.0/24", exposed=True).fenced is False
