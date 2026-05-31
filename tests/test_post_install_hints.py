"""Tests for the PostInstallHints dataclass used by the post-install UX."""

from __future__ import annotations

import pytest
from dataclasses import FrozenInstanceError

from haywire.ui.modals.install_progress_modal import PostInstallHints


@pytest.mark.unit
def test_defaults_to_no_requirements():
    """A bare PostInstallHints() must have both flags False."""
    h = PostInstallHints()
    assert h.needs_refresh is False
    assert h.needs_restart is False


@pytest.mark.unit
def test_is_frozen():
    """PostInstallHints must be frozen (immutable after construction)."""
    h = PostInstallHints()
    with pytest.raises(FrozenInstanceError):
        h.needs_refresh = True  # type: ignore[misc]


@pytest.mark.unit
def test_merge_ors_both_flags():
    """merge() must OR each flag and return a new instance."""
    a = PostInstallHints(needs_refresh=True, needs_restart=False)
    b = PostInstallHints(needs_refresh=False, needs_restart=True)
    out = a.merge(b)
    assert out.needs_refresh is True
    assert out.needs_restart is True


@pytest.mark.unit
def test_merge_with_empty_is_identity():
    """Merging with PostInstallHints() must return an equivalent value."""
    a = PostInstallHints(needs_refresh=True, needs_restart=False)
    out = a.merge(PostInstallHints())
    assert out.needs_refresh is True
    assert out.needs_restart is False


@pytest.mark.unit
def test_merge_does_not_mutate_inputs():
    """merge() must not modify either operand."""
    a = PostInstallHints(needs_refresh=True)
    b = PostInstallHints(needs_restart=True)
    a.merge(b)
    assert a == PostInstallHints(needs_refresh=True, needs_restart=False)
    assert b == PostInstallHints(needs_refresh=False, needs_restart=True)
