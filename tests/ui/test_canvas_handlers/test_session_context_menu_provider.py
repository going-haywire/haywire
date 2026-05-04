"""
Tests for SessionContextMenuProvider.

Verifies that the provider:
- Updates SessionContext.context_menu_trigger before drawing panels
- Calls poll() on registered panels and draws only those returning True
- Clears context_menu_trigger and drains popup metadata when the popup
  close callback is invoked
"""

from unittest.mock import MagicMock, patch

from haybale_studio.focuses import EdgeFocus, NodeFocus
from haywire.ui.context import SessionContext
from haywire.ui.graph_canvas.handlers.context_menu import SessionContextMenuProvider
from haywire.ui.graph_canvas.handlers.context_menu_actions import (
    EdgeContextActions,
    NodeContextActions,
)
from haywire.ui.panel import Panel
from haywire.ui.panel.decorator import panel
from haywire.ui.panel.registry import PanelRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FakeApp:
    workspace_root = "/tmp"
    library_service = None


def make_context(session=None) -> SessionContext:
    ctx = SessionContext(session_id="test-session", app=FakeApp())
    ctx.session = session or MagicMock()
    return ctx


def make_provider(ctx: SessionContext, registry: PanelRegistry, on_emit_event=None):
    """Build a SessionContextMenuProvider with a patched Popup class."""
    popup_container = MagicMock()
    popup = MagicMock()
    popup.__enter__ = MagicMock(return_value=popup_container)
    popup.__exit__ = MagicMock(return_value=False)
    patcher = patch(
        "haywire.ui.graph_canvas.handlers.context_menu.Popup",
        return_value=popup,
    )
    patcher.start()
    provider = SessionContextMenuProvider(
        context=ctx,
        session=ctx.session,
        panel_registry=registry,
        on_emit_event=on_emit_event,
    )
    return provider, popup, patcher


# ---------------------------------------------------------------------------
# Context trigger tests
# ---------------------------------------------------------------------------


def test_on_node_context_sets_trigger_to_node():
    ctx = make_context()
    registry = PanelRegistry()
    provider, popup, _ = make_provider(ctx, registry)

    provider.on_node_context((10, 20), "node-1")

    assert ctx.context_menu_trigger.value == "node"


def test_on_edge_context_sets_trigger_to_edge():
    ctx = make_context()
    registry = PanelRegistry()
    provider, popup, _ = make_provider(ctx, registry)

    provider.on_edge_context((10, 20), "edge-1", MagicMock(), MagicMock())

    assert ctx.context_menu_trigger.value == "edge"


def test_on_canvas_context_sets_trigger_to_canvas():
    ctx = make_context()
    registry = PanelRegistry()
    provider, popup, _ = make_provider(ctx, registry)

    provider.on_canvas_context((10, 20), (5, 5))

    assert ctx.context_menu_trigger.value == "canvas"


def test_on_selection_context_sets_trigger_to_selection():
    ctx = make_context()
    registry = PanelRegistry()
    provider, popup, _ = make_provider(ctx, registry)

    provider.on_selection_context((10, 20), ["n1"], ["e1"])

    assert ctx.context_menu_trigger.value == "selection"


# ---------------------------------------------------------------------------
# Panel poll / draw
# ---------------------------------------------------------------------------


def test_panels_that_return_false_from_poll_are_not_drawn():
    ctx = make_context()
    registry = PanelRegistry()

    drawn = []

    @panel(
        action=NodeContextActions,
        focus=NodeFocus,
        label="Always False",
        registry_id="always_false_panel",
    )
    class AlwaysFalsePanel(Panel):
        @classmethod
        def poll(cls, context):
            return False

        def draw(self, ctx, layout, actions):
            drawn.append("AlwaysFalsePanel")

    registry._register_class(AlwaysFalsePanel)
    provider, _, _ = make_provider(ctx, registry)

    provider.on_node_context((10, 20), "node-1")

    assert drawn == []


def test_panels_that_return_true_from_poll_are_drawn():
    ctx = make_context()
    registry = PanelRegistry()

    drawn = []

    @panel(
        action=NodeContextActions,
        focus=NodeFocus,
        label="Always True",
        registry_id="always_true_panel",
    )
    class AlwaysTruePanel(Panel):
        @classmethod
        def poll(cls, context):
            return True

        def draw(self, ctx, layout, actions):
            drawn.append("AlwaysTruePanel")

    registry._register_class(AlwaysTruePanel)
    provider, _, _ = make_provider(ctx, registry)

    provider.on_node_context((10, 20), "node-1")

    assert "AlwaysTruePanel" in drawn


def test_panels_for_wrong_focus_are_not_drawn():
    ctx = make_context()
    registry = PanelRegistry()

    drawn = []

    @panel(
        action=EdgeContextActions,
        focus=EdgeFocus,
        label="Edge Only",
        registry_id="edge_only_panel",
    )
    class EdgeOnlyPanel(Panel):
        @classmethod
        def poll(cls, context):
            return True

        def draw(self, ctx, layout, actions):
            drawn.append("EdgeOnlyPanel")

    registry._register_class(EdgeOnlyPanel)
    provider, _, _ = make_provider(ctx, registry)

    # Trigger node context — should NOT draw edge panel (different focus)
    provider.on_node_context((10, 20), "node-1")

    assert drawn == []


# ---------------------------------------------------------------------------
# Close callback: trigger cleared + metadata drained
# ---------------------------------------------------------------------------


def test_close_callback_clears_context_menu_trigger():
    session = MagicMock()
    ctx = make_context(session=session)
    registry = PanelRegistry()
    provider, popup, _ = make_provider(ctx, registry)

    provider.on_node_context((10, 20), "node-1")
    assert ctx.context_menu_trigger.value == "node"

    # Simulate popup close — provider must register a close callback on popup
    close_cb = popup.on_close.call_args[0][0]
    close_cb()

    assert ctx.context_menu_trigger.value is None
