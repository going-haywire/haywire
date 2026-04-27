"""Tests for SessionContext."""

from haywire.ui.context import SessionContext


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


# ---------------------------------------------------------------------------
# context_menu_trigger
# ---------------------------------------------------------------------------


def test_context_menu_trigger_defaults_to_none():
    ctx = SessionContext(session_id="test-123", app=FakeApp())
    assert ctx.context_menu_trigger is None


def test_context_menu_trigger_can_be_set_to_node():
    ctx = SessionContext(session_id="test-123", app=FakeApp())
    ctx.context_menu_trigger = "node"
    assert ctx.context_menu_trigger == "node"


def test_context_menu_trigger_can_be_cleared():
    ctx = SessionContext(session_id="test-123", app=FakeApp())
    ctx.context_menu_trigger = "edge"
    ctx.context_menu_trigger = None
    assert ctx.context_menu_trigger is None
