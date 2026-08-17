"""Startup never refuses over a hand-edited document — it fails closed and says so."""

from __future__ import annotations

import json

from haywire.core.access import AccessTier

from haywire_studio.security.document import (
    SECURITY_VERSION,
    NetworkPolicy,
    SecurityDocument,
    load_document,
    sanitize,
)
from haywire_studio.security.roster import KIND_USER, Principal, Roster


def test_hand_edited_exposure_without_auth_boots_on_loopback(tmp_path):
    """The file claims exposure with auth off; a studio must boot, but sealed."""
    path = tmp_path / "security.json"
    path.write_text(
        json.dumps(
            {
                "version": SECURITY_VERSION,
                "auth": {"enabled": False, "session_days": 30, "principals": []},
                "network": {
                    "exposed": True,
                    "allowed_ranges": ["0.0.0.0/0"],
                    "tls_certfile": "",
                    "tls_keyfile": "",
                },
                "farmhand": {"enabled": True, "restrict_to_loopback": True},
            }
        ),
        encoding="utf-8",
    )
    clean, reasons = sanitize(load_document(path))
    assert clean.network.exposed is False
    assert len(reasons) == 2  # auth off AND no TLS


def test_hand_edited_half_tls_is_cleared_not_fatal(tmp_path):
    doc = SecurityDocument(network=NetworkPolicy(tls_certfile="/tmp/only-cert.pem"))
    clean, reasons = sanitize(doc)
    assert clean.network.tls_certfile == ""
    assert clean.network.tls_keyfile == ""
    assert reasons


def test_enabled_auth_without_an_admin_is_disabled_not_fatal():
    doc = SecurityDocument(auth=Roster(enabled=True, principals=[]))
    clean, reasons = sanitize(doc)
    assert clean.auth.enabled is False
    assert reasons


def test_a_valid_document_passes_through_untouched(tmp_path):
    cert, key = tmp_path / "c.pem", tmp_path / "k.pem"
    cert.write_text("c")
    key.write_text("k")
    doc = SecurityDocument(
        auth=Roster(
            enabled=True,
            principals=[Principal(name="root", kind=KIND_USER, tier=AccessTier.ADMIN, password_hash="x")],
        ),
        network=NetworkPolicy(
            exposed=True,
            allowed_ranges=("192.168.1.0/24",),
            tls_certfile=str(cert),
            tls_keyfile=str(key),
        ),
    )
    clean, reasons = sanitize(doc)
    assert reasons == []
    assert clean.network.exposed is True
