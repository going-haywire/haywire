"""
Tests for SessionContextMenuProvider.

Verifies that the provider:
- Calls poll() on registered panels and draws only those returning True
- Clears active_port/active_edge when the popup close callback is invoked
"""

import importlib
from unittest.mock import MagicMock, patch

from haywire.core.library.identity import LibraryIdentity
from haywire.core.state import LibraryStateContainer, LibraryStateRegistry
from haywire.core.session.context import SessionContext
from haywire.ui.panel import BasePanel
from haywire.ui.panel.decorator import panel
from haywire.ui.panel.registry import PanelRegistry

_CONTEXT_MENU_MODULE = "haybale_studio.editors.graph_canvas.handlers.context_menu"


def _current_context_menu():
    """Return the live context_menu module — survives library hot-reloads.

    Top-of-file imports become stale after `importlib.reload` swaps a new
    module object into sys.modules. Tests must always read class references
    and patch targets from the *current* module.
    """
    return importlib.import_module(_CONTEXT_MENU_MODULE)


def _current_focuses():
    return importlib.import_module("haybale_studio.focuses")


def _current_actions():
    return importlib.import_module("haybale_studio.editors.graph_canvas.handlers.context_menu_actions")


_FAKE_LIBRARY_IDENTITY = LibraryIdentity(
    label="fake",
    version="0.1",
    description="test",
    url="",
    help_url="",
    author="",
    author_url="",
    folder_path="/tmp/fake",
    module_name="fake",
    id="fake",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FakeApp:
    workspace_root = "/tmp"
    library_service = None

    def __init__(self) -> None:
        # Per-instance container so the EditState registration in
        # make_context() doesn't bleed across tests.
        self.library_state_container = LibraryStateContainer(LibraryStateRegistry())


def make_context(register_edit_state, session=None) -> tuple[SessionContext, type]:
    """Build a SessionContext with EditState registered for one session.

    Returns ``(ctx, EditState)`` so callers can resolve ``ctx.data[EditState]``
    against the same class reference the container saw (survives library
    hot-reloads).
    """
    app = FakeApp()
    sid = "test-session"
    EditStateCls = register_edit_state(app.library_state_container, sid)

    ctx = SessionContext(session_id=sid, app=app)
    ctx.session = session or MagicMock()
    return ctx, EditStateCls


def make_provider(ctx: SessionContext, registry: PanelRegistry, on_emit_event=None):
    """Build a SessionContextMenuProvider with a patched Popup class.

    Resolves SessionContextMenuProvider from the live module (post-any-reload)
    — top-of-file imports become stale once the library system reloads
    context_menu via importlib.reload.

    Popup is patched on the base module because SessionContextMenuProvider now
    inherits _open_menu (and the Popup instantiation) from BaseContextMenuProvider.
    """
    cm = _current_context_menu()
    base_module = importlib.import_module("haybale_studio.editors._context_menu_base")
    popup_container = MagicMock()
    popup = MagicMock()
    popup.__enter__ = MagicMock(return_value=popup_container)
    popup.__exit__ = MagicMock(return_value=False)
    patcher = patch.object(base_module, "Popup", return_value=popup)
    patcher.start()
    provider = cm.SessionContextMenuProvider(
        context=ctx,
        session=ctx.session,
        panel_registry=registry,
        on_emit_event=on_emit_event,
    )
    return provider, popup, patcher


# ---------------------------------------------------------------------------
# Panel poll / draw
# ---------------------------------------------------------------------------


def test_panels_that_return_false_from_poll_are_not_drawn(register_edit_state):
    ctx, _ = make_context(register_edit_state)
    registry = PanelRegistry()
    actions = _current_actions()
    focuses = _current_focuses()

    drawn = []

    @panel(
        action=actions.NodeContextActions,
        focus=focuses.NodeFocus,
        label="Always False",
        registry_id="always_false_panel",
    )
    class AlwaysFalsePanel(BasePanel):
        @classmethod
        def poll(cls, context):
            return False

        def draw(self, ctx, layout, actions):
            drawn.append("AlwaysFalsePanel")

    registry._register_class(AlwaysFalsePanel, _FAKE_LIBRARY_IDENTITY)
    provider, _, _ = make_provider(ctx, registry)

    provider.on_node_context((10, 20), "node-1")

    assert drawn == []


def test_panels_that_return_true_from_poll_are_drawn(register_edit_state):
    ctx, _ = make_context(register_edit_state)
    registry = PanelRegistry()
    actions = _current_actions()
    focuses = _current_focuses()

    drawn = []

    @panel(
        action=actions.NodeContextActions,
        focus=focuses.NodeFocus,
        label="Always True",
        registry_id="always_true_panel",
    )
    class AlwaysTruePanel(BasePanel):
        @classmethod
        def poll(cls, context):
            return True

        def draw(self, ctx, layout, actions):
            drawn.append("AlwaysTruePanel")

    registry._register_class(AlwaysTruePanel, _FAKE_LIBRARY_IDENTITY)
    provider, _, _ = make_provider(ctx, registry)

    provider.on_node_context((10, 20), "node-1")

    assert "AlwaysTruePanel" in drawn


def test_panels_for_wrong_focus_are_not_drawn(register_edit_state):
    ctx, _ = make_context(register_edit_state)
    registry = PanelRegistry()
    actions = _current_actions()
    focuses = _current_focuses()

    drawn = []

    @panel(
        action=actions.EdgeContextActions,
        focus=focuses.EdgeFocus,
        label="Edge Only",
        registry_id="edge_only_panel",
    )
    class EdgeOnlyPanel(BasePanel):
        @classmethod
        def poll(cls, context):
            return True

        def draw(self, ctx, layout, actions):
            drawn.append("EdgeOnlyPanel")

    registry._register_class(EdgeOnlyPanel, _FAKE_LIBRARY_IDENTITY)
    provider, _, _ = make_provider(ctx, registry)

    # Trigger node context — should NOT draw edge panel (different focus)
    provider.on_node_context((10, 20), "node-1")

    assert drawn == []


# ---------------------------------------------------------------------------
# Close callback: active_port / active_edge cleared
# ---------------------------------------------------------------------------


def test_close_callback_clears_active_port_and_edge(register_edit_state):
    session = MagicMock()
    ctx, EditStateCls = make_context(register_edit_state, session=session)
    edit = ctx.data[EditStateCls]
    edit.active_port.value = MagicMock()
    edit.active_edge.value = MagicMock()
    registry = PanelRegistry()
    provider, popup, _ = make_provider(ctx, registry)

    provider.on_node_context((10, 20), "node-1")

    # Simulate popup close — provider must register a close callback on popup
    close_cb = popup.on_close.call_args[0][0]
    close_cb()

    assert edit.active_port.value is None
    assert edit.active_edge.value is None
