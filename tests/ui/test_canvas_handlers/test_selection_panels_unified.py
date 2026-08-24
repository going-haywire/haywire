"""Tests for the unified SelectionMenu command panels (count-aware labels,
batch redraw/revalidate/reset, poll contracts)."""

from unittest.mock import MagicMock

from typing import Any, cast

import pytest

from haybale_graph_editor.panels.graph.menu.selection.selection import (
    DeleteSelectionMenuPanel as DeleteSelectionPanel,
    RebuildSelectionMenuPanel as RebuildSelectionPanel,
    RedrawSelectionMenuPanel as RedrawSelectionPanel,
    RevalidateSelectionMenuPanel as RevalidateSelectionPanel,
    ResetSelectionMenuPanel as ResetSelectionPanel,
    selection_label,
)
from haybale_graph_editor.surfaces import SelectionActions, SelectionMenu, SelectionRebuildMenu


@pytest.mark.parametrize(
    "panel_cls",
    [RedrawSelectionPanel, RevalidateSelectionPanel, ResetSelectionPanel],
)
def test_batch_panel_registration(panel_cls):
    """The three batch commands sit on the Rebuild submenu, not flat on the menu."""
    assert panel_cls.class_identity.surface is SelectionRebuildMenu
    assert SelectionRebuildMenu.provides is SelectionActions


def test_rebuild_panel_hosts_the_batch_submenu():
    """The row itself stays on SelectionMenu and declares what it renders —
    render_surface refuses any surface not listed in hosts=."""
    assert RebuildSelectionPanel.class_identity.surface is SelectionMenu
    assert RebuildSelectionPanel.class_identity.hosts == (SelectionRebuildMenu,)
    assert SelectionMenu.provides is SelectionActions


def test_rebuild_panel_polls_like_the_commands_it_hosts():
    assert RebuildSelectionPanel.poll(_ctx_with_selection(["n1"], [])) is True
    assert RebuildSelectionPanel.poll(_ctx_with_selection([], [])) is False


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


def test_copy_and_delete_panels_use_count_aware_labels(monkeypatch):
    """Copy/Delete panel draw() renders a count-aware label via selection_label."""
    import haybale_graph_editor.panels.graph.menu.selection.selection as sa
    from haybale_graph_editor.panels.graph.menu.selection.selection import (
        CopySelectionMenuPanel as CopySelectionPanel,
    )

    rendered_labels = []

    class _FakeLayout:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def _fake_menu_row(label, **kwargs):
        rendered_labels.append(label)

    monkeypatch.setattr(sa.hui, "menu_row", _fake_menu_row)

    ctx = _ctx_with_selection(["n1", "n2", "n3"], [])
    actions = MagicMock()

    panel = DeleteSelectionPanel()
    panel.actions = actions
    panel.draw(ctx, cast(Any, _FakeLayout()))

    panel2 = CopySelectionPanel()
    panel2.actions = actions
    panel2.draw(ctx, cast(Any, _FakeLayout()))

    assert "Delete 3 Nodes" in rendered_labels
    assert "Copy 3 Nodes" in rendered_labels
