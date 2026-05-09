"""Tests for SessionContext."""

from haywire.core.state import LibraryStateContainer
from haywire.core.session.context import SessionContext


class FakeApp:
    """Minimal stand-in for IProjectState."""

    workspace_root = "/tmp"
    library_service = None
    library_state_container = LibraryStateContainer()


def test_theme_keys_default_to_none():
    ctx = SessionContext(session_id="test-123", app=FakeApp())
    assert ctx.active_workbench_theme_key.value is None
    assert ctx.active_node_theme_key.value is None


def test_theme_keys_can_be_set():
    ctx = SessionContext(session_id="test-123", app=FakeApp())
    ctx.active_workbench_theme_key.value = "core:theme:workbench:haywire-dark"
    assert ctx.active_workbench_theme_key.value == "core:theme:workbench:haywire-dark"


def test_editor_cluster_fields_are_not_on_session_context():
    """Regression guard for v1.2 C5.

    The 8 graph-editor fields moved from SessionContext to
    ``haybale_studio.state.edit_state.EditState``. They must not be
    declared on ``SessionContext`` — neither at the class level (where
    a ``reactive_field`` descriptor would surface) nor on instances
    (where the per-instance Reactive container would live).

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
