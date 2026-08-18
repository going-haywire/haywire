"""BaseContextMenuProvider — shared infrastructure for panel-driven
context menus.

Concrete subclasses define their own intent methods (e.g. on_node_context,
on_file_context); the base provides _build_popup, the panel iteration
loop, and shared bookkeeping.
"""

from __future__ import annotations

import logging
from typing import Callable, Optional, Tuple, TYPE_CHECKING

from haywire.ui.panel.layout import PanelLayout
from haywire.ui.panel.host_rendering import render_panel, visible_panels
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
    pos, on_close=...) to surface the menu. The base injects ``self`` as
    the ``actions`` provider on each mounted panel, so panel bodies access
    the host via ``self.actions``.
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
        """Build a Popup at the given position. Extracted for testability.

        ``clamp_to_viewport`` keeps the menu on-screen when ``pos`` sits near
        an edge — e.g. the account menu, which opens from a header icon
        pinned at the far-right edge and would otherwise overshoot.
        """
        return Popup(
            position_x=pos[0],
            position_y=pos[1],
            backdrop_click_close=True,
            clamp_to_viewport=True,
        )

    def _open_menu(
        self,
        action: type,
        focus: type,
        pos: Tuple[float, float],
        on_close: Optional[Callable[[], None]] = None,
    ) -> None:
        """Build popup, query panels for (action, focus), inject self as the
        actions provider on each mounted panel, draw matched ones.

        on_close: subclass-supplied cleanup (reset gesture/edit state, resume
        paused drags, etc.). Always runs once the menu is dismissed — and, if
        no panel is visible, runs immediately, since the gesture is over even
        though no popup ever opened. This cleanup is load-bearing: intent
        handlers set edit state (active_port/active_edge, right_clicked_file)
        before calling here and rely on it being reset on close.
        """

        def _wrapped_on_close() -> None:
            self._open_popup = None
            if on_close is not None:
                try:
                    on_close()
                except Exception as exc:
                    logger.exception(f"on_close handler raised: {exc}")

        # Poll-filter before building anything. If nothing is visible there's
        # no popup to open — but the gesture still ended, so run the close
        # cleanup now and bail without constructing/registering a popup.
        panel_classes = self._panel_registry.get_panels_for_action(action, focus)
        visible = visible_panels(panel_classes, self._context)
        if not visible:
            _wrapped_on_close()
            return

        popup = self._build_popup(pos)
        self._open_popup = popup
        popup.on_close(_wrapped_on_close)

        # Inject ``self`` as the actions host (see BasePanel.actions); draw
        # errors surface inline rather than crashing the popup.
        layout = PanelLayout(popup.content)
        for cls in visible:
            render_panel(cls, self._context, layout, actions_host=self)
        popup.open()
