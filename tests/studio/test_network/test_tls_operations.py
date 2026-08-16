"""The rules: setup, update, status classification, and the trust command."""

import datetime
import hashlib
import json

import pytest

from haywire_studio.network import certs
from haywire_studio.network.certs import CertError
from haywire_studio.network.names import LocalNames
from haywire_studio.network.tls_operations import (
    TlsState,
    setup,
    status,
    trust_command,
    update,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def env(tmp_path, monkeypatch):
    """A certificate directory and a settings file, isolated from ~/.haywire."""

    class Env:
        directory = tmp_path / "certs"
        settings = tmp_path / "settings.json"

    # Reads resolve workspace-over-global, so run from an empty workspace: the
    # repo's own .haywire/settings.json would otherwise win over env.settings.
    workspace = tmp_path / "empty_workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)

    # Pin the machine's identity so tests do not depend on the host running them.
    monkeypatch.setattr(
        "haywire_studio.network.tls_operations.local_names",
        lambda: LocalNames(dns=("localhost", "box.local"), ip=("127.0.0.1", "::1", "10.0.0.5")),
    )
    monkeypatch.setattr("haywire_studio.network.tls_operations.primary_address", lambda: "10.0.0.5")
    return Env


def _write_settings(env, **network):
    env.settings.write_text(
        json.dumps({"network": {k: {"value": v} for k, v in network.items()}}),
        encoding="utf-8",
    )


def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --------------------------------------------------------------------------
# setup
# --------------------------------------------------------------------------


def test_setup_creates_both_files_and_configures_them(env):
    result = setup(directory=env.directory, settings_path=env.settings)
    assert result.cert_path.exists()
    assert result.key_path.exists()
    data = json.loads(env.settings.read_text(encoding="utf-8"))
    assert data["network"]["ssl_certfile"]["value"] == str(result.cert_path)
    assert data["network"]["ssl_keyfile"]["value"] == str(result.key_path)


def test_setup_covers_local_names(env):
    result = setup(directory=env.directory, settings_path=env.settings)
    assert "box.local" in result.covered.dns
    assert "10.0.0.5" in result.covered.ip


def test_setup_merges_extra_names(env):
    result = setup(["studio.example.com"], directory=env.directory, settings_path=env.settings)
    assert "studio.example.com" in result.covered.dns


def test_setup_merges_public_hostname_stripping_the_port(env):
    _write_settings(env, public_hostname="haywire.example.com:443")
    result = setup(directory=env.directory, settings_path=env.settings)
    assert "haywire.example.com" in result.covered.dns
    assert not [name for name in result.covered.dns if ":" in name]


def test_setup_twice_is_refused(env):
    setup(directory=env.directory, settings_path=env.settings)
    with pytest.raises(CertError, match="already exists"):
        setup(directory=env.directory, settings_path=env.settings)


def test_setup_adopts_an_orphaned_certificate_without_regenerating(env):
    """The guarantee: a certificate the user may already have trusted
    elsewhere is never silently replaced."""
    first = setup(directory=env.directory, settings_path=env.settings)
    before_cert, before_key = _digest(first.cert_path), _digest(first.key_path)

    env.settings.write_text(json.dumps({"network": {}}), encoding="utf-8")

    result = setup(directory=env.directory, settings_path=env.settings)
    assert result.adopted is True
    assert _digest(first.cert_path) == before_cert
    assert _digest(first.key_path) == before_key
    data = json.loads(env.settings.read_text(encoding="utf-8"))
    assert data["network"]["ssl_certfile"]["value"] == str(first.cert_path)


# --------------------------------------------------------------------------
# update
# --------------------------------------------------------------------------


def test_update_without_a_certificate_is_refused(env):
    with pytest.raises(CertError, match="ssl setup"):
        update(directory=env.directory, settings_path=env.settings)


def test_update_reuses_the_private_key(env):
    created = setup(directory=env.directory, settings_path=env.settings)
    key_before = _digest(created.key_path)
    update(add=["10.9.9.9"], directory=env.directory, settings_path=env.settings)
    assert _digest(created.key_path) == key_before


def test_update_add_preserves_existing_names(env):
    setup(["manual.example.com"], directory=env.directory, settings_path=env.settings)
    result = update(add=["10.9.9.9"], directory=env.directory, settings_path=env.settings)
    assert "manual.example.com" in result.covered.dns
    assert "10.9.9.9" in result.covered.ip


def test_update_refresh_unions_local_names_keeping_manual_ones(env, monkeypatch):
    setup(["manual.example.com"], directory=env.directory, settings_path=env.settings)
    monkeypatch.setattr(
        "haywire_studio.network.tls_operations.local_names",
        lambda: LocalNames(dns=("localhost",), ip=("127.0.0.1", "192.168.1.50")),
    )
    result = update(refresh=True, directory=env.directory, settings_path=env.settings)
    assert "192.168.1.50" in result.covered.ip
    assert "manual.example.com" in result.covered.dns
    assert "10.0.0.5" in result.covered.ip


def test_update_can_remove_a_name(env):
    setup(["gone.example.com"], directory=env.directory, settings_path=env.settings)
    result = update(remove=["gone.example.com"], directory=env.directory, settings_path=env.settings)
    assert "gone.example.com" not in result.covered.dns


def test_update_refuses_to_remove_loopback(env):
    setup(directory=env.directory, settings_path=env.settings)
    with pytest.raises(CertError, match="localhost"):
        update(remove=["localhost"], directory=env.directory, settings_path=env.settings)


def test_update_on_a_mismatched_pair_names_both_files(env):
    created = setup(directory=env.directory, settings_path=env.settings)
    certs.write_key(certs.generate_key(), env.directory)
    with pytest.raises(CertError) as exc:
        update(add=["10.9.9.9"], directory=env.directory, settings_path=env.settings)
    assert str(created.key_path) in str(exc.value)
    assert str(created.cert_path) in str(exc.value)


# --------------------------------------------------------------------------
# status
# --------------------------------------------------------------------------


def test_status_off_loopback_when_not_exposed(env):
    assert status(directory=env.directory, settings_path=env.settings).state is TlsState.OFF_LOOPBACK


def test_status_off_exposed_when_exposed(env):
    _write_settings(env, expose_to_network=True)
    assert status(directory=env.directory, settings_path=env.settings).state is TlsState.OFF_EXPOSED


def test_status_ok_after_setup(env):
    setup(directory=env.directory, settings_path=env.settings)
    result = status(directory=env.directory, settings_path=env.settings)
    assert result.state is TlsState.OK
    assert result.fingerprint
    assert result.expires is not None


def test_status_not_covered_when_the_address_changed(env, monkeypatch):
    setup(directory=env.directory, settings_path=env.settings)
    monkeypatch.setattr("haywire_studio.network.tls_operations.primary_address", lambda: "192.168.1.77")
    result = status(directory=env.directory, settings_path=env.settings)
    assert result.state is TlsState.NOT_COVERED
    assert result.covered_alternative() == "box.local"


def test_status_file_missing_when_the_certificate_was_deleted(env):
    created = setup(directory=env.directory, settings_path=env.settings)
    created.cert_path.unlink()
    result = status(directory=env.directory, settings_path=env.settings)
    assert result.state is TlsState.FILE_MISSING
    assert "ssl_certfile" in result.detail


def test_status_half_configured(env):
    _write_settings(env, ssl_certfile="/somewhere/studio.crt")
    result = status(directory=env.directory, settings_path=env.settings)
    assert result.state is TlsState.HALF_CONFIGURED
    assert "ssl_keyfile" in result.detail


def test_status_orphaned_when_settings_were_cleared(env):
    setup(directory=env.directory, settings_path=env.settings)
    env.settings.write_text(json.dumps({"network": {}}), encoding="utf-8")
    assert status(directory=env.directory, settings_path=env.settings).state is TlsState.ORPHANED


def test_status_key_mismatch(env):
    setup(directory=env.directory, settings_path=env.settings)
    certs.write_key(certs.generate_key(), env.directory)
    assert status(directory=env.directory, settings_path=env.settings).state is TlsState.KEY_MISMATCH


def test_status_unreadable_certificate(env):
    created = setup(directory=env.directory, settings_path=env.settings)
    created.cert_path.write_text("not a certificate", encoding="utf-8")
    assert status(directory=env.directory, settings_path=env.settings).state is TlsState.UNREADABLE


def test_status_expiring(env, monkeypatch):
    setup(directory=env.directory, settings_path=env.settings)
    soon = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=5)
    monkeypatch.setattr("haywire_studio.network.certs.cert_expiry", lambda cert: soon)
    assert status(directory=env.directory, settings_path=env.settings).state is TlsState.EXPIRING


def test_status_never_raises_on_a_broken_settings_file(env):
    env.settings.write_text("{ broken", encoding="utf-8")
    assert status(directory=env.directory, settings_path=env.settings).state is TlsState.OFF_LOOPBACK


# --------------------------------------------------------------------------
# trust
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("platform", "expected"),
    [
        ("darwin", "security add-trusted-cert"),
        ("win32", "Import-Certificate"),
        ("linux", "update-ca-certificates"),
    ],
)
def test_trust_command_per_platform(env, platform, expected):
    assert expected in trust_command(env.directory, platform=platform)


def test_trust_command_names_the_certificate(env):
    _, cert_path = certs.paths(env.directory)
    assert str(cert_path) in trust_command(env.directory, platform="darwin")
