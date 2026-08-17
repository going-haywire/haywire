"""The rules for changing the network and Farmhand blocks."""

from __future__ import annotations

import pytest

from haywire.core.access import AccessTier

from haywire_studio.security.document import (
    NetworkPolicy,
    SecurityDocument,
    load_document,
    save_document,
)
from haywire_studio.security.errors import SecurityError
from haywire_studio.security.operations import (
    expose,
    seal,
    set_farmhand_enabled,
    set_farmhand_loopback,
    write_tls_paths,
)
from haywire_studio.security.roster import KIND_USER, Principal, Roster


@pytest.fixture
def path(tmp_path):
    return tmp_path / "security.json"


def _ready(path, tmp_path):
    """A document with auth on and TLS configured — everything expose() needs."""
    cert, key = tmp_path / "c.pem", tmp_path / "k.pem"
    cert.write_text("cert")
    key.write_text("key")
    doc = SecurityDocument(
        auth=Roster(
            enabled=True,
            principals=[Principal(name="root", kind=KIND_USER, tier=AccessTier.ADMIN, password_hash="x")],
        ),
        network=NetworkPolicy(tls_certfile=str(cert), tls_keyfile=str(key)),
    )
    save_document(doc, path)
    return doc


def test_expose_refuses_without_auth(path, tmp_path):
    save_document(SecurityDocument(), path)
    with pytest.raises(SecurityError, match="authentication off"):
        expose(["192.168.1.0/24"], path=path)


def test_expose_refuses_without_tls(path, tmp_path):
    save_document(
        SecurityDocument(
            auth=Roster(
                enabled=True,
                principals=[
                    Principal(name="root", kind=KIND_USER, tier=AccessTier.ADMIN, password_hash="x")
                ],
            )
        ),
        path,
    )
    with pytest.raises(SecurityError, match="without TLS"):
        expose(["192.168.1.0/24"], path=path)


def test_expose_refuses_empty_ranges(path, tmp_path):
    _ready(path, tmp_path)
    with pytest.raises(SecurityError, match="empty allowlist"):
        expose([], path=path)


def test_expose_refuses_a_bad_cidr(path, tmp_path):
    _ready(path, tmp_path)
    with pytest.raises(SecurityError, match="not a CIDR"):
        expose(["192.168.1.0/24", "nonsense"], path=path)


def test_expose_writes_the_ranges(path, tmp_path):
    _ready(path, tmp_path)
    expose(["192.168.1.0/24", " 10.0.0.0/8 "], path=path)
    net = load_document(path).network
    assert net.exposed is True
    assert net.allowed_ranges == ("192.168.1.0/24", "10.0.0.0/8")


def test_expose_records_hostname_and_proxies(path, tmp_path):
    _ready(path, tmp_path)
    expose(
        ["192.168.1.0/24"],
        public_hostname="studio.example.com",
        trusted_proxies=["10.1.0.0/16"],
        path=path,
    )
    net = load_document(path).network
    assert net.public_hostname == "studio.example.com"
    assert net.trusted_proxies == ("10.1.0.0/16",)


def test_expose_leaves_hostname_alone_when_not_given(path, tmp_path):
    _ready(path, tmp_path)
    expose(["192.168.1.0/24"], public_hostname="studio.example.com", path=path)
    expose(["10.0.0.0/8"], path=path)
    assert load_document(path).network.public_hostname == "studio.example.com"


def test_seal_turns_exposure_off_and_keeps_the_ranges(path, tmp_path):
    _ready(path, tmp_path)
    expose(["192.168.1.0/24"], path=path)
    seal(path=path)
    net = load_document(path).network
    assert net.exposed is False
    assert net.allowed_ranges == ("192.168.1.0/24",)


def test_seal_on_a_sealed_document_is_a_no_op(path):
    save_document(SecurityDocument(), path)
    seal(path=path)
    assert load_document(path).network.exposed is False


def test_farmhand_enabled_toggles(path):
    save_document(SecurityDocument(), path)
    set_farmhand_enabled(False, path=path)
    assert load_document(path).farmhand.enabled is False
    set_farmhand_enabled(True, path=path)
    assert load_document(path).farmhand.enabled is True


def test_allow_remote_refuses_without_auth(path):
    save_document(SecurityDocument(), path)
    with pytest.raises(SecurityError, match="authentication"):
        set_farmhand_loopback(False, path=path)


def test_allow_remote_is_permitted_with_auth_on(path, tmp_path):
    _ready(path, tmp_path)
    set_farmhand_loopback(False, path=path)
    assert load_document(path).farmhand.restrict_to_loopback is False


def test_local_only_never_needs_auth(path):
    save_document(SecurityDocument(), path)
    set_farmhand_loopback(True, path=path)
    assert load_document(path).farmhand.restrict_to_loopback is True


def test_write_tls_paths_sets_both(path, tmp_path):
    save_document(SecurityDocument(), path)
    write_tls_paths("/tmp/c.pem", "/tmp/k.pem", path=path)
    net = load_document(path).network
    assert net.tls_certfile == "/tmp/c.pem"
    assert net.tls_keyfile == "/tmp/k.pem"


def test_write_tls_paths_refuses_one_alone(path):
    save_document(SecurityDocument(), path)
    with pytest.raises(SecurityError, match="half-configured"):
        write_tls_paths("/tmp/c.pem", "", path=path)
