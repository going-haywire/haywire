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
"""

from __future__ import annotations

import logging
from typing import Callable, List, Optional, Tuple, TYPE_CHECKING

from haywire.ui.panel.host_rendering import render_panel, visible_panels
from haywire.ui.panel.layout import PanelLayout
from haywire.ui.components.graph.event_definitions import (
    SelectionBoundsEvent,
    SelectionBoundsHideEvent,
)
from ..event_handlers import handles_event

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext
    from haywire.core.session.session import Session
    from haywire.ui.panel.registry import PanelRegistry
    from haywire.ui.components.popup import Popup

logger = logging.getLogger(__name__)


class SelectionToolbarProvider:
    """Floating-toolbar host: panel-driven, persistent across repositions.

    On show_at(bounds):
      1. Collects toolbar panels via the registry (ToolbarActions + SelectionContextActions
         against ToolbarFocus), deduped and sorted by order.
      2. Poll-filters via visible_panels().
      3. If nothing is visible, hides any existing popup and returns.
      4. If a popup exists, repositions it. Otherwise creates a new one.
      5. Clears popup content, renders visible panels into a horizontal ui.row.

    On hide():
      Closes and deletes the popup, clearing _toolbar_popup.

    SelectionToolbarProvider also implements the ToolbarActions and
    SelectionContextActions Protocols structurally so panels can call
    copy_selection / delete_selection / open_overflow_menu on self.actions.
    """

    def __init__(
        self,
        context: "SessionContext",
        session: "Session",
        panel_registry: "PanelRegistry",
        on_emit_event: Optional[Callable] = None,
        on_emit_sync_event: Optional[Callable] = None,
    ):
        self._context = context
        self._session = session
        self._panel_registry = panel_registry
        self._on_emit_event = on_emit_event
        self._on_emit_sync_event = on_emit_sync_event
        self._toolbar_popup: Optional["Popup"] = None
        self._last_bounds: Optional[Tuple[float, float, float, float]] = None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def show_at(self, bounds: Tuple[float, float, float, float]) -> None:
        """Position (or reposition) the toolbar above the selection bounding box.

        bounds = (left, top, right, bottom) in viewport CSS px.
        """
        self._last_bounds = bounds
        left, top, right, bottom = bounds

        panel_classes = self._collect_toolbar_panels()
        visible = visible_panels(panel_classes, self._context)

        if not visible:
            self.hide()
            return

        # Toolbar position: centred above the selection, 12px gap + 44px toolbar height
        center_x = (left + right) / 2
        pos_y = max(0.0, top - 12 - 44)

        if self._toolbar_popup is None:
            self._toolbar_popup = self._build_popup(center_x, pos_y)
        else:
            # Reposition existing popup via Vue method
            self._toolbar_popup.run_method("setPosition", center_x, pos_y)

        # Rebuild content in a horizontal row
        self._render_into_popup(visible)

    def hide(self) -> None:
        """Dismiss the toolbar popup."""
        if self._toolbar_popup is not None:
            try:
                self._toolbar_popup.close()
                self._toolbar_popup.delete()
            except Exception:
                pass
            self._toolbar_popup = None

    # ------------------------------------------------------------------
    # Panel collection
    # ------------------------------------------------------------------

    def _collect_toolbar_panels(self) -> List[type]:
        """Query registry for panels matching ToolbarActions and SelectionContextActions
        against ToolbarFocus, deduplicated and sorted by order.
        """
        from haybale_graph_editor.focuses import ToolbarFocus
        from haybale_graph_editor.editors.graph_canvas.handlers.context_menu_actions import (
            SelectionContextActions,
            ToolbarActions,
        )

        seen: set[type] = set()
        combined: List[type] = []

        for action_protocol in (ToolbarActions, SelectionContextActions):
            panels = self._panel_registry.get_panels_for_action(action_protocol, ToolbarFocus)
            for cls in panels:
                if cls not in seen:
                    seen.add(cls)
                    combined.append(cls)

        # Sort by the order stored on class_identity (set by @panel decorator)
        combined.sort(key=lambda cls: getattr(getattr(cls, "class_identity", None), "order", 0))
        return combined

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
        )
        popup.open()
        return popup

    def _render_into_popup(self, panel_classes: List[type]) -> None:
        """Clear popup content and render panels into a horizontal ui.row."""
        from nicegui import ui

        popup = self._toolbar_popup
        if popup is None:
            return

        popup.content.clear()

        with popup.content:
            with ui.row().classes("hw-selection-toolbar items-center gap-1 no-wrap"):
                layout = PanelLayout(ui.element("div"))
                for cls in panel_classes:
                    render_panel(cls, self._context, layout, actions_host=self)

    # ------------------------------------------------------------------
    # ToolbarActions Protocol implementation
    # ------------------------------------------------------------------

    def open_overflow_menu(self) -> None:
        """Emit ContextMenuSelectedEvent near the toolbar's right edge."""
        from haywire.ui.components.graph.event_definitions import ContextMenuSelectedEvent
        from ....state.edit_state import EditState

        if self._last_bounds is None:
            return

        left, top, right, bottom = self._last_bounds
        # Position the overflow menu near the toolbar's right edge
        pos_x = right
        pos_y = max(0.0, top - 12 - 44)

        edit = self._context.data[EditState]
        event = ContextMenuSelectedEvent(
            screenX=pos_x,
            screenY=pos_y,
            canvasX=pos_x,
            canvasY=pos_y,
            selectedNodes=list(edit.selected_nodes),
            selectedEdges=list(edit.selected_edges),
        )
        if self._on_emit_event is not None:
            self._on_emit_event(event)

    # ------------------------------------------------------------------
    # SelectionContextActions Protocol implementation
    # ------------------------------------------------------------------

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
