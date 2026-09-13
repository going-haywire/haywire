"""NODE_LAYOUT_CHANGED repaints AND persists.

The category `is_visual_only` documents via NODE_MOVED: a move repaints, but
position is persisted as props.posX/posY, so an app layer must still mark the
file unsaved. A port reorder is the same shape — it changes only what the card
draws, and it is saved.
"""

from __future__ import annotations

import pytest

from haywire.core.graph.types import ChangeReason

pytestmark = pytest.mark.unit


def test_layout_changed_exists() -> None:
    assert ChangeReason.NODE_LAYOUT_CHANGED.value == "node_layout_changed"


def test_layout_changed_requires_a_redraw() -> None:
    """Pins move between positions, so the card is rebuilt."""
    assert ChangeReason.NODE_LAYOUT_CHANGED.requires_redraw() is True


def test_layout_changed_is_not_visual_only() -> None:
    """is_visual_only() True would tell the app not to mark the file unsaved."""
    assert ChangeReason.NODE_LAYOUT_CHANGED.is_visual_only() is False


def test_layout_changed_needs_no_reassembly() -> None:
    """The ports are identical; only their order changed."""
    assert ChangeReason.NODE_LAYOUT_CHANGED.requires_graph_reassembly() is False
