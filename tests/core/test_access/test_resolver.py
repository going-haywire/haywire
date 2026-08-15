"""The access resolver hook — studio installs it; core defaults to full access."""

import pytest

from haywire.core.access import AccessTier, access_resolver, resolve_tier, set_access_resolver


@pytest.fixture(autouse=True)
def _restore_resolver():
    """Snapshot/restore the module global — a leaked resolver breaks later tests."""
    previous = access_resolver()
    yield
    set_access_resolver(previous)


def test_defaults_to_admin_when_no_resolver_installed():
    set_access_resolver(None)
    assert resolve_tier("alice") is AccessTier.ADMIN
    assert resolve_tier(None) is AccessTier.ADMIN


def test_installed_resolver_is_consulted():
    set_access_resolver(lambda name: AccessTier.VIEW if name == "bob" else AccessTier.EDIT)
    assert resolve_tier("bob") is AccessTier.VIEW
    assert resolve_tier("alice") is AccessTier.EDIT


def test_installed_resolver_receives_a_none_principal_intact():
    """A session with no login yet (or an internal/background session) has
    principal=None — the installed resolver decides what that means, core
    must not substitute a default before the call reaches it."""
    seen: list[str | None] = []

    def _resolver(name: str | None) -> AccessTier:
        seen.append(name)
        return AccessTier.VIEW

    set_access_resolver(_resolver)
    resolve_tier(None)
    assert seen == [None]


def test_resolver_is_called_every_time_not_cached():
    calls: list[str | None] = []

    def _resolver(name):
        calls.append(name)
        return AccessTier.EDIT

    set_access_resolver(_resolver)
    resolve_tier("alice")
    resolve_tier("alice")
    assert calls == ["alice", "alice"]


def test_resolver_raising_falls_back_to_view_not_admin():
    def _boom(name):
        raise RuntimeError("roster unreadable")

    set_access_resolver(_boom)
    assert resolve_tier("alice") is AccessTier.VIEW


def test_set_none_restores_the_default():
    set_access_resolver(lambda name: AccessTier.VIEW)
    set_access_resolver(None)
    assert resolve_tier("alice") is AccessTier.ADMIN
