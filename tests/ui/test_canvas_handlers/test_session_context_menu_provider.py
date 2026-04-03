"""
Tests for SessionContextMenuProvider.

Verifies that the provider:
- Updates SessionContext.context_menu_trigger before drawing panels
- Fires CONTEXT_MENU_OPENED via session.notify_context_changed
- Calls poll() on registered panels and draws only those returning True
- Fires CONTEXT_MENU_CLOSED when the popup close callback is invoked
- Clears context_menu_trigger on close
"""

import pytest
from unittest.mock import MagicMock, call, patch
from typing import Optional

from haywire.ui.context import SessionContext
from haywire.ui.context_events import ContextChangeType
from haywire.ui.panel.base import BasePanel
from haywire.ui.panel.decorator import panel
from haywire.ui.panel.registry import PanelRegistry
from haywire.ui.graph_canvas.handlers.context_menu import SessionContextMenuProvider


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

    assert ctx.context_menu_trigger == "node"


def test_on_edge_context_sets_trigger_to_edge():
    ctx = make_context()
    registry = PanelRegistry()
    provider, popup, _ = make_provider(ctx, registry)

    provider.on_edge_context((10, 20), "edge-1", MagicMock(), MagicMock())

    assert ctx.context_menu_trigger == "edge"


def test_on_canvas_context_sets_trigger_to_canvas():
    ctx = make_context()
    registry = PanelRegistry()
    provider, popup, _ = make_provider(ctx, registry)

    provider.on_canvas_context((10, 20), (5, 5))

    assert ctx.context_menu_trigger == "canvas"


def test_on_selection_context_sets_trigger_to_selection():
    ctx = make_context()
    registry = PanelRegistry()
    provider, popup, _ = make_provider(ctx, registry)

    provider.on_selection_context((10, 20), ["n1"], ["e1"])

    assert ctx.context_menu_trigger == "selection"


# ---------------------------------------------------------------------------
# CONTEXT_MENU_OPENED event
# ---------------------------------------------------------------------------


def test_on_node_context_fires_context_menu_opened():
    session = MagicMock()
    ctx = make_context(session=session)
    registry = PanelRegistry()
    provider, _, _ = make_provider(ctx, registry)

    provider.on_node_context((10, 20), "node-1")

    session.notify_context_changed.assert_called_once()
    event = session.notify_context_changed.call_args[0][0]
    assert event.change_type == ContextChangeType.CONTEXT_MENU_OPENED


# ---------------------------------------------------------------------------
# Panel poll / draw
# ---------------------------------------------------------------------------


def test_panels_that_return_false_from_poll_are_not_drawn():
    ctx = make_context()
    registry = PanelRegistry()

    drawn = []

    @panel(registry_id="always_false_panel", editor="context_menu", scope="node")
    class AlwaysFalsePanel(BasePanel):
        @classmethod
        def poll(cls, context):
            return False

        def draw(self, context, layout):
            drawn.append("AlwaysFalsePanel")

    registry._register_class(AlwaysFalsePanel)
    provider, _, _ = make_provider(ctx, registry)

    provider.on_node_context((10, 20), "node-1")

    assert drawn == []


def test_panels_that_return_true_from_poll_are_drawn():
    ctx = make_context()
    registry = PanelRegistry()

    drawn = []

    @panel(registry_id="always_true_panel", editor="context_menu", scope="node")
    class AlwaysTruePanel(BasePanel):
        @classmethod
        def poll(cls, context):
            return True

        def draw(self, context, layout):
            drawn.append("AlwaysTruePanel")

    registry._register_class(AlwaysTruePanel)
    provider, _, _ = make_provider(ctx, registry)

    provider.on_node_context((10, 20), "node-1")

    assert "AlwaysTruePanel" in drawn


def test_panels_for_wrong_scope_are_not_drawn():
    ctx = make_context()
    registry = PanelRegistry()

    drawn = []

    @panel(registry_id="edge_only_panel", editor="context_menu", scope="edge")
    class EdgeOnlyPanel(BasePanel):
        @classmethod
        def poll(cls, context):
            return True

        def draw(self, context, layout):
            drawn.append("EdgeOnlyPanel")

    registry._register_class(EdgeOnlyPanel)
    provider, _, _ = make_provider(ctx, registry)

    # Trigger node context — should NOT draw edge panel
    provider.on_node_context((10, 20), "node-1")

    assert drawn == []


# ---------------------------------------------------------------------------
# CONTEXT_MENU_CLOSED + trigger cleared
# ---------------------------------------------------------------------------


def test_close_callback_clears_context_menu_trigger():
    session = MagicMock()
    ctx = make_context(session=session)
    registry = PanelRegistry()
    provider, popup, _ = make_provider(ctx, registry)

    provider.on_node_context((10, 20), "node-1")
    assert ctx.context_menu_trigger == "node"

    # Simulate popup close — provider must register a close callback on popup
    close_cb = popup.on_close.call_args[0][0]
    close_cb()

    assert ctx.context_menu_trigger is None


def test_close_callback_fires_context_menu_closed():
    session = MagicMock()
    ctx = make_context(session=session)
    registry = PanelRegistry()
    provider, popup, _ = make_provider(ctx, registry)

    provider.on_node_context((10, 20), "node-1")
    session.notify_context_changed.reset_mock()

    close_cb = popup.on_close.call_args[0][0]
    close_cb()

    session.notify_context_changed.assert_called_once()
    event = session.notify_context_changed.call_args[0][0]
    assert event.change_type == ContextChangeType.CONTEXT_MENU_CLOSED


def test_on_emit_event_is_set_on_context_metadata_before_panels_draw():
    """on_emit_event wrapper in context.metadata must delegate to fake_emit."""
    ctx = make_context()
    registry = PanelRegistry()
    fake_emit = MagicMock()

    captured = {}

    @panel(registry_id="capture_emit_panel", editor="context_menu", scope="node")
    class CaptureEmitPanel(BasePanel):
        @classmethod
        def poll(cls, context):
            return True

        def draw(self, context, layout):
            captured["fn"] = context.metadata.get("on_emit_event")

    registry._register_class(CaptureEmitPanel)
    provider, popup, _ = make_provider(ctx, registry, on_emit_event=fake_emit)

    provider.on_node_context((10, 20), "node-1")

    assert "fn" in captured
    sentinel = object()
    captured["fn"](sentinel)
    fake_emit.assert_called_once_with(sentinel)
    popup.close.assert_called_once()


def test_on_emit_event_cleared_from_metadata_on_close():
    """on_emit_event must be removed from context.metadata when popup closes."""
    session = MagicMock()
    ctx = make_context(session=session)
    registry = PanelRegistry()
    fake_emit = MagicMock()
    provider, popup, _ = make_provider(ctx, registry, on_emit_event=fake_emit)

    provider.on_node_context((10, 20), "node-1")
    assert "on_emit_event" in ctx.metadata

    close_cb = popup.on_close.call_args[0][0]
    close_cb()

    assert "on_emit_event" not in ctx.metadata
