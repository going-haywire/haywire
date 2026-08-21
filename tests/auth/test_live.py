"""Live tier resolution — mtime-cached roster reads behind the core resolver hook."""

import pytest

from haywire.core.access import AccessTier, access_resolver, resolve_tier, set_access_resolver
from haywire_studio.auth.live import RosterCache, install_resolver
from haywire_studio.auth.operations import add_agent, add_user, enable_auth, set_tier

STRONG = "Correct-Horse9"


@pytest.fixture(autouse=True)
def _restore_resolver():
    previous = access_resolver()
    yield
    set_access_resolver(previous)


@pytest.fixture
def path(tmp_path):
    return tmp_path / "security.json"


def test_cache_returns_the_roster(path):
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    assert RosterCache(path).roster().find("alice") is not None


def test_cache_reparses_after_mtime_changes(path):
    add_user("alice", STRONG, AccessTier.VIEW, path=path)
    cache = RosterCache(path)
    found = cache.roster().find("alice")
    assert found is not None
    assert found.tier is AccessTier.VIEW

    set_tier("alice", AccessTier.ADMIN, path=path)
    found = cache.roster().find("alice")
    assert found is not None
    assert found.tier is AccessTier.ADMIN


def test_cache_does_not_reparse_when_unchanged(path, monkeypatch):
    add_user("alice", STRONG, AccessTier.VIEW, path=path)
    cache = RosterCache(path)
    cache.roster()

    import haywire_studio.auth.live as live

    def _boom(_p):
        raise AssertionError("should not re-parse an unchanged roster")

    monkeypatch.setattr(live, "load_document", _boom)
    assert cache.roster().find("alice") is not None


def test_missing_file_resolves_to_an_empty_roster(path):
    assert RosterCache(path).roster().principals == []


def test_roster_reflects_a_write(path):
    """The cache re-parses when the file moves."""
    add_user("alice", STRONG, AccessTier.VIEW, path=path)
    cache = RosterCache(path)
    before = cache.roster().find("alice")
    assert before is not None
    assert before.tier is AccessTier.VIEW

    set_tier("alice", AccessTier.ADMIN, path=path)
    after = cache.roster().find("alice")
    assert after is not None
    assert after.tier is AccessTier.ADMIN


def test_resolver_answers_the_principals_tier(path):
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    add_user("bob", STRONG + "z", AccessTier.EDIT, path=path)
    enable_auth("alice", STRONG, path=path)
    install_resolver(RosterCache(path))
    assert resolve_tier("bob") is AccessTier.EDIT


def test_resolver_denies_an_unknown_principal_to_view(path):
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    enable_auth("alice", STRONG, path=path)
    install_resolver(RosterCache(path))
    assert resolve_tier("ghost") is AccessTier.VIEW


def test_resolver_denies_none_principal_to_view_when_auth_is_on(path):
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    enable_auth("alice", STRONG, path=path)
    install_resolver(RosterCache(path))
    assert resolve_tier(None) is AccessTier.VIEW


def test_resolver_answers_admin_when_auth_is_disabled(path):
    add_user("alice", STRONG, AccessTier.VIEW, path=path)  # roster.enabled stays False
    install_resolver(RosterCache(path))
    assert resolve_tier("alice") is AccessTier.ADMIN
    assert resolve_tier(None) is AccessTier.ADMIN


def test_demotion_is_visible_to_the_resolver_without_reinstalling(path):
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    add_user("root", STRONG + "z", AccessTier.ADMIN, path=path)
    install_resolver(RosterCache(path))
    enable_auth("alice", STRONG, path=path)
    assert resolve_tier("alice") is AccessTier.ADMIN

    set_tier("alice", AccessTier.VIEW, path=path)
    assert resolve_tier("alice") is AccessTier.VIEW


def test_agents_resolve_like_users(path):
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    add_agent("builder", AccessTier.EDIT, path=path)
    enable_auth("alice", STRONG, path=path)
    install_resolver(RosterCache(path))
    assert resolve_tier("builder") is AccessTier.EDIT
