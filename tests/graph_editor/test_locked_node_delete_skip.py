"""Delete skips locked nodes, and SAYS it did.

Partial success is the rule shared with drag: a locked node in the selection
does not veto the whole operation — the rest goes through. The difference is
that delete reports the skip. A silent skip in a fifty-node delete is the
failure mode where the user assumes it worked and finds out much later; the
drag case needs no toast because the node visibly staying put is the feedback.

Only the NODE is protected. Its edges are not: an edge belongs to two nodes, so
letting one veto operations on its neighbour would surprise in the other
direction.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from haywire.ui.components.graph.event_definitions import UserRemoveEvent
from haybale_graph_editor.editors.graph_canvas.handlers.visual_layer import (
    VisualLayerHandlers,
)

pytestmark = pytest.mark.unit


def _handlers(
    locked_ids: set[str],
    *,
    missing: set[str] = frozenset(),  # type: ignore[assignment]
) -> VisualLayerHandlers:
    """A handler whose graph reports `locked_ids` as locked, others unlocked.

    ``missing`` nodes answer None — a selection can name a node deleted under
    a menu that was already open.
    """

    def get_node_wrapper(node_id: str):
        if node_id in missing:
            return None
        wrapper = MagicMock()
        wrapper.node.props.locked = node_id in locked_ids
        return wrapper

    graph = MagicMock()
    graph.get_node_wrapper.side_effect = get_node_wrapper

    handlers = VisualLayerHandlers.__new__(VisualLayerHandlers)
    handlers.graph = graph
    handlers.editor = MagicMock()
    handlers.editor.remove_elements.return_value = True
    return handlers


def _remove_mock(handlers) -> MagicMock:
    """``editor.remove_elements`` as the mock it is.

    Untyped parameter on purpose: read off the real ``Editor`` attribute,
    mypy resolves the declared method signature and rejects the mock verbs.
    """
    return handlers.editor.remove_elements


def _removed(handlers) -> tuple[list[str], list[str]]:
    """The (nodes, edges) actually passed to the editor."""
    mock = _remove_mock(handlers)
    mock.assert_called_once()
    args = mock.call_args[0]
    return list(args[0]), list(args[1])


class TestLockedNodesAreSkipped:
    def test_an_unlocked_selection_is_deleted_whole(self):
        handlers = _handlers(locked_ids=set())
        with patch("haybale_graph_editor.editors.graph_canvas.handlers.visual_layer.ui"):
            handlers.process_element_removal(UserRemoveEvent(nodes=["a", "b"], edges=[]))
        assert _removed(handlers) == (["a", "b"], [])

    def test_the_unlocked_remainder_still_goes(self):
        """The rule: partial success, not a veto."""
        handlers = _handlers(locked_ids={"b"})
        with patch("haybale_graph_editor.editors.graph_canvas.handlers.visual_layer.ui"):
            handlers.process_element_removal(UserRemoveEvent(nodes=["a", "b", "c"], edges=[]))
        assert _removed(handlers) == (["a", "c"], [])

    def test_the_skip_is_reported(self):
        handlers = _handlers(locked_ids={"b"})
        with patch("haybale_graph_editor.editors.graph_canvas.handlers.visual_layer.ui") as mock_ui:
            handlers.process_element_removal(UserRemoveEvent(nodes=["a", "b"], edges=[]))
        message = mock_ui.notify.call_args[0][0]
        assert "skipped" in message, f"the skip must be named, got {message!r}"

    def test_an_all_locked_selection_deletes_nothing_and_says_so(self):
        handlers = _handlers(locked_ids={"a", "b"})
        with patch("haybale_graph_editor.editors.graph_canvas.handlers.visual_layer.ui") as mock_ui:
            handlers.process_element_removal(UserRemoveEvent(nodes=["a", "b"], edges=[]))
        _remove_mock(handlers).assert_not_called()
        assert "locked" in mock_ui.notify.call_args[0][0]

    def test_a_vanished_node_does_not_read_as_locked(self):
        """A selection can name a node deleted under an already-open menu."""
        handlers = _handlers(locked_ids=set(), missing={"gone"})
        with patch("haybale_graph_editor.editors.graph_canvas.handlers.visual_layer.ui"):
            handlers.process_element_removal(UserRemoveEvent(nodes=["gone", "a"], edges=[]))
        assert _removed(handlers) == (["gone", "a"], [])

    def test_edges_are_never_protected_by_a_locked_node(self):
        """A locked node's edges stay deletable — lock covers the node's own
        geometry and existence, not its wiring."""
        handlers = _handlers(locked_ids={"a"})
        with patch("haybale_graph_editor.editors.graph_canvas.handlers.visual_layer.ui"):
            handlers.process_element_removal(UserRemoveEvent(nodes=["a"], edges=["e1", "e2"]))
        assert _removed(handlers) == ([], ["e1", "e2"])
