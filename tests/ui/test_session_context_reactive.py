# tests/ui/test_session_context_reactive.py
"""SessionContext fields are reactive.

Class access yields ReactivePath; instance access yields Reactive[T].
"""

from unittest.mock import MagicMock

from haywire.ui.context import SessionContext
from haywire.ui.reactive import Reactive, ReactivePath


def _make_ctx() -> SessionContext:
    """Build a SessionContext with mock dependencies."""
    return SessionContext(session_id="test", app=MagicMock())


def test_active_node_class_access_is_reactive_path():
    p = SessionContext.active_node
    assert isinstance(p, ReactivePath)
    assert p.owner is SessionContext
    assert p.attr == "active_node"


def test_active_node_instance_access_is_reactive():
    ctx = _make_ctx()
    assert isinstance(ctx.active_node, Reactive)
    assert ctx.active_node.value is None


def test_active_node_write_through_value():
    ctx = _make_ctx()
    sentinel = MagicMock(name="node_wrapper")
    ctx.active_node.value = sentinel
    assert ctx.active_node.value is sentinel


def test_each_instance_has_independent_reactives():
    a = _make_ctx()
    b = _make_ctx()
    a.active_node.value = MagicMock()
    assert a.active_node.value is not None
    assert b.active_node.value is None


def test_all_documented_reactive_fields_are_present():
    ctx = _make_ctx()
    expected_fields = {
        "active_graph",
        "active_node",
        "active_edge",
        "active_port",
        "selected_nodes",
        "selected_edges",
        "workspace_name",
        "active_library",
        "active_component",
        "active_file",
        "active_graph_path",
        "active_workbench_theme_key",
        "active_node_theme_key",
        "context_menu_trigger",
    }
    for name in expected_fields:
        attr = getattr(ctx, name)
        assert isinstance(attr, Reactive), f"{name} is not Reactive: {type(attr)}"


def test_metadata_is_still_a_plain_dict():
    """metadata stays as a dict for now (Phase 1.5 lifts gesture state to typed fields)."""
    ctx = _make_ctx()
    assert isinstance(ctx.metadata, dict)
    ctx.metadata["k"] = "v"
    assert ctx.metadata["k"] == "v"
