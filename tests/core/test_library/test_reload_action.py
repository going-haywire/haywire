"""on_reload is stored in its wire form; the enum is reachable for ordering."""

from typing import Any, cast

import pytest

from haywire.core.library.identity import LibraryIdentity, LibraryReloadAction


def _identity(**overrides):
    base = dict(
        label="Demo",
        version="0.1.0",
        folder_path="/tmp/demo",
        module_name="haybale_demo",
        name="demo",
    )
    base.update(overrides)
    return LibraryIdentity(**cast(Any, base))


def test_on_reload_is_a_plain_string():
    identity = _identity(on_reload="restart")
    assert identity.on_reload == "restart"
    assert type(identity.on_reload) is str


def test_default_is_none_wire_value():
    assert _identity().on_reload == "none"


def test_enum_input_is_normalised_to_its_value():
    identity = _identity(on_reload=LibraryReloadAction.REFRESH)
    assert identity.on_reload == "refresh"
    assert type(identity.on_reload) is str


@pytest.mark.parametrize("raw", ["NONE", " Restart ", "refresh"])
def test_case_and_whitespace_are_normalised(raw):
    assert _identity(on_reload=raw).on_reload == raw.strip().lower()


def test_reload_action_returns_the_enum():
    assert _identity(on_reload="restart").reload_action is LibraryReloadAction.RESTART


def test_reload_action_supports_max_across_libraries():
    """Combining declarations is max() — the reason the enum is still reachable."""
    actions = [_identity(on_reload=v).reload_action for v in ("none", "restart", "refresh")]
    assert max(actions) is LibraryReloadAction.RESTART


def test_unknown_value_raises_at_construction():
    with pytest.raises(ValueError, match="explode"):
        _identity(on_reload="explode")
