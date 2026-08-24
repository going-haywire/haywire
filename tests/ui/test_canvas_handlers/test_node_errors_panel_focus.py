"""The two node-errors panels sit on different surfaces.

The menu one is on ``SelectionMenu`` (the unified right-click menu); the
inspector one stays on ``NodeInspector``. With the display/action fork gone,
the surface id is the only thing keeping them apart — which is precisely the
double duty the Edge and Canvas splits had to resolve."""

from unittest.mock import MagicMock

from haybale_graph_editor.panels.properties.introspect.node import NodeErrorsPanel
from haybale_graph_editor.panels.graph.menu.selection.selection import (
    NodeErrorsSelectionMenuPanel as ContextMenuNodeErrorsPanel,
)
from haybale_graph_editor.surfaces import NodeInspector, SelectionMenu


def test_inspector_errors_panel_stays_on_the_node_inspector():
    assert NodeErrorsPanel.class_identity.surface is NodeInspector


def test_context_menu_errors_panel_sits_on_the_selection_menu():
    assert ContextMenuNodeErrorsPanel.class_identity.surface is SelectionMenu


def test_the_two_panels_are_on_disjoint_surfaces():
    assert NodeInspector.id != SelectionMenu.id


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
