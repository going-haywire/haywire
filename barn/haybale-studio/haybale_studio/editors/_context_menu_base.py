"""BaseContextMenuProvider — shared infrastructure for panel-driven
context menus. Used by:
  - SessionContextMenuProvider (graph canvas)
  - SessionFileMenuProvider (file browser)

Concrete subclasses define their own intent methods (e.g. on_node_context,
on_file_context); the base provides _build_popup, the panel iteration
loop, and shared bookkeeping.
"""

from __future__ import annotations

import logging
from typing import Callable, Optional, Tuple, TYPE_CHECKING

from haywire.ui.panel.layout import PanelLayout
from haywire.ui.components.popup import Popup

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext
    from haywire.core.session.session import Session
    from haywire.ui.panel.registry import PanelRegistry

logger = logging.getLogger(__name__)


class BaseContextMenuProvider:
    """Shared base for panel-driven context menu providers.

    Subclasses provide intent methods (e.g. on_node_context) and the
    actions Protocol implementation. They call _open_menu(action, focus,
    pos, on_close=...) to surface the menu.
    """

    def __init__(
        self,
        context: "SessionContext",
        session: "Session",
        panel_registry: "PanelRegistry",
    ):
        self._context = context
        self._session = session
        self._panel_registry = panel_registry
        self._open_popup: Optional[Popup] = None

    def _build_popup(self, pos: Tuple[float, float]) -> Popup:
        """Build a Popup at the given position. Extracted for testability."""
        return Popup(position_x=pos[0], position_y=pos[1], backdrop_click_close=True)

    def _open_menu(
        self,
        action: type,
        focus: type,
        pos: Tuple[float, float],
        on_close: Optional[Callable[[], None]] = None,
    ) -> None:
        """Build popup, query panels for (action, focus), draw matched ones.

        on_close: subclass-supplied additional cleanup, called when the
        popup closes (after the base clears _open_popup).

        Same behavior as canvas on no-panels-found: no eager cleanup.
        """
        popup = self._build_popup(pos)
        self._open_popup = popup

        def _wrapped_on_close() -> None:
            self._open_popup = None
            if on_close is not None:
                try:
                    on_close()
                except Exception as exc:
                    logger.exception(f"on_close handler raised: {exc}")

        popup.on_close(_wrapped_on_close)

        panel_classes = self._panel_registry.get_panels_for(actions_provider=self, focus=focus)
        visible = [cls for cls in panel_classes if cls.poll(self._context)]
        if not visible:
            return

        layout = PanelLayout(popup.content)
        for cls in visible:
            try:
                cls().draw(self._context, layout, self)
            except Exception as exc:
                logger.exception(f"Error drawing context menu panel {cls.__name__}: {exc}")
        popup.open()
