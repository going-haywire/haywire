"""Tests for the unified SelectionFocus command panels (count-aware labels,
batch redraw/revalidate/reset, poll contracts)."""

from unittest.mock import MagicMock

import pytest

from haybale_graph_editor.panels.context_menu.selection_actions import (
    DeleteSelectionPanel,
    RedrawSelectionPanel,
    RevalidateSelectionPanel,
    ResetSelectionPanel,
    selection_label,
)
from haybale_graph_editor.focuses import SelectionFocus
from haybale_graph_editor.editors.graph_canvas.handlers.context_menu_actions import (
    SelectionContextActions,
)


@pytest.mark.parametrize(
    "panel_cls",
    [RedrawSelectionPanel, RevalidateSelectionPanel, ResetSelectionPanel],
)
def test_batch_panel_registration(panel_cls):
    assert panel_cls.class_identity.action_protocol is SelectionContextActions
    assert panel_cls.class_identity.focus is SelectionFocus


def test_selection_label_single_node():
    assert selection_label("Delete", n_nodes=1, n_edges=0) == "Delete Node"


def test_selection_label_multiple_nodes():
    assert selection_label("Delete", n_nodes=3, n_edges=0) == "Delete 3 Nodes"


def test_selection_label_single_edge():
    assert selection_label("Delete", n_nodes=0, n_edges=1) == "Delete Edge"


def test_selection_label_mixed_falls_back_to_selection():
    assert selection_label("Delete", n_nodes=2, n_edges=1) == "Delete Selection"


def test_selection_label_multiple_edges():
    assert selection_label("Delete", n_nodes=0, n_edges=2) == "Delete 2 Edges"


def test_selection_label_zero_both_falls_back_to_selection():
    assert selection_label("Delete", n_nodes=0, n_edges=0) == "Delete Selection"


def _ctx_with_selection(nodes, edges):
    """Minimal SessionContext stub exposing data[EditState] -> selection sets."""
    from types import SimpleNamespace

    edit = SimpleNamespace(selected_nodes=set(nodes), selected_edges=set(edges))
    data = MagicMock()
    data.__getitem__.return_value = edit
    return SimpleNamespace(data=data)


def test_batch_panels_poll_true_when_nodes_selected():
    ctx = _ctx_with_selection(["n1"], [])
    assert RedrawSelectionPanel.poll(ctx) is True
    assert RevalidateSelectionPanel.poll(ctx) is True
    assert ResetSelectionPanel.poll(ctx) is True


def test_batch_panels_poll_false_when_nothing_selected():
    ctx = _ctx_with_selection([], [])
    assert RedrawSelectionPanel.poll(ctx) is False
    assert RevalidateSelectionPanel.poll(ctx) is False
    assert ResetSelectionPanel.poll(ctx) is False
