"""
Tests for the haybale-testing TestCreateNodePanel.

Verifies:
- Panel is registered with action_protocol=TestCanvasContextActions, focus=TestCanvasFocus
- poll() always returns True (canvas menu is always available)
- draw() invokes NodeMenuBuilder using ctx.app.node_factory
- on_node_selected calls actions.test_create_node_at_click with the registry key
"""

import sys
from types import SimpleNamespace

from unittest.mock import MagicMock, patch

from haywire.core.state import LibraryStateContainer, LibraryStateRegistry
from haywire.core.session.context import SessionContext
from haywire.ui.panel import BasePanel
from haywire.ui.panel.layout import PanelLayout

from haybale_testing.test_actions import TestCanvasContextActions
from haybale_testing.test_focuses import TestCanvasFocus
from haybale_testing.panels.test_create_node_panel import TestCreateNodePanel as CreateNodePanel

_PANEL_MODULE = sys.modules[CreateNodePanel.__module__]


def _make_app(container: LibraryStateContainer) -> object:
    app = MagicMock()
    app.workspace_root = "/tmp"
    app.library_service = None
    app.node_factory = None
    app.library_state_container = container
    return app


def make_context(register_edit_state) -> tuple[SessionContext, type]:
    from tests.conftest import attach_stub_session

    container = LibraryStateContainer(LibraryStateRegistry())
    sid = "test"
    EditStateCls = register_edit_state(container, sid)
    ctx = attach_stub_session(SessionContext(session_id=sid, app=_make_app(container)))
    return ctx, EditStateCls


# ---------------------------------------------------------------------------
# Registration metadata
# ---------------------------------------------------------------------------


def test_create_node_panel_action_protocol_is_test_canvas_context_actions():
    assert CreateNodePanel.class_identity.action_protocol is TestCanvasContextActions


def test_create_node_panel_focus_is_test_canvas_focus():
    assert CreateNodePanel.class_identity.focus is TestCanvasFocus


def test_create_node_panel_is_panel_subclass():
    assert issubclass(CreateNodePanel, BasePanel)


# ---------------------------------------------------------------------------
# poll()
# ---------------------------------------------------------------------------


def test_create_node_panel_poll_always_true(register_edit_state):
    ctx, _ = make_context(register_edit_state)
    assert CreateNodePanel.poll(ctx) is True


def test_create_node_panel_poll_true_when_node_selected(register_edit_state):
    ctx, EditStateCls = make_context(register_edit_state)
    ctx.data[EditStateCls].active_node = MagicMock()
    assert CreateNodePanel.poll(ctx) is True


# ---------------------------------------------------------------------------
# draw() — calls NodeMenuBuilder
# ---------------------------------------------------------------------------


def test_create_node_panel_draw_calls_node_menu_builder(register_edit_state):
    ctx, _ = make_context(register_edit_state)
    ctx.app.node_factory = MagicMock()

    layout = MagicMock(spec=PanelLayout)
    actions = MagicMock(spec=TestCanvasContextActions)
    builder_mock = MagicMock()

    with patch.object(_PANEL_MODULE, "NodeMenuBuilder", return_value=builder_mock):
        instance = CreateNodePanel()
        instance.actions = actions  # host injection
        instance.draw(ctx, layout)

    builder_mock.create_node_menu.assert_called_once()


def test_on_node_selected_calls_test_create_node_at_click(register_edit_state):
    """Selecting a node info must call actions.test_create_node_at_click with the registry key."""
    ctx, _ = make_context(register_edit_state)
    ctx.app.node_factory = MagicMock()

    layout = MagicMock(spec=PanelLayout)
    actions = MagicMock(spec=TestCanvasContextActions)
    builder_instance = MagicMock()
    captured_callback = {}

    def fake_constructor(node_factory, on_node_selected, **kwargs):
        captured_callback["fn"] = on_node_selected
        return builder_instance

    with patch.object(_PANEL_MODULE, "NodeMenuBuilder", side_effect=fake_constructor):
        instance = CreateNodePanel()
        instance.actions = actions  # host injection
        instance.draw(ctx, layout)

    captured_callback["fn"](SimpleNamespace(identity=SimpleNamespace(registry_key="my_lib/MyNode")))

    actions.test_create_node_at_click.assert_called_once_with("my_lib/MyNode")
