"""The joined report: which findings fire, and which stay silent."""

from __future__ import annotations

import pytest

from haywire.core.access import AccessTier

from haywire_studio.network.tls_operations import TlsState, TlsStatus
from haywire_studio.network.names import LocalNames
from haywire_studio.security.document import FarmhandPolicy, NetworkPolicy, SecurityDocument
from haywire_studio.security.posture import Severity, assess_document
from haywire_studio.security.roster import KIND_USER, Principal, Roster


def _tls(state: TlsState, *, reachable: str | None = "192.168.1.5") -> TlsStatus:
    return TlsStatus(
        state=state,
        certfile="/tmp/c.pem" if state is TlsState.OK else "",
        keyfile="/tmp/k.pem" if state is TlsState.OK else "",
        covered=LocalNames.empty(),
        reachable_at=reachable,
        exposed=False,
        expires=None,
        fingerprint=None,
        detail="",
    )


def _admin() -> Principal:
    return Principal(name="root", kind=KIND_USER, tier=AccessTier.ADMIN, password_hash="x")


def _hardened() -> SecurityDocument:
    return SecurityDocument(
        auth=Roster(enabled=True, principals=[_admin()]),
        network=NetworkPolicy(
            exposed=True,
            allowed_ranges=("192.168.1.0/24",),
            trusted_proxies=("10.1.0.0/16",),
            tls_certfile="/tmp/c.pem",
            tls_keyfile="/tmp/k.pem",
        ),
    )


def _headlines(posture):
    return " ".join(f.headline for f in posture.findings)


def test_loopback_default_is_clean():
    posture = assess_document(SecurityDocument(), _tls(TlsState.OFF_LOOPBACK))
    assert posture.findings == ()
    assert posture.reachable_by_others is False


def test_hardened_and_exposed_raises_nothing_above_a_note():
    """A hardened studio still gets the "/mcp is reachable" NOTE — that is a fact
    worth knowing, not a gap. Nothing louder may fire."""
    posture = assess_document(_hardened(), _tls(TlsState.OK))
    assert posture.worst in (None, Severity.NOTE)
    assert posture.reachable_by_others is True


def test_hand_edited_violation_is_critical():
    doc = _hardened()
    doc.auth.enabled = False  # only reachable by hand-editing
    posture = assess_document(doc, _tls(TlsState.OK))
    assert posture.worst is Severity.CRITICAL
    assert "not in force" in _headlines(posture)


def test_broken_tls_is_critical_even_on_loopback():
    posture = assess_document(SecurityDocument(), _tls(TlsState.KEY_MISMATCH))
    assert posture.worst is Severity.CRITICAL


def test_no_admin_is_reported_without_exposure():
    doc = SecurityDocument(auth=Roster(enabled=True, principals=[]))
    posture = assess_document(doc, _tls(TlsState.OFF_LOOPBACK))
    assert "no admin" in _headlines(posture)


def test_broad_allowlist_warns_when_reachable():
    doc = _hardened()
    doc.network.allowed_ranges = ("10.0.0.0/8",)
    posture = assess_document(doc, _tls(TlsState.OK))
    assert "very broad" in _headlines(posture)


def test_broad_allowlist_is_silent_when_sealed():
    doc = _hardened()
    doc.network.exposed = False
    doc.network.allowed_ranges = ("10.0.0.0/8",)
    posture = assess_document(doc, _tls(TlsState.OK))
    assert "very broad" not in _headlines(posture)


def test_farmhand_remote_without_auth_is_critical():
    doc = SecurityDocument(farmhand=FarmhandPolicy(restrict_to_loopback=False))
    posture = assess_document(doc, _tls(TlsState.OFF_LOOPBACK))
    assert posture.worst is Severity.CRITICAL
    assert "DNS-rebinding" in _headlines(posture)


def test_farmhand_remote_with_auth_is_a_note():
    doc = _hardened()
    doc.farmhand.restrict_to_loopback = False
    posture = assess_document(doc, _tls(TlsState.OK))
    assert posture.worst is Severity.NOTE
    assert "DNS-rebinding" in _headlines(posture)


def test_farmhand_disabled_is_silent():
    doc = SecurityDocument(farmhand=FarmhandPolicy(enabled=False))
    posture = assess_document(doc, _tls(TlsState.OFF_LOOPBACK))
    assert posture.findings == ()
    assert posture.farmhand_enabled is False


def test_no_trusted_proxies_is_a_note_when_reachable():
    doc = _hardened()
    doc.network.trusted_proxies = ()
    posture = assess_document(doc, _tls(TlsState.OK))
    assert any(f.severity is Severity.NOTE for f in posture.findings)


def test_covers_own_address_is_true_for_a_matching_subnet():
    posture = assess_document(_hardened(), _tls(TlsState.OK, reachable="192.168.1.5"))
    assert posture.covers_own_address() is True


def test_covers_own_address_is_false_for_a_foreign_subnet():
    posture = assess_document(_hardened(), _tls(TlsState.OK, reachable="10.9.9.9"))
    assert posture.covers_own_address() is False


@pytest.mark.parametrize(
    ("exposed", "ranges", "expected"),
    [
        (False, (), False),
        (False, ("192.168.1.0/24",), False),
        (True, (), False),
        (True, ("192.168.1.0/24",), True),
    ],
)
def test_reachable_by_others_truth_table(exposed, ranges, expected):
    doc = _hardened()
    doc.network.exposed = exposed
    doc.network.allowed_ranges = ranges
    posture = assess_document(doc, _tls(TlsState.OK))
    assert posture.reachable_by_others is expected
