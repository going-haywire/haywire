"""Writing ssl_certfile/ssl_keyfile into ~/.haywire/settings.json.

Clobbering a user's settings is the most damaging thing this feature could do —
the real file holds expose_to_network, allowed_remote_ranges, public_hostname
and trusted_proxies — so preservation is tested harder than the write itself.
"""

import json

import pytest

from haywire_studio.network.tls_settings import (
    SettingsWriteError,
    read_network_setting,
    read_tls_paths,
    write_tls_paths,
)

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _empty_workspace(tmp_path, monkeypatch):
    """Run from a workspace with no settings file.

    Reads resolve workspace-over-global, so without this the *repo's own*
    ``.haywire/settings.json`` wins over whatever a test writes to its
    ``path=`` file — inverting the assertions rather than failing loudly.
    """
    workspace = tmp_path / "empty_workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)


@pytest.fixture
def settings_file(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps(
            {
                "network": {
                    "expose_to_network": {"value": True},
                    "allowed_remote_ranges": {"value": "192.168.0.0/24"},
                    "public_hostname": {"value": "studio.example.com:443"},
                    "trusted_proxies": {"value": "172.16.0.0/12"},
                },
                "farmhand": {"require_auth": {"value": True}},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def test_unrelated_network_keys_survive(settings_file):
    """The four live network settings must not be disturbed."""
    write_tls_paths("/certs/studio.crt", "/certs/studio.key", path=settings_file)
    data = json.loads(settings_file.read_text(encoding="utf-8"))
    network = data["network"]
    assert network["expose_to_network"]["value"] is True
    assert network["allowed_remote_ranges"]["value"] == "192.168.0.0/24"
    assert network["public_hostname"]["value"] == "studio.example.com:443"
    assert network["trusted_proxies"]["value"] == "172.16.0.0/12"


def test_unrelated_namespaces_survive(settings_file):
    write_tls_paths("/certs/studio.crt", "/certs/studio.key", path=settings_file)
    data = json.loads(settings_file.read_text(encoding="utf-8"))
    assert data["farmhand"]["require_auth"]["value"] is True


def test_paths_are_written_in_the_expected_shape(settings_file):
    write_tls_paths("/certs/studio.crt", "/certs/studio.key", path=settings_file)
    data = json.loads(settings_file.read_text(encoding="utf-8"))
    assert data["network"]["ssl_certfile"] == {"value": "/certs/studio.crt"}
    assert data["network"]["ssl_keyfile"] == {"value": "/certs/studio.key"}


def test_round_trips_through_read(settings_file):
    write_tls_paths("/certs/studio.crt", "/certs/studio.key", path=settings_file)
    assert read_tls_paths(path=settings_file) == ("/certs/studio.crt", "/certs/studio.key")


def test_writing_twice_is_idempotent(settings_file):
    write_tls_paths("/a.crt", "/a.key", path=settings_file)
    first = settings_file.read_text(encoding="utf-8")
    write_tls_paths("/a.crt", "/a.key", path=settings_file)
    assert settings_file.read_text(encoding="utf-8") == first


def test_missing_file_is_created(tmp_path):
    target = tmp_path / "nested" / "settings.json"
    write_tls_paths("/a.crt", "/a.key", path=target)
    assert read_tls_paths(path=target) == ("/a.crt", "/a.key")


def test_unparseable_file_raises_rather_than_overwriting(tmp_path):
    """A hand-edited typo must be reported, never silently replaced."""
    target = tmp_path / "settings.json"
    target.write_text("{ this is not json", encoding="utf-8")
    with pytest.raises(SettingsWriteError):
        write_tls_paths("/a.crt", "/a.key", path=target)
    assert target.read_text(encoding="utf-8") == "{ this is not json"


def test_reading_an_absent_file_yields_empty_paths(tmp_path):
    assert read_tls_paths(path=tmp_path / "nope.json") == ("", "")


def test_reading_an_unparseable_file_yields_empty_paths(tmp_path):
    """status must still run against a broken file — it is how the user finds out."""
    target = tmp_path / "settings.json"
    target.write_text("{ broken", encoding="utf-8")
    assert read_tls_paths(path=target) == ("", "")


def test_read_network_setting_returns_values(settings_file):
    assert read_network_setting("expose_to_network", path=settings_file) is True
    assert read_network_setting("public_hostname", path=settings_file) == "studio.example.com:443"


def test_read_network_setting_defaults_when_absent(tmp_path):
    assert read_network_setting("expose_to_network", path=tmp_path / "nope.json") is None


# ---------------------------------------------------------------------------
# Tier resolution — workspace beats global
# ---------------------------------------------------------------------------


def _write_workspace(namespace):
    """Write ``<cwd>/.haywire/settings.json`` — the tier the studio prefers."""
    from pathlib import Path

    target = Path.cwd() / ".haywire"
    target.mkdir(parents=True, exist_ok=True)
    (target / "settings.json").write_text(
        json.dumps({"network": {k: {"value": v} for k, v in namespace.items()}}), encoding="utf-8"
    )


def test_workspace_value_beats_global(settings_file):
    """The registry resolves workspace SET > global SET, so reporting the
    global value alone describes a studio that will not run."""
    _write_workspace({"expose_to_network": False})
    assert read_network_setting("expose_to_network", path=settings_file) is False


def test_global_value_applies_when_workspace_omits_the_key(settings_file):
    _write_workspace({"public_hostname": "ws.example.com"})
    assert read_network_setting("expose_to_network", path=settings_file) is True
    assert read_network_setting("public_hostname", path=settings_file) == "ws.example.com"


def test_workspace_tls_paths_beat_global(settings_file):
    write_tls_paths("/global.crt", "/global.key", path=settings_file)
    _write_workspace({"ssl_certfile": "/ws.crt", "ssl_keyfile": "/ws.key"})
    assert read_tls_paths(path=settings_file) == ("/ws.crt", "/ws.key")


def test_a_workspace_false_is_not_mistaken_for_absent(settings_file):
    """``False`` is a set value, not a missing one — the distinction the
    ``_UNSET`` sentinel exists for. Without it, turning exposure off in a
    workspace would silently fall through to the global ``true``."""
    _write_workspace({"expose_to_network": False})
    assert read_network_setting("expose_to_network", path=settings_file) is False
    _write_workspace({"allowed_remote_ranges": ""})
    assert read_network_setting("allowed_remote_ranges", path=settings_file) == ""


def test_write_leaves_no_temp_file(settings_file):
    write_tls_paths("/a.crt", "/a.key", path=settings_file)
    assert not list(settings_file.parent.glob(".*.tmp"))


def test_bare_value_entries_are_tolerated(tmp_path):
    """The store also accepts scalars, not just {'value': …} tables."""
    target = tmp_path / "settings.json"
    target.write_text(json.dumps({"network": {"port": 9000}}), encoding="utf-8")
    write_tls_paths("/a.crt", "/a.key", path=target)
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["network"]["port"] == 9000
    assert data["network"]["ssl_certfile"]["value"] == "/a.crt"
