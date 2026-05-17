"""Tests for SessionContext."""

from haywire.core.state import LibraryStateContainer, LibraryStateRegistry
from haywire.core.session.context import SessionContext


class FakeApp:
    """Minimal stand-in for IProjectState."""

    workspace_root = "/tmp"
    library_service = None
    library_state_container = LibraryStateContainer(LibraryStateRegistry())


def test_theme_keys_default_to_none():
    ctx = SessionContext(session_id="test-123", app=FakeApp())
    assert ctx.active_workbench_theme_key is None
    assert ctx.active_node_theme_key is None


def test_theme_keys_can_be_set():
    ctx = SessionContext(session_id="test-123", app=FakeApp())
    # SessionContext._signal_emit forwards to self.session.publish; the
    # write goes through the signal_field descriptor which calls _signal_emit
    # via instance.session — wire a minimal stub so the emit succeeds.
    ctx.session = type("S", (), {"publish": staticmethod(lambda _s: None)})()
    ctx.active_workbench_theme_key = "core:theme:workbench:haywire-dark"
    assert ctx.active_workbench_theme_key == "core:theme:workbench:haywire-dark"


def test_editor_cluster_fields_are_not_on_session_context():
    """Regression guard for v1.2 C5.

    The 8 graph-editor fields moved from SessionContext to
    ``haybale_graph_editor.state.edit_state.EditState``. They must not be
    declared on ``SessionContext`` — neither at the class level (where
    a ``signal_field`` descriptor would surface) nor on instances
    (where the per-instance storage would live).

    This test catches a future regression where someone re-adds one of
    the 8 fields to SessionContext instead of putting it on EditState.
    """
    removed_fields = (
        "active_graph",
        "active_graph_path",
        "active_node",
        "active_edge",
        "active_port",
        "selected_nodes",
        "selected_edges",
        "clipboard",
    )
    ctx = SessionContext(session_id="test-123", app=FakeApp())
    for name in removed_fields:
        assert not hasattr(SessionContext, name), (
            f"SessionContext should not declare {name!r} (moved to EditState in v1.2 C5)"
        )
        assert not hasattr(ctx, name), (
            f"SessionContext instance should not have {name!r} (moved to EditState in v1.2 C5)"
        )
