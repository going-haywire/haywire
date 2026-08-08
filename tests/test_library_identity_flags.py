"""Tests for the post-change reload declaration on LibraryIdentity."""

from __future__ import annotations

from typing import Any, cast

import pytest

from haywire.core.library.identity import LibraryIdentity, LibraryReloadAction


def _make_identity(**overrides) -> LibraryIdentity:
    """Build a LibraryIdentity with minimal-but-complete required fields."""
    base = dict(
        label="test",
        version="1.0.0",
        description="",
        url="",
        author="",
        author_url="",
        folder_path="/tmp/test",
        module_name="test_module",
        id="test",
    )
    base.update(overrides)
    return LibraryIdentity(**cast(Any, base))


@pytest.mark.unit
def test_on_reload_defaults_to_none():
    """A library that declares nothing asks nothing of the user."""
    assert _make_identity().on_reload is LibraryReloadAction.NONE


@pytest.mark.unit
@pytest.mark.parametrize(
    "action",
    [LibraryReloadAction.NONE, LibraryReloadAction.REFRESH, LibraryReloadAction.RESTART],
)
def test_on_reload_enum_member_round_trips(action: LibraryReloadAction):
    assert _make_identity(on_reload=action).on_reload is action


@pytest.mark.unit
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("none", LibraryReloadAction.NONE),
        ("refresh", LibraryReloadAction.REFRESH),
        ("restart", LibraryReloadAction.RESTART),
        ("RESTART", LibraryReloadAction.RESTART),
        ("  refresh  ", LibraryReloadAction.REFRESH),
    ],
)
def test_on_reload_coerces_the_on_disk_string_form(raw: str, expected: LibraryReloadAction):
    """Authors write on_reload="restart" so the decorator source needs no import."""
    identity = _make_identity(on_reload=raw)
    assert identity.on_reload is expected


@pytest.mark.unit
def test_on_reload_rejects_an_unknown_value():
    """A typo must fail at import, not degrade silently to NONE."""
    with pytest.raises(ValueError, match="reboot"):
        _make_identity(on_reload="reboot")


@pytest.mark.unit
def test_reload_actions_are_ordered_by_escalating_scope():
    """merge()/max() across libraries relies on this ordering."""
    assert LibraryReloadAction.NONE < LibraryReloadAction.REFRESH < LibraryReloadAction.RESTART
    assert max(LibraryReloadAction.REFRESH, LibraryReloadAction.RESTART) is LibraryReloadAction.RESTART
    assert max(LibraryReloadAction.NONE, LibraryReloadAction.REFRESH) is LibraryReloadAction.REFRESH


@pytest.mark.unit
def test_reload_action_serializes_as_its_bare_string():
    """Farmhand JSON and the edit dialog's identity dict carry the plain value."""
    assert LibraryReloadAction.RESTART.value == "restart"
    assert f"{LibraryReloadAction.REFRESH}" == "refresh"
