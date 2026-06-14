"""The context-menu node-errors panel must register under SelectionFocus
(so it shows in the unified right-click menu); the inspector errors panel
stays under NodeFocus."""

from unittest.mock import MagicMock

from haybale_graph_editor.panels.context_menu.node_errors import (
    NodeErrorsPanel,
    ContextMenuNodeErrorsPanel,
)
from haybale_graph_editor.focuses import NodeFocus, SelectionFocus
from haybale_graph_editor.editors.graph_canvas.handlers.context_menu_actions import (
    SelectionContextActions,
)


def test_inspector_errors_panel_stays_on_node_focus():
    assert NodeErrorsPanel.class_identity.focus is NodeFocus


def test_context_menu_errors_panel_moves_to_selection_focus():
    assert ContextMenuNodeErrorsPanel.class_identity.focus is SelectionFocus
    assert ContextMenuNodeErrorsPanel.class_identity.action_protocol is SelectionContextActions


def _ctx_with_active_node(node):
    from types import SimpleNamespace

    edit = SimpleNamespace(active_node=node)
    data = MagicMock()
    data.__getitem__.return_value = edit
    return SimpleNamespace(data=data)


def test_context_menu_errors_panel_polls_on_active_node_errors():
    """Scoped to the primary (active) node's errors, not an aggregate."""
    node = MagicMock()
    node.state.get_errors.return_value = ["boom"]
    ctx = _ctx_with_active_node(node)
    assert ContextMenuNodeErrorsPanel.poll(ctx) is True

    node.state.get_errors.return_value = []
    assert ContextMenuNodeErrorsPanel.poll(ctx) is False

    ctx_none = _ctx_with_active_node(None)
    assert ContextMenuNodeErrorsPanel.poll(ctx_none) is False
