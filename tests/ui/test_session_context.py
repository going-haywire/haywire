"""Tests for SessionContext."""

from haywire.ui.context import SessionContext


class FakeApp:
    """Minimal stand-in for IProjectState."""

    workspace_root = "/tmp"
    library_service = None


def test_theme_keys_default_to_none():
    ctx = SessionContext(session_id="test-123", app=FakeApp())
    assert ctx.active_workbench_theme_key.value is None
    assert ctx.active_node_theme_key.value is None


def test_theme_keys_can_be_set():
    ctx = SessionContext(session_id="test-123", app=FakeApp())
    ctx.active_workbench_theme_key.value = "core:theme:workbench:haywire-dark"
    assert ctx.active_workbench_theme_key.value == "core:theme:workbench:haywire-dark"
