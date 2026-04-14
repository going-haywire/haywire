"""
Slot and EditorBinding — runtime containers for the AppShell's four slots.

A :class:`Slot` owns the editor bindings that can be hosted in one of the
four shell slots (``left``, ``right``, ``main``, ``bottom``), the live area
container those editors draw into, and the currently active binding.

A :class:`EditorBinding` pairs an editor class + payload with its live
instance. The ``payload`` field is reserved for a follow-up PRD that will
enable multi-instance editors (e.g., a GraphEditor per open graph file); in
the current scope every binding is constructed with ``payload=None`` and the
field is unused, but carrying it from day one avoids a second refactor.

Relationship to AppShell:

* The shell owns the slot dict ``{"left": Slot, "right": Slot, ...}``.
* The shell renders bars (activity bar, context bar, main/bottom tab bars)
  because those are layout chrome outside the slot's area.
* The shell calls ``slot.render_area(parent)`` to mount each slot's
  container at the right spot in the layout.
* On user click (bar) or ``reveal_editor`` event, the shell calls
  ``slot.switch_to(key)`` and does its own follow-up (bar refresh,
  WORKSPACE_CHANGED broadcast). The slot handles everything inside its
  area — container clear, instance lazy-create, draw.
* On every ``ContextChangedEvent``, the shell calls
  ``slot.handle_context_event(event)`` on each slot to run the poll/draw
  gate on the active binding.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Optional, TYPE_CHECKING

from nicegui import ui

if TYPE_CHECKING:
    from haywire.ui.context_events import ContextChangedEvent
    from haywire.ui.editor.base import BaseEditor
    from haywire.ui.session import Session

logger = logging.getLogger(__name__)


@dataclass
class EditorBinding:
    """
    One editor class + optional payload, paired with its live instance.

    Attributes:
        editor_key: Registry key of the editor class.
        editor_cls: The editor class. Used to create ``instance`` lazily.
        payload: Reserved for the multi-instance follow-up (e.g., a graph
            path). Always ``None`` in scope B; every current call site
            passes ``None``.
        instance: The live editor instance. Created on first activation.
    """

    editor_key: str
    editor_cls: type["BaseEditor"]
    payload: Any = None
    instance: Optional["BaseEditor"] = None

    def ensure_instance(self) -> "BaseEditor":
        """Lazy-create ``instance`` on first use. Subsequent calls return it."""
        if self.instance is None:
            self.instance = self.editor_cls()
        return self.instance


class Slot:
    """
    Runtime manager for one of the four shell slots.

    Owns its editor bindings, the currently active binding, its area
    container, and the slot's visibility state. Provides the switch,
    reveal, and poll/draw entry points used by the AppShell.

    Lifecycle:
        * Constructed by the shell once per slot, seeded with the list of
          bindings appropriate for that slot (registry-derived for
          left/right; workspace-tabs-derived for main/bottom).
        * ``render_area(parent)`` creates the slot's area container as a
          child of ``parent`` and draws the active binding.
        * ``switch_to(key)`` changes the active binding, clears the area,
          re-draws the new active binding's editor. Returns ``True`` only
          when the active key actually changed.
        * ``handle_context_event(event)`` runs the poll/draw gate on the
          active binding. No-op when there is no active binding.
        * ``set_visible(visible)`` toggles the area container visibility.

    Instance state:
        * The editor instance of a previously-active binding is kept in its
          ``EditorBinding`` so its Python-side state survives being hidden.
          The container DOM is cleared on switch and re-built on
          reactivation (``draw()`` runs on a fresh container).
    """

    def __init__(
        self,
        session: "Session",
        name: str,
        initial_bindings: list[EditorBinding],
        active_key: Optional[str] = None,
    ):
        """
        Args:
            session: The owning session (used to access context on
                draw/poll). Slot holds it for its lifetime.
            name: Slot identifier — one of ``"left"``, ``"right"``,
                ``"main"``, ``"bottom"``. Used in logs only.
            initial_bindings: Bindings to host in this slot. The shell is
                responsible for enumerating these per-slot (registry for
                left/right; workspace tabs for main/bottom).
            active_key: Registry key of the initially active binding. If
                the key has no matching binding, the first binding (if
                any) becomes active; if there are no bindings, the slot
                is inactive until a binding is added.
        """
        self._session = session
        self.name = name
        self._bindings: list[EditorBinding] = list(initial_bindings)
        self._active: Optional[EditorBinding] = self._resolve_initial_active(active_key)
        self._visible: bool = True
        self._area_container: Optional["ui.element"] = None

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    def _resolve_initial_active(self, active_key: Optional[str]) -> Optional[EditorBinding]:
        """Pick the starting active binding from ``active_key`` or the first binding."""
        if active_key is not None:
            match = self.find_binding(active_key)
            if match is not None:
                return match
        return self._bindings[0] if self._bindings else None

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @property
    def active_binding(self) -> Optional[EditorBinding]:
        """The binding currently shown in the area, or ``None`` if empty."""
        return self._active

    @property
    def active_key(self) -> Optional[str]:
        """Registry key of the active binding, or ``None`` if empty."""
        return self._active.editor_key if self._active is not None else None

    @property
    def visible(self) -> bool:
        """Whether the area container is currently visible."""
        return self._visible

    @property
    def bindings(self) -> list[EditorBinding]:
        """Read-only view of the bindings list."""
        return list(self._bindings)

    def find_binding(self, editor_key: str) -> Optional[EditorBinding]:
        """
        First-match lookup by registry key.

        Logs a warning when multiple bindings share ``editor_key`` — this
        is a no-op in scope B (every binding has a unique key) but surfaces
        an ambiguity when the multi-instance follow-up lands.
        """
        matches = [b for b in self._bindings if b.editor_key == editor_key]
        if not matches:
            return None
        if len(matches) > 1:
            logger.warning(
                f"Slot '{self.name}': {len(matches)} bindings match key '{editor_key}'; "
                "returning the first. Use a payload-aware reveal once available."
            )
        return matches[0]

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render_area(self, parent: "ui.element") -> None:
        """
        Create the area container as a child of ``parent`` and draw the
        active binding's editor into it.

        Called once during the shell's initial render. The container is
        stored so subsequent ``switch_to`` calls can clear + re-render
        without re-building the wrapper.
        """
        with parent:
            self._area_container = (
                ui.element("div")
                .classes("hw-panel")
                .style(
                    "width: 100%; height: 100%; background: var(--hw-bg-page); color: var(--hw-text-body);"
                )
            )
        self._area_container.set_visibility(self._visible)
        self._draw_active()

    def _draw_active(self) -> None:
        """Clear the area container and draw the active binding (if any)."""
        if self._area_container is None:
            return
        self._area_container.clear()
        if self._active is None:
            with self._area_container:
                ui.label("No editor").classes("hw-text-muted p-4")
            return
        try:
            instance = self._active.ensure_instance()
            instance.draw(self._session.context, self._area_container)
        except Exception as exc:
            logger.error(f"Slot '{self.name}': draw failed for '{self._active.editor_key}': {exc}")
            with self._area_container:
                ui.label(f"Error loading editor: {self._active.editor_key}").classes("hw-text-danger p-4")

    # ------------------------------------------------------------------
    # Switching
    # ------------------------------------------------------------------

    def switch_to(self, editor_key: str) -> bool:
        """
        Change the active binding to the one matching ``editor_key``.

        Re-renders the area on success. No-op if ``editor_key`` already
        identifies the active binding. Logs a warning and returns ``False``
        when no binding matches the key.

        Returns:
            ``True`` iff the active binding actually changed.
        """
        if self._active is not None and self._active.editor_key == editor_key:
            return False

        target = self.find_binding(editor_key)
        if target is None:
            logger.warning(f"Slot '{self.name}': switch_to('{editor_key}') — no binding with that key")
            return False

        self._active = target
        logger.info(f"Slot '{self.name}': switched to '{editor_key}'")
        self._draw_active()
        return True

    # ------------------------------------------------------------------
    # Visibility
    # ------------------------------------------------------------------

    def set_visible(self, visible: bool) -> None:
        """Show or hide the area container."""
        self._visible = visible
        if self._area_container is not None:
            self._area_container.set_visibility(visible)

    # ------------------------------------------------------------------
    # Orchestrator hook
    # ------------------------------------------------------------------

    def handle_context_event(self, event: "ContextChangedEvent") -> None:
        """
        Run the poll/draw gate on the active binding.

        Called by the shell's orchestrator for every ContextChangedEvent.
        Does nothing when the slot has no active binding or when the
        binding's instance has not yet been created (instances are created
        lazily on first draw).
        """
        if self._active is None or self._area_container is None:
            return
        instance = self._active.instance
        if instance is None:
            return
        try:
            if instance.poll(self._session.context, event):
                self._area_container.clear()
                instance.draw(self._session.context, self._area_container)
        except Exception as exc:
            logger.error(f"Slot '{self.name}': poll/draw error for '{self._active.editor_key}': {exc}")

    # ------------------------------------------------------------------
    # Hot-reload support
    # ------------------------------------------------------------------

    def replace_class(
        self,
        editor_key: str,
        new_cls: type["BaseEditor"],
        cleanup_old: Callable[["BaseEditor"], None] | None = None,
    ) -> bool:
        """
        Swap the class of every binding with ``editor_key`` to ``new_cls``.

        Used by the shell's hot-reload handler: when a class is reloaded,
        every binding that references the old class gets its ``instance``
        cleared (after optional cleanup) and its class pointer updated. If
        the reloaded binding was active, a fresh draw runs immediately.

        Returns:
            ``True`` iff a redraw was triggered (i.e., the reloaded class
            was active in this slot).
        """
        redrew = False
        for binding in self._bindings:
            if binding.editor_key != editor_key:
                continue
            if binding.instance is not None and cleanup_old is not None:
                try:
                    cleanup_old(binding.instance)
                except Exception as exc:
                    logger.warning(f"Slot '{self.name}': cleanup error for '{editor_key}': {exc}")
            binding.editor_cls = new_cls
            binding.instance = None
            if self._active is binding:
                self._draw_active()
                redrew = True
        return redrew

    def remove_bindings(
        self,
        editor_key: str,
        cleanup: Callable[["BaseEditor"], None] | None = None,
    ) -> None:
        """
        Drop every binding with ``editor_key`` from the slot.

        Used by the shell's hot-reload handler on CLASS_REMOVED. If the
        active binding is removed, the first remaining binding becomes
        active (or the slot becomes inactive).
        """
        removed = [b for b in self._bindings if b.editor_key == editor_key]
        if not removed:
            return
        for binding in removed:
            if binding.instance is not None and cleanup is not None:
                try:
                    cleanup(binding.instance)
                except Exception as exc:
                    logger.warning(f"Slot '{self.name}': cleanup error for '{editor_key}': {exc}")
        self._bindings = [b for b in self._bindings if b.editor_key != editor_key]
        if self._active in removed:
            self._active = self._bindings[0] if self._bindings else None
            self._draw_active()
