"""SessionContext access predicates — read live authority, never a stamped tier."""

from unittest.mock import MagicMock

import pytest

from haywire.core.access import AccessTier, access_resolver, set_access_resolver
from haywire.core.session.context import SessionContext


@pytest.fixture(autouse=True)
def _restore_resolver():
    previous = access_resolver()
    yield
    set_access_resolver(previous)


def _ctx() -> SessionContext:
    app = MagicMock()
    app.library_state_container = MagicMock()
    return SessionContext(session_id="s1", app=app)


def test_principal_defaults_to_none():
    assert _ctx().principal is None


def test_everything_allowed_when_no_resolver_installed():
    set_access_resolver(None)
    ctx = _ctx()
    assert ctx.can_view() is True
    assert ctx.can_edit() is True
    assert ctx.can_admin() is True


def test_view_principal_can_only_view():
    set_access_resolver(lambda name: AccessTier.VIEW)
    ctx = _ctx()
    ctx.principal = "bob"
    assert ctx.can_view() is True
    assert ctx.can_edit() is False
    assert ctx.can_admin() is False


def test_edit_principal_can_view_and_edit():
    set_access_resolver(lambda name: AccessTier.EDIT)
    ctx = _ctx()
    ctx.principal = "carol"
    assert ctx.can_view() is True
    assert ctx.can_edit() is True
    assert ctx.can_admin() is False


def test_can_access_takes_the_tier_as_data():
    set_access_resolver(lambda name: AccessTier.EDIT)
    ctx = _ctx()
    ctx.principal = "carol"
    assert ctx.can_access(AccessTier.VIEW) is True
    assert ctx.can_access(AccessTier.EDIT) is True
    assert ctx.can_access(AccessTier.ADMIN) is False


def test_the_principal_name_reaches_the_resolver():
    seen: list[str | None] = []

    def _resolver(name: str | None) -> AccessTier:
        seen.append(name)
        return AccessTier.VIEW

    set_access_resolver(_resolver)
    ctx = _ctx()
    ctx.principal = "dave"
    ctx.can_edit()
    assert seen == ["dave"]


def test_demotion_takes_effect_without_touching_the_context():
    """The whole point of reading live: no re-login, no eviction, no stale tier."""
    tier = {"value": AccessTier.ADMIN}
    set_access_resolver(lambda name: tier["value"])
    ctx = _ctx()
    ctx.principal = "erin"
    assert ctx.can_admin() is True

    tier["value"] = AccessTier.VIEW
    assert ctx.can_admin() is False
    assert ctx.can_view() is True
