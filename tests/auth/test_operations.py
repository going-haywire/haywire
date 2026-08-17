"""Roster mutation rules — shared by the CLI (slice 2) and the roster UI (slice 5)."""

import pytest

from haywire.core.access import AccessTier
from haywire_studio.auth.operations import (
    add_agent,
    add_user,
    authenticate,
    disable_auth,
    enable_auth,
    remove_principal,
    set_password,
    set_tier,
)
from haywire_studio.security.document import load_document
from haywire_studio.security.errors import SecurityError

STRONG = "Correct-Horse9"
OTHER = "Battery-Staple7"


@pytest.fixture
def path(tmp_path):
    return tmp_path / "security.json"


def test_add_user_hashes_the_password(path):
    principal = add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    assert principal.is_user
    assert STRONG not in principal.password_hash
    found = load_document(path).auth.find("alice")
    assert found is not None
    assert found.tier is AccessTier.ADMIN


def test_add_user_rejects_a_weak_password(path):
    with pytest.raises(SecurityError, match="12"):
        add_user("alice", "short", AccessTier.ADMIN, path=path)


def test_add_user_rejects_a_password_containing_the_username(path):
    with pytest.raises(SecurityError):
        add_user("alice", "Alice-Password9", AccessTier.ADMIN, path=path)


def test_add_user_rejects_a_duplicate_name(path):
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    with pytest.raises(SecurityError, match="already"):
        add_user("alice", OTHER, AccessTier.VIEW, path=path)


def test_add_user_rejects_an_empty_name(path):
    with pytest.raises(SecurityError):
        add_user("", STRONG, AccessTier.ADMIN, path=path)


def test_add_agent_mints_a_token(path):
    agent = add_agent("builder", AccessTier.EDIT, path=path)
    assert agent.is_agent
    assert len(agent.token) >= 40
    assert agent.password_hash == ""


def test_add_agent_records_the_workspace_scope(path):
    add_agent("builder", AccessTier.EDIT, workspace="/proj", path=path)
    found = load_document(path).auth.find("builder")
    assert found is not None
    assert found.workspace == "/proj"


def test_agent_tokens_are_unique(path):
    a = add_agent("one", AccessTier.EDIT, path=path)
    b = add_agent("two", AccessTier.EDIT, path=path)
    assert a.token != b.token


def test_remove_principal(path):
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    add_user("bob", OTHER, AccessTier.VIEW, path=path)
    remove_principal("bob", path=path)
    assert load_document(path).auth.find("bob") is None


def test_remove_unknown_principal_raises(path):
    with pytest.raises(SecurityError, match="No principal"):
        remove_principal("nobody", path=path)


def test_cannot_remove_the_last_admin_while_auth_is_enabled(path):
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    enable_auth("alice", STRONG, path=path)
    with pytest.raises(SecurityError, match="last admin"):
        remove_principal("alice", path=path)


def test_can_remove_an_admin_when_another_remains(path):
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    add_user("carol", OTHER, AccessTier.ADMIN, path=path)
    enable_auth("alice", STRONG, path=path)
    remove_principal("carol", path=path)
    assert load_document(path).auth.find("carol") is None


def test_cannot_demote_the_last_admin_while_auth_is_enabled(path):
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    enable_auth("alice", STRONG, path=path)
    with pytest.raises(SecurityError, match="last admin"):
        set_tier("alice", AccessTier.VIEW, path=path)


def test_cannot_demote_the_last_human_admin_even_with_an_agent_admin_present(path):
    """An agent admin can't authenticate() as a human, so it must not count as
    "another admin" that makes demoting the last human admin safe."""
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    add_agent("bot", AccessTier.ADMIN, path=path)
    enable_auth("alice", STRONG, path=path)
    with pytest.raises(SecurityError, match="last admin"):
        set_tier("alice", AccessTier.VIEW, path=path)


def test_cannot_remove_the_last_human_admin_even_with_an_agent_admin_present(path):
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    add_agent("bot", AccessTier.ADMIN, path=path)
    enable_auth("alice", STRONG, path=path)
    with pytest.raises(SecurityError, match="last admin"):
        remove_principal("alice", path=path)


def test_set_password_changes_the_hash_and_still_verifies(path):
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    set_password("alice", OTHER, path=path)
    assert authenticate("alice", OTHER, path=path) is not None
    assert authenticate("alice", STRONG, path=path) is None


def test_set_password_enforces_the_policy(path):
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    with pytest.raises(SecurityError):
        set_password("alice", "weak", path=path)


def test_set_tier(path):
    add_user("bob", STRONG, AccessTier.VIEW, path=path)
    set_tier("bob", AccessTier.EDIT, path=path)
    found = load_document(path).auth.find("bob")
    assert found is not None
    assert found.tier is AccessTier.EDIT


# --- authenticate -----------------------------------------------------


def test_authenticate_accepts_correct_credentials(path):
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    authenticated = authenticate("alice", STRONG, path=path)
    assert authenticated is not None
    assert authenticated.name == "alice"


def test_authenticate_rejects_wrong_password(path):
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    assert authenticate("alice", OTHER, path=path) is None


def test_authenticate_rejects_unknown_user(path):
    assert authenticate("nobody", STRONG, path=path) is None


def test_authenticate_never_matches_an_agent(path):
    add_agent("builder", AccessTier.EDIT, path=path)
    assert authenticate("builder", STRONG, path=path) is None


# --- enable / disable -------------------------------------------------


def test_enable_requires_a_working_admin_login(path):
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    enable_auth("alice", STRONG, path=path)
    assert load_document(path).auth.enabled is True


def test_enable_rejects_a_wrong_password(path):
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    with pytest.raises(SecurityError, match="credentials"):
        enable_auth("alice", OTHER, path=path)
    assert load_document(path).auth.enabled is False


def test_enable_rejects_a_non_admin(path):
    add_user("bob", STRONG, AccessTier.VIEW, path=path)
    with pytest.raises(SecurityError, match="admin"):
        enable_auth("bob", STRONG, path=path)
    assert load_document(path).auth.enabled is False


def test_enable_with_no_admin_at_all_raises(path):
    with pytest.raises(SecurityError):
        enable_auth("alice", STRONG, path=path)


def test_disable_requires_a_working_admin_login(path):
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    enable_auth("alice", STRONG, path=path)
    disable_auth("alice", STRONG, path=path)
    assert load_document(path).auth.enabled is False


def test_disable_rejects_a_wrong_password(path):
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    enable_auth("alice", STRONG, path=path)
    with pytest.raises(SecurityError):
        disable_auth("alice", OTHER, path=path)
    assert load_document(path).auth.enabled is True
