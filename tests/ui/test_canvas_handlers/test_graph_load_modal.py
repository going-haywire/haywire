"""Tests for the blocking graph-load overlay.

The overlay's job is not decoration: while a large graph mounts, the canvas
holds a partial graph (some nodes, no edges — those arrive in one batch at the
end) and the Python-side registries are still being written. Interaction has to
be impossible for that whole window, and the overlay has to come down no matter
how the load ends, or the user is stranded behind an undismissable backdrop.
"""

import pytest
from unittest.mock import MagicMock, patch

from haybale_graph_editor.editors.graph_canvas.graph_load_modal import (
    GraphLoadModal,
    graph_load_modal,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def modal():
    return GraphLoadModal(popup=MagicMock(), label=MagicMock(), bar=MagicMock(), total=10)


# ---------------------------------------------------------------------------
# Blocking configuration — the load-bearing part
# ---------------------------------------------------------------------------


def test_popup_is_not_dismissable_by_the_user():
    """No close button, no backdrop-click, no Escape.

    Any of the three would let a user reach a half-built canvas, which is the
    exact state this overlay exists to make unreachable.
    """
    with (
        patch("haybale_graph_editor.editors.graph_canvas.graph_load_modal.Popup") as popup_cls,
        patch("haybale_graph_editor.editors.graph_canvas.graph_load_modal.ui"),
    ):
        graph_load_modal(graph_name="big", total_nodes=200)

    kwargs = popup_cls.call_args.kwargs
    assert kwargs["closable"] is False
    assert kwargs["backdrop_click_close"] is False
    assert kwargs["escape_close"] is False


def test_popup_is_opened_immediately():
    """The block must be in place before the first node mounts, not after."""
    with (
        patch("haybale_graph_editor.editors.graph_canvas.graph_load_modal.Popup") as popup_cls,
        patch("haybale_graph_editor.editors.graph_canvas.graph_load_modal.ui"),
    ):
        graph_load_modal(graph_name="big", total_nodes=200)

    popup_cls.return_value.open.assert_called_once()


# ---------------------------------------------------------------------------
# Progress
# ---------------------------------------------------------------------------


def test_advance_updates_label_and_bar(modal):
    modal.advance(5)

    modal._label.set_text.assert_called_with("Mounting nodes… 5 / 10")
    modal._bar.set_value.assert_called_with(0.5)


def test_advance_accepts_the_loaders_two_arg_callback_shape(modal):
    """Passed straight as on_progress(mounted, total); total wins over the ctor count."""
    modal.advance(3, 6)

    modal._label.set_text.assert_called_with("Mounting nodes… 3 / 6")
    modal._bar.set_value.assert_called_with(0.5)


def test_advance_never_exceeds_full(modal):
    modal.advance(99)

    modal._bar.set_value.assert_called_with(1.0)


def test_advance_after_close_is_ignored(modal):
    """A cancelled load may still emit progress; it must not touch dead elements."""
    modal.close()
    modal._label.reset_mock()

    modal.advance(7)

    modal._label.set_text.assert_not_called()


# ---------------------------------------------------------------------------
# Teardown
# ---------------------------------------------------------------------------


def test_close_closes_and_deletes_the_popup(modal):
    modal.close()

    modal._popup.close.assert_called_once()
    modal._popup.delete.assert_called_once()


def test_close_is_idempotent(modal):
    """Success and cancellation paths can both call it; the second is a no-op."""
    modal.close()
    modal.close()

    modal._popup.close.assert_called_once()


def test_close_survives_a_dead_client(modal):
    """Tearing down against a disconnected browser must not raise.

    close() runs in the loader's ``finally``; if it raised, it would mask the
    real exception from the load.
    """
    modal._popup.close.side_effect = RuntimeError("client is gone")

    modal.close()  # does not raise
