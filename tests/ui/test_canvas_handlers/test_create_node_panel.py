"""
Tests for CreateNodePanel (context_menu / canvas scope).

Verifies:
- Panel is registered with editor='context_menu', scope='canvas'
- poll() always returns True (canvas menu is always available)
- draw() invokes NodeMenuBuilder using ctx.app.node_factory
- on_node_selected wraps the key in NodeCreateRequestEvent
"""

import sys
from types import SimpleNamespace

from unittest.mock import MagicMock, patch

from haywire.ui.panel.base import BasePanel, PanelLayout
from haywire.ui.context import SessionContext
from haywire.ui.graph_canvas.event_definitions import NodeCreateRequestEvent

from haybale_testing.panels.test_create_node_panel import TestCreateNodePanel as CreateNodePanel

# The library system may import the panel module under a different sys.modules key
# than a direct `import haybale_testing.panels.test_create_node_panel`.  Resolve
# the *defining* module via the class so the mock always targets the correct dict.
_PANEL_MODULE = sys.modules[CreateNodePanel.__module__]


class FakeApp:
    workspace_root = "/tmp"
    library_service = None
    node_factory = None


def make_context() -> SessionContext:
    ctx = SessionContext(session_id="test", app=FakeApp())
    ctx.session = MagicMock()
    return ctx


# ---------------------------------------------------------------------------
# Registration metadata
# ---------------------------------------------------------------------------


def test_create_node_panel_has_context_menu_editor():
    assert CreateNodePanel.class_identity.editor_keys == ["test_inspector"]


def test_create_node_panel_has_canvas_scope():
    assert "test_canvas" in CreateNodePanel.class_identity.scopes


def test_create_node_panel_is_base_panel_subclass():
    assert issubclass(CreateNodePanel, BasePanel)


# ---------------------------------------------------------------------------
# poll()
# ---------------------------------------------------------------------------


def test_create_node_panel_poll_always_true():
    ctx = make_context()
    assert CreateNodePanel.poll(ctx) is True


def test_create_node_panel_poll_true_when_node_selected():
    ctx = make_context()
    ctx.active_node = MagicMock()
    assert CreateNodePanel.poll(ctx) is True


# ---------------------------------------------------------------------------
# draw() — calls NodeMenuBuilder
# ---------------------------------------------------------------------------


def test_create_node_panel_draw_calls_node_menu_builder(monkeypatch):
    ctx = make_context()
    ctx.app.node_factory = MagicMock()

    layout = MagicMock(spec=PanelLayout)
    builder_mock = MagicMock()

    with patch.object(
        _PANEL_MODULE,
        "NodeMenuBuilder",
        return_value=builder_mock,
    ):
        panel = CreateNodePanel()
        panel.draw(ctx, layout)

    builder_mock.create_node_menu.assert_called_once()


def test_on_node_selected_emits_node_create_request_event():
    """Selecting a node key must emit a NodeCreateRequestEvent, not the raw string."""
    ctx = make_context()
    ctx.app.node_factory = MagicMock()
    ctx.metadata["canvas_position"] = {"x": 42.0, "y": 99.0}

    emitted = []
    ctx.metadata["on_emit_event"] = emitted.append

    layout = MagicMock(spec=PanelLayout)
    builder_instance = MagicMock()
    captured_callback = {}

    def fake_create_node_menu(on_node_selected, **kwargs):
        captured_callback["fn"] = on_node_selected

    builder_instance.create_node_menu.side_effect = fake_create_node_menu

    with patch.object(
        _PANEL_MODULE,
        "NodeMenuBuilder",
        return_value=builder_instance,
    ):
        CreateNodePanel().draw(ctx, layout)

    captured_callback["fn"](SimpleNamespace(identity=SimpleNamespace(registry_key="my_lib/MyNode")))

    assert len(emitted) == 1
    event = emitted[0]
    assert isinstance(event, NodeCreateRequestEvent)
    assert event.registryKey == "my_lib/MyNode"
    assert event.position == {"x": 42.0, "y": 99.0}
