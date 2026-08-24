"""
Tests for SessionContextMenuProvider.

Verifies that the provider:
- Gates the surface, then polls its panels and draws only those that apply
- Clears active_port/active_edge when the popup close callback is invoked
- Runs that cleanup even when no popup opens (the gesture still ended)
"""

from typing import Any, cast

import importlib
from unittest.mock import MagicMock, patch

from haywire.core.library.identity import LibraryIdentity
from haywire.core.state import LibraryStateContainer, LibraryStateRegistry
from haywire.core.session.context import SessionContext
from haywire.ui.panel import BasePanel
from haywire.ui.panel.decorator import panel
from haywire.ui.panel.registry import PanelRegistry

_CONTEXT_MENU_MODULE = "haybale_graph_editor.editors.graph_canvas.handlers.context_menu"


def _current_context_menu():
    """Return the live context_menu module — survives library hot-reloads.

    Top-of-file imports become stale after `importlib.reload` swaps a new
    module object into sys.modules. Tests must always read class references
    and patch targets from the *current* module.
    """
    return importlib.import_module(_CONTEXT_MENU_MODULE)


def _current_surfaces():
    return importlib.import_module("haybale_graph_editor.surfaces")


_FAKE_LIBRARY_IDENTITY = LibraryIdentity(
    label="fake",
    version="0.1",
    folder_path="/tmp/fake",
    module_name="fake",
    name="fake",
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

    ctx = SessionContext(session_id=sid, app=cast(Any, app))
    ctx.session = session or MagicMock()
    return ctx, EditStateCls


def make_provider(ctx: SessionContext, registry: PanelRegistry, on_emit_event=None):
    """Build a SessionContextMenuProvider with a patched Popup class.

    Resolves SessionContextMenuProvider from the live module (post-any-reload)
    — top-of-file imports become stale once the library system reloads
    context_menu via importlib.reload.

    Popup is patched on the base module because SessionContextMenuProvider
    inherits _open_menu (and the Popup instantiation) from
    BaseContextMenuProvider. ``popup.content`` has to be usable as a context
    manager: the host renders the tree into it before deciding whether to open.
    """
    cm = _current_context_menu()
    base_module = importlib.import_module("haywire.ui.panel.context_menu_base")
    popup_content = MagicMock()
    popup_content.__enter__ = MagicMock(return_value=popup_content)
    popup_content.__exit__ = MagicMock(return_value=False)
    popup = MagicMock()
    popup.content = popup_content
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
    SelectionMenu = _current_surfaces().SelectionMenu

    drawn = []

    @panel(
        surface=SelectionMenu,
        label="Always False",
        registry_id="always_false_panel",
    )
    class AlwaysFalsePanel(BasePanel):
        actions: Any

        @classmethod
        def poll(cls, context):
            return False

        def draw(self, ctx, layout):
            drawn.append("AlwaysFalsePanel")

    registry._register_class(AlwaysFalsePanel, _FAKE_LIBRARY_IDENTITY)
    provider, _, _ = make_provider(ctx, registry)

    # A non-empty selection so the *surface* gate passes and the panel's own
    # poll() is what decides — otherwise the surface short-circuits first.
    provider.on_selection_context((10, 20), ["n1"], [])

    assert drawn == []


def test_panels_that_return_true_from_poll_are_drawn(register_edit_state):
    ctx, _ = make_context(register_edit_state)
    registry = PanelRegistry()
    SelectionMenu = _current_surfaces().SelectionMenu

    drawn = []

    @panel(
        surface=SelectionMenu,
        label="Always True",
        registry_id="always_true_panel",
    )
    class AlwaysTruePanel(BasePanel):
        actions: Any

        @classmethod
        def poll(cls, context):
            return True

        def draw(self, ctx, layout):
            drawn.append("AlwaysTruePanel")

    registry._register_class(AlwaysTruePanel, _FAKE_LIBRARY_IDENTITY)
    provider, _, _ = make_provider(ctx, registry)

    provider.on_selection_context((10, 20), ["n1"], [])

    assert "AlwaysTruePanel" in drawn


def test_panels_on_another_surface_are_not_drawn(register_edit_state):
    ctx, _ = make_context(register_edit_state)
    registry = PanelRegistry()
    EdgeMenu = _current_surfaces().EdgeMenu

    drawn = []

    @panel(
        surface=EdgeMenu,
        label="Edge Only",
        registry_id="edge_only_panel",
    )
    class EdgeOnlyPanel(BasePanel):
        actions: Any

        @classmethod
        def poll(cls, context):
            return True

        def draw(self, ctx, layout):
            drawn.append("EdgeOnlyPanel")

    registry._register_class(EdgeOnlyPanel, _FAKE_LIBRARY_IDENTITY)
    provider, _, _ = make_provider(ctx, registry)

    # Opening SelectionMenu must not reach a panel on EdgeMenu.
    provider.on_selection_context((10, 20), ["n1"], [])

    assert drawn == []


def test_surface_gate_short_circuits_before_panels_are_queried(register_edit_state):
    """A surface that does not apply costs nothing: no popup, no panel poll."""
    ctx, _ = make_context(register_edit_state)
    SelectionMenu = _current_surfaces().SelectionMenu

    polled = []

    @panel(
        surface=SelectionMenu,
        label="Counts Polls",
        registry_id="counts_polls_panel",
    )
    class CountsPollsPanel(BasePanel):
        actions: Any

        @classmethod
        def poll(cls, context):
            polled.append(1)
            return True

        def draw(self, ctx, layout):
            pass

    registry = PanelRegistry()
    registry._register_class(CountsPollsPanel, _FAKE_LIBRARY_IDENTITY)
    provider, popup, _ = make_provider(ctx, registry)

    # Empty selection: SelectionMenu.poll() is False.
    provider.on_selection_context((10, 20), [], [])

    assert polled == []
    popup.open.assert_not_called()


# ---------------------------------------------------------------------------
# Close callback: active_port / active_edge cleared
# ---------------------------------------------------------------------------


def test_close_callback_clears_active_port_and_edge(register_edit_state):
    session = MagicMock()
    ctx, EditStateCls = make_context(register_edit_state, session=session)
    edit: Any = ctx.data[EditStateCls]
    edit.active_port = MagicMock()
    edit.active_edge = MagicMock()
    SelectionMenu = _current_surfaces().SelectionMenu

    # A visible panel so the popup actually opens and wires on_close.
    @panel(
        surface=SelectionMenu,
        label="Always True",
        registry_id="close_cb_panel",
    )
    class _Panel(BasePanel):
        actions: Any

        @classmethod
        def poll(cls, context):
            return True

        def draw(self, ctx, layout):
            pass

    registry = PanelRegistry()
    registry._register_class(_Panel, _FAKE_LIBRARY_IDENTITY)
    provider, popup, _ = make_provider(ctx, registry)

    provider.on_selection_context((10, 20), ["n1"], [])

    # Simulate popup close — provider must register a close callback on popup
    close_cb = popup.on_close.call_args[0][0]
    close_cb()

    assert edit.active_port is None
    assert edit.active_edge is None


def test_close_cleanup_runs_immediately_when_no_panels_visible(register_edit_state):
    """No visible panel → gesture ends at once: active_port/edge cleared without an opened popup."""
    session = MagicMock()
    ctx, EditStateCls = make_context(register_edit_state, session=session)
    edit: Any = ctx.data[EditStateCls]
    edit.active_port = MagicMock()
    edit.active_edge = MagicMock()
    registry = PanelRegistry()
    provider, popup, _ = make_provider(ctx, registry)

    provider.on_selection_context((10, 20), ["n1"], [])

    popup.open.assert_not_called()
    assert edit.active_port is None
    assert edit.active_edge is None


def test_a_tree_that_draws_nothing_deletes_the_popup(register_edit_state):
    """Emptiness is a property of the tree: a layout panel polling true is not
    enough to open a menu. The popup is built hidden, rendered into, and
    discarded if no *leaf* drew — and the close cleanup runs either way."""
    session = MagicMock()
    ctx, EditStateCls = make_context(register_edit_state, session=session)
    edit: Any = ctx.data[EditStateCls]
    edit.active_port = MagicMock()
    SelectionMenu = _current_surfaces().SelectionMenu

    from haywire.ui.surface import Surface

    class _EmptyRegionSurface(Surface):
        id = "test_empty_region_surface"

    @panel(
        surface=SelectionMenu,
        hosts=(_EmptyRegionSurface,),
        label="Layout Only",
        registry_id="layout_only_panel",
    )
    class LayoutOnlyPanel(BasePanel):
        actions: Any

        @classmethod
        def poll(cls, context):
            return True

        def draw(self, ctx, layout):
            # Renders an arrangement, but nothing lands inside it.
            pass

    registry = PanelRegistry()
    registry._register_class(LayoutOnlyPanel, _FAKE_LIBRARY_IDENTITY)
    provider, popup, _ = make_provider(ctx, registry)

    provider.on_selection_context((10, 20), ["n1"], [])

    popup.open.assert_not_called()
    popup.delete.assert_called_once()
    assert edit.active_port is None


# The hosting-panel-drawing-an-empty-flyout emptiness case is covered at the
# primitive level in tests/ui/test_flyout_nesting.py (it needs a real NiceGUI
# page context to construct hui.flyout's ui.button anchor, which this file's
# MagicMock-Popup harness does not provide) — see
# test_a_flyout_over_an_empty_body_at_the_popup_level_does_not_count_as_a_leaf.


# ---------------------------------------------------------------------------
# Verb-less surfaces: no ``provides`` means render inert, not abort
# ---------------------------------------------------------------------------


def test_a_surface_declaring_no_provides_opens_with_inert_panels(register_edit_state):
    """A surface with no ``provides`` is not the same as one whose ``provides``
    this host fails to satisfy — the first renders inspector-style panels
    with ``actions=None`` and the menu still opens; only the second aborts.
    Conflating them made every verb-less surface (the common case for a
    third-party surface reached through the DOM attribute — ADR-0029, "No
    addressability check") silently open nothing."""
    session = MagicMock()
    ctx, EditStateCls = make_context(register_edit_state, session=session)
    edit: Any = ctx.data[EditStateCls]
    edit.active_port = MagicMock()

    from haywire.ui.surface import Surface

    class _VerblessSurface(Surface):
        id = "test_verbless_surface"
        # No `provides` — deliberately.

    seen_actions: list[Any] = []

    @panel(
        surface=_VerblessSurface,
        label="Inert",
        registry_id="inert_panel",
    )
    class InertPanel(BasePanel):
        actions: Any

        @classmethod
        def poll(cls, context):
            return True

        def draw(self, ctx, layout):
            seen_actions.append(self.actions)

    registry = PanelRegistry()
    registry._register_class(InertPanel, _FAKE_LIBRARY_IDENTITY)
    provider, popup, _ = make_provider(ctx, registry)

    provider._open_menu(_VerblessSurface, (10, 20))

    popup.open.assert_called_once()
    assert seen_actions == [None]


# ---------------------------------------------------------------------------
# on_surface_context: no fallback for an unregistered surface id
# ---------------------------------------------------------------------------


def test_on_surface_context_with_unregistered_id_opens_nothing_and_logs(register_edit_state, caplog):
    """No fallback. The old ``or NodeFocus`` made the node inspector reachable
    by default from any right-click; deleting the branch means an id that
    resolves to nothing opens nothing and logs — not some default surface."""
    import logging

    session = MagicMock()
    ctx, EditStateCls = make_context(register_edit_state, session=session)
    registry = PanelRegistry()
    provider, popup, _ = make_provider(ctx, registry)

    with caplog.at_level(logging.WARNING):
        provider.on_surface_context((10, 20), "", "no_such_surface_id_anywhere")

    popup.open.assert_not_called()
    assert any("no_such_surface_id_anywhere" in r.getMessage() for r in caplog.records)


# The inverse-emptiness case (a leaf two levels down polling true is enough to
# open the menu) needs real nested render_surface() calls, which need a real
# NiceGUI slot context this file's MagicMock-Popup harness does not provide
# (render_surface builds a real ui.element/PanelLayout) — see
# test_leaf_two_levels_down_is_enough_to_open_the_menu in
# tests/ui/panel/test_render_surface.py.
