# tests/libraries/test_focuses_have_ids.py
"""Every Focus subclass in haybale-core and haybale-studio must declare an id."""

from haywire.ui.panel.focus import focus_by_id


def test_node_focus_has_id():
    # Importing the module triggers Focus.__init_subclass__.
    from haybale_graph_editor.focuses import NodeFocus

    assert NodeFocus.id == "node"
    assert focus_by_id("node") is NodeFocus


def test_edge_focus_has_id():
    from haybale_graph_editor.focuses import EdgeFocus

    assert EdgeFocus.id == "edge"
    assert focus_by_id("edge") is EdgeFocus


def test_graph_focus_has_id():
    from haybale_graph_editor.focuses import GraphFocus

    assert GraphFocus.id == "graph"
    assert focus_by_id("graph") is GraphFocus


def test_port_focus_has_id():
    from haybale_graph_editor.focuses import PortFocus

    assert PortFocus.id == "port"
    assert focus_by_id("port") is PortFocus


def test_app_focus_has_id():
    from haybale_studio.focuses import AppFocus

    assert AppFocus.id == "app"
    assert focus_by_id("app") is AppFocus


def test_execution_focus_has_id():
    from haybale_studio.focuses import ExecutionFocus

    assert ExecutionFocus.id == "execution"
    assert focus_by_id("execution") is ExecutionFocus


def test_canvas_focus_has_id():
    from haybale_studio.focuses import CanvasFocus

    assert CanvasFocus.id == "canvas"


def test_settings_focus_has_id():
    from haybale_graph_editor.focuses import SettingsFocus

    assert SettingsFocus.id == "settings"


def test_selection_focus_has_id():
    from haybale_graph_editor.focuses import SelectionFocus

    assert SelectionFocus.id == "selection"
    assert focus_by_id("selection") is SelectionFocus


def _make_ctx_with_edit_stub():
    """Build a stand-in SessionContext-shaped object whose ``data[EditState]``
    yields a stub with bare field values matching the post-migration
    signal_field API (production code reads ``edit.selected_nodes``, not
    ``edit.selected_nodes.value``).

    Bypasses the LibraryStateContainer class-identity check (the test's
    ``EditState`` reference may be a different class object than the one
    ``SelectionFocus.available`` resolves to after library hot-reload).
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


def test_selection_focus_available_when_nodes_selected():
    from haybale_graph_editor.focuses import SelectionFocus

    ctx, edit_stub = _make_ctx_with_edit_stub()
    assert SelectionFocus.available(ctx) is False  # nothing selected

    edit_stub.selected_nodes = {"node-1"}
    assert SelectionFocus.available(ctx) is True


def test_selection_focus_available_when_edges_selected():
    from haybale_graph_editor.focuses import SelectionFocus

    ctx, edit_stub = _make_ctx_with_edit_stub()
    edit_stub.selected_edges = {"edge-1"}
    assert SelectionFocus.available(ctx) is True
