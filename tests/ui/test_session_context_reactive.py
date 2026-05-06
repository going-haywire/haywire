# tests/ui/test_session_context_reactive.py
"""SessionContext fields are reactive.

Class access yields ReactivePath; instance access yields Reactive[T].

After v1.2 C5, the editor-cluster fields (``active_node``, ``active_edge``,
``active_graph``, ``active_port``, ``selected_nodes``, ``selected_edges``,
``active_graph_path``, ``clipboard``) live on
``haybale_studio.state.edit_state.EditState`` and are no longer declared
on ``SessionContext``. The descriptor-mechanism tests below use
``active_file`` — a remaining session-level reactive field — as the
representative example.
"""

from unittest.mock import MagicMock

from haywire.ui.context import SessionContext
from haywire.ui.reactive import Reactive, ReactivePath


def _make_ctx() -> SessionContext:
    """Build a SessionContext with mock dependencies."""
    return SessionContext(session_id="test", app=MagicMock())


def test_active_file_class_access_is_reactive_path():
    p = SessionContext.active_file
    assert isinstance(p, ReactivePath)
    assert p.owner is SessionContext
    assert p.attr == "active_file"


def test_active_file_instance_access_is_reactive():
    ctx = _make_ctx()
    assert isinstance(ctx.active_file, Reactive)
    assert ctx.active_file.value is None


def test_active_file_write_through_value():
    ctx = _make_ctx()
    sentinel = MagicMock(name="file")
    ctx.active_file.value = sentinel
    assert ctx.active_file.value is sentinel


def test_each_instance_has_independent_reactives():
    a = _make_ctx()
    b = _make_ctx()
    a.active_file.value = MagicMock()
    assert a.active_file.value is not None
    assert b.active_file.value is None


def test_all_documented_reactive_fields_are_present():
    ctx = _make_ctx()
    # The editor-cluster fields (active_node, active_edge, active_graph,
    # active_port, selected_nodes, selected_edges, active_graph_path,
    # clipboard) moved to EditState in v1.2 C5; the remaining
    # session-level fields stay on SessionContext.
    expected_fields = {
        "active_library",
        "active_component",
        "active_file",
        "active_workbench_theme_key",
        "active_node_theme_key",
    }
    for name in expected_fields:
        attr = getattr(ctx, name)
        assert isinstance(attr, Reactive), f"{name} is not Reactive: {type(attr)}"
