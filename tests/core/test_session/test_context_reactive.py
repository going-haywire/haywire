# tests/core/test_session/test_context_reactive.py
"""SessionContext fields are signal_field descriptors.

Class access yields the synthetic Signal subclass (used as a subscription
key on the per-session bus); instance access yields the stored value.
Writes auto-emit the synthetic signal via the descriptor's __set__.

After v1.2 C5, the editor-cluster fields (``active_node``, ``active_edge``,
``active_graph``, ``active_port``, ``selected_nodes``, ``selected_edges``,
``active_graph_path``, ``clipboard``) live on
``haybale_studio.state.edit_state.EditState`` and are no longer declared
on ``SessionContext``. The descriptor-mechanism tests below use
``active_file`` — a remaining session-level signal field — as the
representative example.
"""

from unittest.mock import MagicMock

from haywire.core.session.context import SessionContext
from haywire.core.session.signals import Signal


def _make_ctx() -> SessionContext:
    """Build a SessionContext with mock dependencies + stubbed session."""
    from tests.conftest import attach_stub_session

    return attach_stub_session(SessionContext(session_id="test", app=MagicMock()))


def test_active_file_class_access_returns_synthetic_signal_class():
    cls = SessionContext.active_file
    assert isinstance(cls, type)
    assert issubclass(cls, Signal)
    # The synthetic class is named after the field.
    assert cls.__name__ == "active_file"


def test_active_file_instance_access_returns_stored_value():
    ctx = _make_ctx()
    assert ctx.active_file is None


def test_active_file_write_stores_and_emits():
    ctx = _make_ctx()
    sentinel = MagicMock(name="file")
    ctx.active_file = sentinel
    assert ctx.active_file is sentinel
    # Write went through the descriptor; the descriptor emitted the
    # synthetic signal via session.publish.
    ctx.session.publish.assert_called_once()
    emitted = ctx.session.publish.call_args.args[0]
    assert isinstance(emitted, SessionContext.active_file)


def test_each_instance_has_independent_storage():
    a = _make_ctx()
    b = _make_ctx()
    a.active_file = MagicMock()
    assert a.active_file is not None
    assert b.active_file is None


def test_all_documented_signal_fields_are_present():
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
        # Class-level access returns the synthetic Signal subclass.
        cls_attr = getattr(SessionContext, name)
        assert isinstance(cls_attr, type) and issubclass(cls_attr, Signal), (
            f"{name} class access is not a Signal subclass: {cls_attr!r}"
        )
        # Instance-level access returns the stored value (default None
        # here since nothing wrote to the field).
        assert getattr(ctx, name) is None, f"{name} default is not None: {getattr(ctx, name)!r}"
