# tests/libraries/test_surfaces_have_ids.py
"""Every Surface in the in-tree libraries declares an id and registers under it."""

from haywire.ui.surface import surface_by_id


def test_node_inspector_has_id():
    # Importing the module triggers Surface.__init_subclass__.
    from haybale_graph_editor.surfaces import NodeInspector

    assert NodeInspector.id == "node"
    assert surface_by_id("node") is NodeInspector


def test_edge_split_keeps_edge_for_the_inspector():
    """The *menu* took the new id, so DOM attributes and docs on ``edge`` still
    point at the properties tab."""
    from haybale_graph_editor.surfaces import EdgeInspector, EdgeMenu

    assert EdgeInspector.id == "edge"
    assert surface_by_id("edge") is EdgeInspector
    assert EdgeMenu.id == "edge-menu"
    assert surface_by_id("edge-menu") is EdgeMenu


def test_edge_split_get_panels_are_disjoint_and_neither_is_empty():
    """The id split above is necessary but not sufficient: this is the split
    that actually matters — EdgeInspector (the properties tab) and EdgeMenu
    (the right-click menu) must show DIFFERENT panels, or the whole point of
    splitting EdgeFocus in two is defeated. Registers the real, in-tree panel
    classes for both surfaces (not synthetic test doubles) and checks
    get_panels() against a fresh registry, since @panel does not
    self-register."""
    from haywire.core.library.identity import LibraryIdentity
    from haywire.ui.panel.registry import PanelRegistry
    from haybale_graph_editor.surfaces import EdgeInspector, EdgeMenu
    from haybale_graph_editor.panels.graph.menu.edge.edge import (
        DeleteEdgeMenuPanel,
        EdgeErrorsMenuPanel,
        EdgeWarningsMenuPanel,
        InsertRerouteMenuPanel,
        ReconnectEdgeMenuPanel,
    )
    from haybale_graph_editor.panels.properties.introspect.edge import (
        EdgeErrorsPanel,
        EdgePathPanel,
        EdgeStatsPanel,
        EdgeWarningsPanel,
    )

    identity = LibraryIdentity(
        label="Graph Editor Test",
        version="0.0.1",
        folder_path="/tmp/edge-split-test",
        module_name="haybale_graph_editor",
        name="graph_editor",
    )

    registry = PanelRegistry()
    menu_panels = (
        EdgeErrorsMenuPanel,
        EdgeWarningsMenuPanel,
        InsertRerouteMenuPanel,
        DeleteEdgeMenuPanel,
        ReconnectEdgeMenuPanel,
    )
    inspector_panels = (EdgeErrorsPanel, EdgeWarningsPanel, EdgeStatsPanel, EdgePathPanel)
    for menu_cls in menu_panels:
        registry._register_class(menu_cls, identity)
    for inspector_cls in inspector_panels:
        registry._register_class(inspector_cls, identity)

    menu_result = registry.get_panels(EdgeMenu)
    inspector_result = registry.get_panels(EdgeInspector)

    assert menu_result, "EdgeMenu must have at least one panel"
    assert inspector_result, "EdgeInspector must have at least one panel"
    assert set(menu_result).isdisjoint(inspector_result), (
        "EdgeMenu and EdgeInspector must show disjoint panel sets — the whole "
        "point of splitting EdgeFocus into inspector/menu halves"
    )
    assert set(menu_result) == set(menu_panels)
    assert set(inspector_result) == set(inspector_panels)


def test_graph_inspector_has_id():
    from haybale_graph_editor.surfaces import GraphInspector

    assert GraphInspector.id == "graph"
    assert surface_by_id("graph") is GraphInspector


def test_pin_menu_has_id():
    from haybale_graph_editor.surfaces import PinMenu

    assert PinMenu.id == "pin"
    assert surface_by_id("pin") is PinMenu


def test_port_inspector_has_id():
    from haybale_graph_editor.surfaces import PortInspector

    assert PortInspector.id == "ports"
    assert surface_by_id("ports") is PortInspector


def test_app_settings_has_id():
    from haywire.barn.builtin.surfaces import AppSettings

    assert AppSettings.id == "app"
    assert surface_by_id("app") is AppSettings


def test_execution_inspector_has_id():
    from haywire.barn.builtin.surfaces import ExecutionInspector

    assert ExecutionInspector.id == "execution"
    assert surface_by_id("execution") is ExecutionInspector


def test_canvas_settings_keeps_canvas_id():
    """The inspector half of CanvasFocus; the menu half moved to GraphContext."""
    from haywire.barn.builtin.surfaces import CanvasSettings

    assert CanvasSettings.id == "canvas"
    assert surface_by_id("canvas") is CanvasSettings


def test_debug_surface_has_id():
    """Log levels and the debug overlay live on their own tab, last in order."""
    from haywire.barn.builtin.surfaces import CanvasSettings, DebugSurface

    assert DebugSurface.id == "debug"
    assert surface_by_id("debug") is DebugSurface
    assert DebugSurface.order > CanvasSettings.order


def test_graph_context_surfaces_have_ids():
    from haybale_graph_editor.surfaces import (
        GraphContext,
        GraphContextBody,
        GraphMoreActions,
        GraphToolBar,
    )

    assert GraphContext.id == "graph-context"
    assert GraphToolBar.id == "graph-toolbar"
    assert GraphContextBody.id == "graph-body"
    assert GraphMoreActions.id == "graph-more"


def test_settings_inspector_has_id():
    from haybale_graph_editor.surfaces import SettingsInspector

    assert SettingsInspector.id == "settings"


def test_selection_menu_has_id():
    from haybale_graph_editor.surfaces import SelectionMenu

    assert SelectionMenu.id == "selection"
    assert surface_by_id("selection") is SelectionMenu


def test_selection_rebuild_menu_has_id():
    from haybale_graph_editor.surfaces import SelectionRebuildMenu

    assert SelectionRebuildMenu.id == "selection-rebuild"
    assert surface_by_id("selection-rebuild") is SelectionRebuildMenu


def _make_ctx_with_edit_stub():
    """Build a stand-in SessionContext-shaped object whose ``data[EditState]``
    yields a stub with bare field values matching the post-migration
    signal_field API (production code reads ``edit.selected_nodes``, not
    ``edit.selected_nodes.value``).

    Bypasses the LibraryStateContainer class-identity check (the test's
    ``EditState`` reference may be a different class object than the one
    ``SelectionMenu.poll`` resolves to after library hot-reload).
    """
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    edit_stub = SimpleNamespace(
        active_graph=None,
        active_graph_path=None,
        active_node=None,
        active_edge=None,
        active_port=None,
        selected_nodes=set(),
        selected_edges=set(),
        clipboard=None,
    )
    data = MagicMock()
    data.__getitem__.return_value = edit_stub

    return SimpleNamespace(
        active_graph=None,
        active_graph_path=None,
        active_node=None,
        active_edge=None,
        active_port=None,
        selected_nodes=set(),
        selected_edges=set(),
        clipboard=None,
        data=data,
        app=MagicMock(),
        session_id="t",
    ), edit_stub


def test_selection_menu_polls_true_when_nodes_selected():
    from haybale_graph_editor.surfaces import SelectionMenu

    ctx, edit_stub = _make_ctx_with_edit_stub()
    assert SelectionMenu.poll(ctx) is False  # nothing selected

    edit_stub.selected_nodes = {"node-1"}
    assert SelectionMenu.poll(ctx) is True


def test_selection_menu_polls_true_when_edges_selected():
    from haybale_graph_editor.surfaces import SelectionMenu

    ctx, edit_stub = _make_ctx_with_edit_stub()
    edit_stub.selected_edges = {"edge-1"}
    assert SelectionMenu.poll(ctx) is True
