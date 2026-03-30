"""Tests for SessionContext."""

from haywire.ui.context import SessionContext, InteractionMode


class FakeApp:
    """Minimal stand-in for IProjectState."""

    workspace_root = "/tmp"
    library_service = None


def test_theme_keys_default_to_none():
    ctx = SessionContext(session_id="test-123", app=FakeApp())
    assert ctx.active_workbench_theme_key is None
    assert ctx.active_node_theme_key is None


def test_theme_keys_can_be_set():
    ctx = SessionContext(session_id="test-123", app=FakeApp())
    ctx.active_workbench_theme_key = "core:theme:workbench:haywire-dark"
    assert ctx.active_workbench_theme_key == "core:theme:workbench:haywire-dark"


def test_interaction_mode_defaults_to_idle():
    ctx = SessionContext(session_id="test-123", app=FakeApp())
    assert ctx.interaction_mode == InteractionMode.IDLE
