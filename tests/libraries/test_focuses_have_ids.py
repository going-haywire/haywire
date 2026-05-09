# tests/libraries/test_focuses_have_ids.py
"""Every Focus subclass in haybale-core and haybale-studio must declare an id."""

from haywire.ui.panel.focus import focus_by_id


def test_node_focus_has_id():
    # Importing the module triggers Focus.__init_subclass__.
    from haybale_studio.focuses import NodeFocus

    assert NodeFocus.id == "node"
    assert focus_by_id("node") is NodeFocus


def test_edge_focus_has_id():
    from haybale_studio.focuses import EdgeFocus

    assert EdgeFocus.id == "edge"
    assert focus_by_id("edge") is EdgeFocus


def test_graph_focus_has_id():
    from haybale_studio.focuses import GraphFocus

    assert GraphFocus.id == "graph"
    assert focus_by_id("graph") is GraphFocus


def test_port_focus_has_id():
    from haybale_studio.focuses import PortFocus

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
    from haybale_studio.focuses import SettingsFocus

    assert SettingsFocus.id == "settings"


def test_selection_focus_has_id():
    from haybale_studio.focuses import SelectionFocus

    assert SelectionFocus.id == "selection"
    assert focus_by_id("selection") is SelectionFocus


def _make_ctx_with_edit_stub():
    """Build a stand-in SessionContext-shaped object whose ``data[EditState]``
    yields a stub with real Reactive fields.

    Bypasses the LibraryStateContainer class-identity check (the test's
    ``EditState`` reference may be a different class object than the one
    ``SelectionFocus.available`` resolves to after library hot-reload).
    """
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from haywire.core.session.reactive import Reactive

    edit_stub = SimpleNamespace(
        active_graph=Reactive(None),
        active_graph_path=Reactive(None),
        active_node=Reactive(None),
        active_edge=Reactive(None),
        active_port=Reactive(None),
        selected_nodes=Reactive(set()),
        selected_edges=Reactive(set()),
        clipboard=Reactive(None),
    )
    data = MagicMock()
    data.__getitem__.return_value = edit_stub

    return SimpleNamespace(
        active_graph=Reactive(None),
        active_graph_path=Reactive(None),
        active_node=Reactive(None),
        active_edge=Reactive(None),
        active_port=Reactive(None),
        selected_nodes=Reactive(set()),
        selected_edges=Reactive(set()),
        clipboard=Reactive(None),
        data=data,
        app=MagicMock(),
        session_id="t",
    ), edit_stub


def test_selection_focus_available_when_nodes_selected():
    from haybale_studio.focuses import SelectionFocus

    ctx, edit_stub = _make_ctx_with_edit_stub()
    assert SelectionFocus.available(ctx) is False  # nothing selected

    edit_stub.selected_nodes.value = {"node-1"}
    assert SelectionFocus.available(ctx) is True


def test_selection_focus_available_when_edges_selected():
    from haybale_studio.focuses import SelectionFocus

    ctx, edit_stub = _make_ctx_with_edit_stub()
    edit_stub.selected_edges.value = {"edge-1"}
    assert SelectionFocus.available(ctx) is True
