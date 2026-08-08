"""Tests for the PostInstallHints dataclass used by the post-install UX."""

from __future__ import annotations

import pytest
from dataclasses import FrozenInstanceError

from haywire.core.library.identity import LibraryReloadAction
from haywire.ui.modals.install_progress_modal import PostInstallHints


@pytest.mark.unit
def test_defaults_to_no_requirement():
    """A bare PostInstallHints() must ask nothing of the user."""
    assert PostInstallHints().action is LibraryReloadAction.NONE


@pytest.mark.unit
def test_is_frozen():
    """PostInstallHints must be frozen (immutable after construction)."""
    h = PostInstallHints()
    with pytest.raises(FrozenInstanceError):
        h.action = LibraryReloadAction.RESTART  # type: ignore[misc]


@pytest.mark.unit
def test_merge_keeps_the_more_demanding_action():
    """One install can import several libraries; the heaviest ask wins."""
    a = PostInstallHints(LibraryReloadAction.REFRESH)
    b = PostInstallHints(LibraryReloadAction.RESTART)
    assert a.merge(b).action is LibraryReloadAction.RESTART
    assert b.merge(a).action is LibraryReloadAction.RESTART


@pytest.mark.unit
def test_merge_with_empty_is_identity():
    """Merging with PostInstallHints() must return an equivalent value."""
    a = PostInstallHints(LibraryReloadAction.REFRESH)
    assert a.merge(PostInstallHints()).action is LibraryReloadAction.REFRESH
    assert PostInstallHints().merge(a).action is LibraryReloadAction.REFRESH


@pytest.mark.unit
def test_merge_is_idempotent():
    a = PostInstallHints(LibraryReloadAction.RESTART)
    assert a.merge(a).action is LibraryReloadAction.RESTART


@pytest.mark.unit
def test_merge_does_not_mutate_inputs():
    """merge() must not modify either operand."""
    a = PostInstallHints(LibraryReloadAction.REFRESH)
    b = PostInstallHints(LibraryReloadAction.RESTART)
    a.merge(b)
    assert a == PostInstallHints(LibraryReloadAction.REFRESH)
    assert b == PostInstallHints(LibraryReloadAction.RESTART)
