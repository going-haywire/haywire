"""The security document: round-trip, invariants, fail-closed loading."""

from __future__ import annotations

import json
import os
import stat

import pytest

from haywire.core.access import AccessTier

from haywire_studio.security.document import (
    SECURITY_VERSION,
    FarmhandPolicy,
    NetworkPolicy,
    SecurityDocument,
    load_document,
    sanitize,
    save_document,
    validate,
)
from haywire_studio.security.errors import SecurityError
from haywire_studio.security.roster import KIND_AGENT, KIND_USER, Principal, Roster


@pytest.fixture
def path(tmp_path):
    return tmp_path / "security.json"


def _admin() -> Principal:
    return Principal(name="root", kind=KIND_USER, tier=AccessTier.ADMIN, password_hash="x")


def _hardened() -> SecurityDocument:
    """The one document shape that satisfies every invariant."""
    return SecurityDocument(
        auth=Roster(enabled=True, principals=[_admin()]),
        network=NetworkPolicy(
            exposed=True,
            allowed_ranges=("192.168.1.0/24",),
            tls_certfile="/tmp/c.pem",
            tls_keyfile="/tmp/k.pem",
        ),
        farmhand=FarmhandPolicy(),
    )


def test_missing_file_is_a_default_document(path):
    doc = load_document(path)
    assert doc.auth.enabled is False
    assert doc.network.exposed is False
    assert doc.farmhand.enabled is True
    assert doc.farmhand.restrict_to_loopback is True


def test_round_trip_preserves_every_block(path):
    save_document(_hardened(), path)
    doc = load_document(path)
    assert doc.auth.enabled is True
    assert doc.auth.principals[0].name == "root"
    assert doc.network.exposed is True
    assert doc.network.allowed_ranges == ("192.168.1.0/24",)
    assert doc.network.tls_certfile == "/tmp/c.pem"
    assert doc.farmhand.restrict_to_loopback is True


def test_saved_file_is_private(path):
    save_document(SecurityDocument(), path)
    mode = stat.S_IMODE(os.stat(path).st_mode)
    assert mode == 0o600


def test_save_leaves_no_temp_file(path):
    save_document(SecurityDocument(), path)
    assert list(path.parent.iterdir()) == [path]


def test_unparseable_file_raises(path):
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(SecurityError):
        load_document(path)


def test_wrong_version_raises(path):
    path.write_text(json.dumps({"version": 99}), encoding="utf-8")
    with pytest.raises(SecurityError):
        load_document(path)


def test_auth_enabled_without_an_admin_is_rejected(path):
    doc = SecurityDocument(auth=Roster(enabled=True, principals=[]))
    assert validate(doc)
    with pytest.raises(SecurityError):
        save_document(doc, path)


def test_exposed_without_auth_is_rejected(path):
    doc = _hardened()
    doc.auth.enabled = False
    assert validate(doc)
    with pytest.raises(SecurityError):
        save_document(doc, path)


def test_exposed_without_tls_is_rejected(path):
    doc = _hardened()
    doc.network.tls_certfile = ""
    doc.network.tls_keyfile = ""
    assert validate(doc)
    with pytest.raises(SecurityError):
        save_document(doc, path)


def test_exposed_without_ranges_is_rejected(path):
    doc = _hardened()
    doc.network.allowed_ranges = ()
    assert validate(doc)
    with pytest.raises(SecurityError):
        save_document(doc, path)


def test_half_configured_tls_is_rejected(path):
    doc = SecurityDocument(network=NetworkPolicy(tls_certfile="/tmp/c.pem"))
    assert validate(doc)
    with pytest.raises(SecurityError):
        save_document(doc, path)


def test_invalid_cidr_is_rejected(path):
    doc = _hardened()
    doc.network.allowed_ranges = ("not-a-cidr",)
    assert validate(doc)
    with pytest.raises(SecurityError):
        save_document(doc, path)


def test_hardened_document_saves(path):
    save_document(_hardened(), path)
    assert validate(load_document(path)) == []


def test_sanitize_downgrades_a_hand_edited_violation():
    """Fail closed, never refuse to start — a lockout's fix needs the UI it took away."""
    doc = _hardened()
    doc.auth.enabled = False  # hand-edited: exposed with auth off
    clean, reasons = sanitize(doc)
    assert clean.network.exposed is False
    assert reasons
    assert validate(clean) == []


def test_sanitize_leaves_a_valid_document_alone():
    clean, reasons = sanitize(_hardened())
    assert reasons == []
    assert clean.network.exposed is True


def test_agent_principal_round_trips(path):
    doc = SecurityDocument(
        auth=Roster(principals=[Principal(name="bot", kind=KIND_AGENT, tier=AccessTier.EDIT, token="t0ken")])
    )
    save_document(doc, path)
    loaded = load_document(path)
    found = loaded.auth.find_by_token("t0ken")
    assert found is not None
    assert found.name == "bot"
    assert loaded.auth.find_by_token("") is None


def test_version_is_written(path):
    save_document(SecurityDocument(), path)
    assert json.loads(path.read_text())["version"] == SECURITY_VERSION
