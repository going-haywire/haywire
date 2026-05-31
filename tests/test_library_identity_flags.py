"""Tests for the post-install requirement flags on LibraryIdentity."""

from __future__ import annotations

import pytest

from haywire.core.library.identity import LibraryIdentity


def _make_identity(**overrides) -> LibraryIdentity:
    """Build a LibraryIdentity with minimal-but-complete required fields."""
    base = dict(
        label="test",
        version="1.0.0",
        description="",
        url="",
        help_url="",
        author="",
        author_url="",
        folder_path="/tmp/test",
        module_name="test_module",
        id="test",
    )
    base.update(overrides)
    return LibraryIdentity(**base)


@pytest.mark.unit
def test_needs_refresh_defaults_to_false():
    """LibraryIdentity.needs_refresh must default to False when not specified."""
    identity = _make_identity()
    assert identity.needs_refresh is False


@pytest.mark.unit
def test_needs_restart_defaults_to_false():
    """LibraryIdentity.needs_restart must default to False when not specified."""
    identity = _make_identity()
    assert identity.needs_restart is False


@pytest.mark.unit
def test_needs_refresh_explicit_true_preserved():
    """An explicit needs_refresh=True must round-trip through the dataclass."""
    identity = _make_identity(needs_refresh=True)
    assert identity.needs_refresh is True


@pytest.mark.unit
def test_needs_restart_explicit_true_preserved():
    """An explicit needs_restart=True must round-trip through the dataclass."""
    identity = _make_identity(needs_restart=True)
    assert identity.needs_restart is True


@pytest.mark.unit
def test_both_flags_can_be_set_together():
    """Both flags can be True simultaneously."""
    identity = _make_identity(needs_refresh=True, needs_restart=True)
    assert identity.needs_refresh is True
    assert identity.needs_restart is True
