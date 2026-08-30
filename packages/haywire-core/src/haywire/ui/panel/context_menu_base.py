"""BaseContextMenuProvider — shared infrastructure for panel-driven
context menus.

Concrete subclasses define their own intent methods (e.g. on_node_context,
on_file_context); the base provides _build_popup, the panel iteration
loop, and shared bookkeeping.
"""

from __future__ import annotations

import logging
from typing import Callable, Optional, Tuple, TYPE_CHECKING

from haywire.ui import elements as hui
from haywire.ui.panel.layout import PanelLayout
from haywire.ui.panel.host_rendering import (
    _poll_surface,
    counting_leaves,
    partition_panels,
    render_panel,
    render_path_extended,
)
from haywire.ui.components.popup import Popup

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext
    from haywire.core.session.session import Session
    from haywire.ui.panel.registry import PanelRegistry
    from haywire.ui.surface import Surface

logger = logging.getLogger(__name__)


class BaseContextMenuProvider:
    """Shared base for panel-driven context menu providers.

    Subclasses provide intent methods (e.g. on_node_context) and implement
    whatever Protocol the surfaces they open declare as ``provides``. They
    call ``_open_menu(surface, pos, on_close=...)`` to surface the menu. The
    base injects ``self`` as the ``actions`` host on each mounted panel, so
    panel bodies reach the host via ``self.actions``.

    The host renders only the *root* surface's panels; anything nested is a
    panel's own ``render_surface`` call.
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

    def close_open_menu(self) -> None:
        """Dismiss the menu this provider currently has open, if any.

        **Call this before a new gesture seeds any state, not from inside
        ``_open_menu``.** Closing fires the previous popup's ``on_close``,
        which resets that gesture's edit state and its ``_OpenMenuContext``.
        By the time ``_open_menu`` runs, the *new* gesture has already written
        both — an intent handler sets ``active_node`` / ``pending_connection``
        and only then opens the menu — so closing there would have the old
        cleanup wipe the new gesture's context. The single dispatch point
        (``ContextMenuHandlers.process_context_menu``) is early enough that the
        old cleanup can only touch the gesture it belongs to.

        Closing is what clears ``_open_popup``, via that ``on_close`` — so this
        must not clear the attribute itself, or the cleanup would see a
        provider with no open menu and the two would disagree.

        Never raises: a popup whose client has gone (page closed under a
        pending gesture) must not take the next menu down with it.
        """
        popup = self._open_popup
        if popup is None:
            return
        try:
            popup.close()
        except Exception as exc:
            logger.debug(f"closing previous context menu failed: {exc}")
            self._open_popup = None

    def _open_menu(
        self,
        surface: type["Surface"],
        pos: Tuple[float, float],
        on_close: Optional[Callable[[], None]] = None,
    ) -> None:
        """Gate the surface, render its tree into a hidden popup, keep it if
        a leaf drew.

        on_close: subclass-supplied cleanup (reset gesture/edit state, resume
        paused drags, etc.). Always runs once the menu is dismissed — and, if
        no popup opens, runs immediately, since the gesture is over even
        though nothing appeared. This cleanup is load-bearing: intent
        handlers set edit state (active_port/active_edge, right_clicked_file)
        before calling here and rely on it being reset on close.

        **Emptiness is a property of the tree, not of the root surface**
        (ADR-0029). A layout panel polls true unconditionally, so the root's
        panel list stops answering the question once nesting exists. The
        popup is therefore built (``start-visible: False``, so invisible),
        the whole tree is rendered into it, and it is opened only if a *leaf*
        panel — one declaring no ``hosts=`` — drew via either ``draw()`` or
        ``draw_disabled()``. Otherwise it is deleted, which reclaims the whole
        subtree, and the close cleanup runs exactly as it does when nothing
        polls true.
        """

        def _wrapped_on_close() -> None:
            self._open_popup = None
            if on_close is not None:
                try:
                    on_close()
                except Exception as exc:
                    logger.exception(f"on_close handler raised: {exc}")

        # Gate the surface before building anything. A surface that does not
        # apply costs nothing and takes the cheap early return, which is what
        # keeps the common paths off the render-then-discard path below.
        if not _poll_surface(surface, self._context):
            _wrapped_on_close()
            return

        panels = self._panel_registry.get_panels(surface)
        applies, disabled = partition_panels(panels, self._context)
        if not applies and not disabled:
            _wrapped_on_close()
            return

        satisfied, host = self._host_for(surface)
        if not satisfied:
            _wrapped_on_close()
            return

        popup = self._build_popup(pos)
        layout = PanelLayout(popup.content)
        by_order = sorted(
            [(cls, False) for cls in applies] + [(cls, True) for cls in disabled],
            key=lambda pair: getattr(pair[0].class_identity, "order", 100),
        )

        # A popup is a menu *level*: push the root flyout-sibling group around
        # its content so any submenu rows drawn inside — on this surface or
        # any nested one — share one group and close each other.
        with counting_leaves() as leaves, render_path_extended(surface.id):
            with popup.content, hui.open_flyout_group():
                for cls, is_disabled in by_order:
                    render_panel(
                        cls,
                        self._context,
                        layout,
                        actions_host=host,
                        registry=self._panel_registry,
                        disabled=is_disabled,
                    )
            drew = leaves() > 0

        if not drew:
            popup.delete()
            _wrapped_on_close()
            return

        self._open_popup = popup
        popup.on_close(_wrapped_on_close)
        popup.open()

    def _host_for(self, surface: type["Surface"]) -> Tuple[bool, object | None]:
        """``(contract_satisfiable, host)`` for this surface's panels.

        The two halves answer different questions, and conflating them is what
        made a verb-less surface abort the whole menu:

        - ``(True, self)`` — the surface declares a ``provides`` Protocol this
          provider satisfies. Its panels reach the provider via ``self.actions``.
        - ``(True, None)`` — the surface declares **no** ``provides``. There is
          no contract to fail, so the menu proceeds and the panels render with
          ``actions=None``. This is inert rather than broken: a verb-less
          surface's panels never call ``self.actions``, and it is the *common*
          case for a third-party surface reached through the DOM attribute,
          since ``provides`` is checked against a Protocol a third-party library
          cannot extend (ADR-0029, "No addressability check").
        - ``(False, None)`` — the surface demands verbs this provider does not
          have. That contract genuinely cannot be satisfied, so it is an
          authoring error, reported as one, and the only case that aborts.
        """
        want = getattr(surface, "provides", None)
        if want is None:
            return True, None
        if not isinstance(self, want):
            logger.warning(
                "%s does not satisfy %s, required by surface %r — no menu opened.",
                type(self).__name__,
                want.__name__,
                surface.id,
            )
            return False, None
        return True, self
