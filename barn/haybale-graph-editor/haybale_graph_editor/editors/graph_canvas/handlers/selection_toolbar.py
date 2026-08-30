"""SelectionToolbarProvider and SelectionToolbarHandlers.

SelectionToolbarProvider manages a persistent floating toolbar that appears
above the canvas selection bounding box. It reuses the panel rendering
machinery from BaseContextMenuProvider but renders panels into a horizontal
ui.row rather than a vertical column.

SelectionToolbarHandlers translates SelectionBoundsEvent / SelectionBoundsHideEvent
into provider calls.

Architecture note: SelectionToolbarProvider does NOT inherit from
BaseContextMenuProvider because the toolbar lifecycle is fundamentally
different — it's persistent (repositioned, not recreated per gesture) and
has no on_close cleanup contract. It composes the needed pieces directly.

It is also **event-driven rather than signal-driven**: it is rebuilt when the
canvas emits new selection bounds, and ``SelectionToolbar`` is *defined* by
the selection, so its panels have no trigger their host does not already
answer. It therefore subscribes to no ``redraw_on`` signal at all — see
ADR-0029, Redraw, for why subscribing it would buy nothing and cost a hazard
(a signal mid-gesture re-showing a toolbar the user hid by starting a pan).
"""

from __future__ import annotations

import logging
from typing import Callable, List, Optional, Tuple, TYPE_CHECKING

from haywire.ui import elements as hui
from haywire.ui.panel.host_rendering import (
    _poll_surface,
    counting_leaves,
    partition_panels,
    render_panel,
    render_path_extended,
)
from haywire.ui.panel.layout import PanelLayout
from haywire.ui.components.graph.event_definitions import (
    SelectionBoundsEvent,
    SelectionBoundsHideEvent,
)
from ..event_handlers import handles_event

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext
    from haywire.core.session.session import Session
    from haywire.ui.panel import BasePanel
    from haywire.ui.panel.registry import PanelRegistry
    from haywire.ui.components.popup import Popup
    from .context_menu import SessionContextMenuProvider

logger = logging.getLogger(__name__)


class SelectionToolbarProvider:
    """Floating-toolbar host: panel-driven, persistent across repositions.

    On show_at(bounds):
      1. Gates ``SelectionToolbar`` once, then collects its panels.
      2. Partitions them into applicable / disabled.
      3. Renders the tree into the popup, counting leaves.
      4. If no leaf drew, hides; otherwise positions and shows.

    On hide():
      Closes the popup via ``v-show`` so its DOM survives one gesture's
      hide/show round trip.

    **Host contract.** ``SelectionToolbar.provides`` is ``SelectionActions``,
    and this class satisfies all seven verbs — five of them by forwarding to
    the ``SessionContextMenuProvider`` constructed alongside it, which already
    implements them against the same canvas. Before the surface model there
    was no structural check anywhere in the panel system, so this class
    claimed both ``ToolbarActions`` and ``SelectionContextActions`` while
    implementing 3 of the latter's 7 verbs; ``render_surface``'s ``isinstance``
    is the first thing that would have caught it. Delegation, not
    duplication, is the fix — the ⋯ then hosts ``SelectionMenu`` directly and
    no panel learns anything.
    """

    def __init__(
        self,
        context: "SessionContext",
        session: "Session",
        panel_registry: "PanelRegistry",
        on_emit_event: Optional[Callable] = None,
        on_emit_sync_event: Optional[Callable] = None,
        menu_provider: Optional["SessionContextMenuProvider"] = None,
    ):
        self._context = context
        self._session = session
        self._panel_registry = panel_registry
        self._on_emit_event = on_emit_event
        self._on_emit_sync_event = on_emit_sync_event
        self._menu_provider = menu_provider
        self._toolbar_popup: Optional["Popup"] = None
        self._last_bounds: Optional[Tuple[float, float, float, float]] = None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def show_at(self, bounds: Tuple[float, float, float, float]) -> None:
        """Position (or reposition) the toolbar above the selection bounding box.

        bounds = (left, top, right, bottom) in viewport CSS px.
        """
        from haybale_graph_editor.surfaces.toolbar import SelectionToolbar

        self._last_bounds = bounds
        left, top, right, bottom = bounds

        if not _poll_surface(SelectionToolbar, self._context):
            self.hide()
            return

        applies, disabled = partition_panels(
            self._panel_registry.get_panels(SelectionToolbar), self._context
        )
        if not applies and not disabled:
            self.hide()
            return

        # Toolbar position: centred above the selection, 12px gap + 44px toolbar height
        center_x = (left + right) / 2
        pos_y = max(0.0, top - 12 - 44)

        if self._toolbar_popup is None:
            self._toolbar_popup = self._build_popup(center_x, pos_y)
        else:
            # Re-open before repositioning: open() calls _initPosition() which
            # resets currentX/Y to the construction-time props, so setPosition
            # must run after open() to land at the correct coordinates.
            if not self._toolbar_popup.is_open:
                self._toolbar_popup.open()
            self._toolbar_popup.run_method("setPosition", center_x, pos_y)

        # Render unconditionally. The old `visible != self._rendered_panels`
        # guard held only the *root* surface's panels, so once the ⋯ hosts a
        # surface it could not see anything nested: a poll flip inside the
        # flyout with an unchanged root set would render stale and never
        # correct. Rebuilding costs one row per gesture end — every
        # selectionBounds emission is edge-triggered (hide on drag/pan start,
        # show on drag end) plus a 120 ms trailing debounce for wheel-zoom,
        # so there is no per-frame path here any more.
        drew = self._render_into_popup(applies, disabled)
        if not drew:
            self.hide()

    def hide(self) -> None:
        """Hide the toolbar without destroying it.

        Uses the popup's Vue-side ``close()`` (a ``v-show`` toggle) so the
        rendered button DOM survives one gesture's hide/show round trip —
        worth keeping even though the per-pan-frame path the original comment
        described no longer exists.
        """
        if self._toolbar_popup is not None and self._toolbar_popup.is_open:
            try:
                self._toolbar_popup.close()
            except Exception:
                pass

    def destroy(self) -> None:
        """Fully tear down the popup (real lifecycle cleanup, not gesture hide)."""
        if self._toolbar_popup is not None:
            try:
                self._toolbar_popup.close()
                self._toolbar_popup.delete()
            except Exception:
                pass
            self._toolbar_popup = None

    # ------------------------------------------------------------------
    # Popup construction
    # ------------------------------------------------------------------

    def _build_popup(self, x: float, y: float) -> "Popup":
        """Create a persistent, non-modal toolbar popup at (x, y)."""
        from haywire.ui.components.popup import Popup

        popup = Popup(
            position_x=x,
            position_y=y,
            backdrop_click_close=False,
            backdrop_color="transparent",
            draggable=False,
            clamp_to_viewport=True,
            center_x=True,
        )
        popup.open()
        return popup

    def _render_into_popup(
        self,
        applies: List[type["BasePanel"]],
        disabled: List[type["BasePanel"]],
    ) -> bool:
        """Clear popup content, render panels into a horizontal ui.row.

        Returns whether any *leaf* panel drew — the same emptiness rule the
        context-menu host uses. A toolbar holding only the ⋯ (a hosting panel
        whose flyout body came up empty) is not a toolbar worth showing.
        """
        from nicegui import ui
        from haybale_graph_editor.surfaces.toolbar import SelectionToolbar

        popup = self._toolbar_popup
        if popup is None:
            return False

        popup.content.clear()

        by_order = sorted(
            [(cls, False) for cls in applies] + [(cls, True) for cls in disabled],
            key=lambda pair: getattr(pair[0].class_identity, "order", 100),
        )

        with counting_leaves() as leaves, render_path_extended(SelectionToolbar.id):
            with popup.content:
                # The toolbar row is a menu level of its own: push the root
                # flyout-sibling group around it so submenu rows drawn by its
                # panels (and by anything nested) share one group.
                with (
                    ui.row().classes("hw-selection-toolbar items-center gap-1 no-wrap"),
                    hui.open_flyout_group(),
                ):
                    layout = PanelLayout(ui.element("div"))
                    for cls, is_disabled in by_order:
                        render_panel(
                            cls,
                            self._context,
                            layout,
                            actions_host=self,
                            registry=self._panel_registry,
                            disabled=is_disabled,
                        )
            return leaves() > 0

    # ------------------------------------------------------------------
    # SelectionActions Protocol implementation
    # ------------------------------------------------------------------
    #
    # copy/delete are emitted here directly (they predate the delegation and
    # read the same EditState); the remaining five forward to the menu
    # provider, which already implements them. Forwarding rather than
    # duplicating keeps one definition of each verb.

    def copy_selection(self) -> None:
        """Emit UserCopySelectedEvent for the current selection."""
        from haywire.ui.components.graph.event_definitions import UserCopySelectedEvent
        from ....state.edit_state import EditState

        edit = self._context.data[EditState]
        event = UserCopySelectedEvent(
            selectedNodes=list(edit.selected_nodes),
            selectedEdges=list(edit.selected_edges),
        )
        if self._on_emit_event is not None:
            self._on_emit_event(event)

    def delete_selection(self) -> None:
        """Emit UserRemoveEvent for the current selection."""
        from haywire.ui.components.graph.event_definitions import UserRemoveEvent
        from ....state.edit_state import EditState

        edit = self._context.data[EditState]
        event = UserRemoveEvent(
            nodes=list(edit.selected_nodes),
            edges=list(edit.selected_edges),
        )
        if self._on_emit_event is not None:
            self._on_emit_event(event)

    def paste_at_click(self) -> None:
        self._delegate("paste_at_click")

    def redraw_selection(self) -> None:
        self._delegate("redraw_selection")

    def revalidate_selection(self) -> None:
        self._delegate("revalidate_selection")

    def reset_selection(self) -> None:
        self._delegate("reset_selection")

    def dissolve_reroute(self, node_id: str) -> None:
        self._delegate("dissolve_reroute", node_id)

    # ADR 0032 card axes. Required here even though the toolbar draws no rows
    # for them itself: its ⋯ hosts SelectionMenu directly, and render_surface
    # isinstance-checks the host against that surface's `provides`. A verb
    # missing here does not fail at the missing row — it fails the whole menu.
    def set_selection_collapsed(self, collapsed: bool) -> None:
        self._delegate("set_selection_collapsed", collapsed)

    def selection_is_collapsed(self) -> bool:
        return bool(self._delegate_result("selection_is_collapsed"))

    def toggle_selection_collapsed(self) -> bool:
        return bool(self._delegate_result("toggle_selection_collapsed"))

    def set_selection_detail(self, detail: str) -> None:
        self._delegate("set_selection_detail", detail)

    def clear_selection_detail_overrides(self) -> None:
        self._delegate("clear_selection_detail_overrides")

    def _delegate_result(self, verb: str, *args: object) -> object:
        """Forward a verb that RETURNS something, rather than a fire-and-forget one.

        ``_delegate`` swallows the return value, which is fine for commands and
        wrong for a query like ``selection_is_collapsed``. With no provider the
        answer is ``None`` — callers coerce, and a toggle reading False simply
        offers to collapse.
        """
        if self._menu_provider is None:
            logger.warning("SelectionToolbarProvider: no menu provider to delegate %r to", verb)
            return None
        return getattr(self._menu_provider, verb)(*args)

    def _delegate(self, verb: str, *args: object) -> None:
        """Forward one verb to the SessionContextMenuProvider.

        Absent (a test constructing the toolbar alone), the verb is a no-op
        and logs — the alternative, raising from a click handler, would take
        down the popup for a case the canvas never produces.
        """
        if self._menu_provider is None:
            logger.warning("SelectionToolbarProvider: no menu provider to delegate %r to", verb)
            return
        getattr(self._menu_provider, verb)(*args)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


class SelectionToolbarHandlers:
    """Route SelectionBounds* events to SelectionToolbarProvider."""

    def __init__(self, provider: SelectionToolbarProvider):
        self._provider = provider

    @handles_event(SelectionBoundsEvent)
    def process_selection_bounds(self, event: SelectionBoundsEvent) -> None:
        """Show or reposition the toolbar above the selection."""
        self._provider.show_at((event.left, event.top, event.right, event.bottom))

    @handles_event(SelectionBoundsHideEvent)
    def process_selection_bounds_hide(self, event: SelectionBoundsHideEvent) -> None:
        """Hide the toolbar during pan/zoom/drag gestures."""
        self._provider.hide()
