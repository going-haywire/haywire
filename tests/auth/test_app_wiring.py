"""HaywireApp wiring — gate installed only when the roster says so; TLS passthrough."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from haywire.core.access import AccessTier, access_resolver, set_access_resolver
from haywire_studio.auth.operations import add_user, enable_auth
from haywire_studio.auth.roster import Roster, save_roster

if TYPE_CHECKING:
    from haywire_studio.app import HaywireApp

STRONG = "Correct-Horse9"


@pytest.fixture(autouse=True)
def _restore_resolver():
    """``_install_auth`` calls ``install_resolver``, which sets the module-level
    global resolver — same leak this pattern guards against in
    tests/auth/test_live.py, tests/core/test_access/test_resolver.py, and
    tests/core/test_session/test_context_access.py."""
    previous = access_resolver()
    yield
    set_access_resolver(previous)


@pytest.fixture
def enabled(tmp_path):
    path = tmp_path / "auth.json"
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    enable_auth("alice", STRONG, path=path)
    return path


@pytest.fixture
def disabled(tmp_path):
    path = tmp_path / "auth.json"
    save_roster(Roster(enabled=False), path)
    return path


def _isolated_home(tmp_path, monkeypatch):
    """Point roster_path()/secret_path() (both ``~/.haywire/...``) at tmp_path.

    ``_install_auth`` hardcodes the real global paths (no path injection), so
    isolating it from the developer's actual ``~/.haywire`` requires
    redirecting ``Path.home()`` for the duration of the test. Returns the
    ``~/.haywire`` dir so a test can drop a roster file at the exact path
    ``_install_auth`` will read.
    """
    home = tmp_path / "home"
    haywire_dir = home / ".haywire"
    haywire_dir.mkdir(parents=True)
    monkeypatch.setattr("pathlib.Path.home", lambda: home)
    return haywire_dir


def test_ssl_kwargs_empty_when_no_cert_configured():
    from haywire_studio.app import _ssl_kwargs

    assert _ssl_kwargs("", "") == {}


def test_ssl_kwargs_populated_when_both_set(tmp_path):
    from haywire_studio.app import _ssl_kwargs

    cert, key = tmp_path / "c.pem", tmp_path / "k.pem"
    cert.write_text("x")
    key.write_text("y")
    assert _ssl_kwargs(str(cert), str(key)) == {"ssl_certfile": str(cert), "ssl_keyfile": str(key)}


def test_ssl_kwargs_exits_when_only_one_is_set(tmp_path):
    from haywire_studio.app import _ssl_kwargs

    cert = tmp_path / "c.pem"
    cert.write_text("x")
    with pytest.raises(SystemExit):
        _ssl_kwargs(str(cert), "")


def test_ssl_kwargs_exits_when_a_file_is_missing(tmp_path):
    from haywire_studio.app import _ssl_kwargs

    with pytest.raises(SystemExit):
        _ssl_kwargs(str(tmp_path / "nope.pem"), str(tmp_path / "nope.key"))


def test_farmhand_origins_use_https_when_tls_is_on():
    from haywire_studio.farmhand.host import _origin_scheme

    assert _origin_scheme(tls=True) == "https"
    assert _origin_scheme(tls=False) == "http"


# -- _install_auth -----------------------------------------------------
#
# _install_auth() only touches `self` to read `self.workspace_root` and
# stash `self._auth_cache`, so `HaywireApp.__new__(HaywireApp)` (skips
# `__init__`, matching the precedent in test_ip_allowlist_wiring.py) is
# enough — building a real HaywireApp would stand up the whole library
# system for no benefit.


def _bare_app(workspace_root: str = "") -> "HaywireApp":
    from haywire_studio.app import HaywireApp

    instance = HaywireApp.__new__(HaywireApp)
    instance.workspace_root = workspace_root
    return instance


def test_disabled_roster_installs_nothing_and_returns_false(tmp_path, monkeypatch, disabled):
    _isolated_home(tmp_path, monkeypatch)
    from haywire_studio.auth.roster import roster_path

    roster_path().write_bytes(disabled.read_bytes())

    instance = _bare_app()
    assert instance._install_auth() is False
    assert not hasattr(instance, "_auth_cache")


def test_enabled_roster_with_admin_installs_gate_and_returns_true(tmp_path, monkeypatch, enabled):
    _isolated_home(tmp_path, monkeypatch)
    from haywire_studio.auth.roster import roster_path

    roster_path().write_bytes(enabled.read_bytes())

    installed = {}

    def _fake_add_middleware(cls, **kwargs):
        installed["middleware_cls"] = cls
        installed["kwargs"] = kwargs

    monkeypatch.setattr("nicegui.app.add_middleware", _fake_add_middleware)

    instance = _bare_app()
    assert instance._install_auth() is True
    assert hasattr(instance, "_auth_cache")
    assert installed["middleware_cls"].__name__ == "AuthGateMiddleware"
    assert installed["kwargs"]["cache"] is instance._auth_cache


def test_enabled_roster_without_admin_exits(tmp_path, monkeypatch):
    _isolated_home(tmp_path, monkeypatch)
    from haywire_studio.auth.roster import Roster, roster_path, save_roster

    # enabled=True with no principals at all — no admin exists.
    save_roster(Roster(enabled=True), roster_path())

    instance = _bare_app()
    with pytest.raises(SystemExit):
        instance._install_auth()


def test_unreadable_roster_exits_loudly_at_startup(tmp_path, monkeypatch):
    """The first-ever read must fail startup, unlike RosterCache.roster()'s
    later swallow-and-keep-last-good behaviour (live.py) which is correct
    only once a good copy already exists."""
    _isolated_home(tmp_path, monkeypatch)
    from haywire_studio.auth.roster import roster_path

    roster_path().write_text("not valid json")

    instance = _bare_app()
    with pytest.raises(SystemExit):
        instance._install_auth()
