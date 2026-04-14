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

    @property
    def binding_id(self) -> str:
        """Stable identity matching :attr:`TabState.tab_id`.

        Equals ``editor_key`` for single-instance bindings (the case for every
        binding today) and ``editor_key::payload`` when a payload is present.
        Used as the key for the slot's per-binding ``ui.tab_panel``.
        """
        return f"{self.editor_key}::{self.payload}" if self.payload else self.editor_key

    def ensure_instance(self) -> "BaseEditor":
        """Lazy-create ``instance`` on first use. Subsequent calls return it.

        On creation the binding attaches itself to the instance via
        ``instance.binding = self`` so the editor can read its own
        ``editor_key`` / ``payload`` at any time (draw, poll, handlers)
        without the slot having to pass it through each entry point.
        """
        if self.instance is None:
            self.instance = self.editor_cls()
            self.instance.binding = self
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
        self._panels: dict[str, "ui.element"] = {}
        self._drawn: set[str] = set()

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
    def active_binding_id(self) -> Optional[str]:
        """Full binding id (``editor_key`` or ``editor_key::payload``) of the active binding."""
        return self._active.binding_id if self._active is not None else None

    @property
    def visible(self) -> bool:
        """Whether the area container is currently visible."""
        return self._visible

    @property
    def bindings(self) -> list[EditorBinding]:
        """Read-only view of the bindings list."""
        return list(self._bindings)

    def find_binding(self, editor_key: str, payload: Any = None) -> Optional[EditorBinding]:
        """
        Lookup a binding by ``(editor_key, payload)``.

        An exact match (both fields equal) always wins. When ``payload`` is
        ``None`` and no exact match exists, falls back to the first binding
        whose ``editor_key`` matches — this preserves the behavior every
        pre-multi-instance call site relied on.

        Warns on ambiguous matches so the multi-instance migration surfaces
        any call site that still looks up by key alone when duplicates exist.
        """
        exact = [b for b in self._bindings if b.editor_key == editor_key and b.payload == payload]
        if exact:
            if len(exact) > 1:
                logger.warning(
                    f"Slot '{self.name}': {len(exact)} bindings match "
                    f"({editor_key!r}, payload={payload!r}); returning the first."
                )
            return exact[0]

        if payload is None:
            fuzzy = [b for b in self._bindings if b.editor_key == editor_key]
            if not fuzzy:
                return None
            if len(fuzzy) > 1:
                logger.warning(
                    f"Slot '{self.name}': {len(fuzzy)} bindings match key '{editor_key}' "
                    "(payload-less lookup); returning the first. "
                    "Pass payload to disambiguate once multi-instance tabs land."
                )
            return fuzzy[0]
        return None

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render_area(self, parent: "ui.element") -> None:
        """
        Create the area container (a headless ``ui.tab_panels``) as a child
        of ``parent`` and draw the active binding's editor into its panel.

        Each binding gets its own ``ui.tab_panel`` keyed by ``editor_key``.
        All panels live in the DOM simultaneously; switching toggles
        visibility via ``set_value`` rather than clearing and re-rendering.

        Called once during the shell's initial render. The container and
        per-binding panels are stored so ``switch_to`` can change the
        active panel without rebuilding anything.
        """
        initial_value = self._active.binding_id if self._active is not None else None
        with parent:
            self._area_container = (
                ui.tab_panels(value=initial_value, animated=False)
                .props("keep-alive")
                .classes("hw-panel")
                .style(
                    "width: 100%; height: 100%; background: var(--hw-bg-page); color: var(--hw-text-body);"
                )
            )
        self._area_container.set_visibility(self._visible)

        for binding in self._bindings:
            self._create_panel(binding)

        if self._active is None and self._area_container is not None:
            with self._area_container:
                ui.label("No editor").classes("hw-text-muted p-4")
        elif self._active is not None:
            self._ensure_drawn(self._active)

    def _create_panel(self, binding: EditorBinding) -> None:
        """Create a ``ui.tab_panel`` shell for ``binding``. Draw is deferred."""
        if self._area_container is None:
            return
        with self._area_container:
            panel = ui.tab_panel(binding.binding_id).style("width: 100%; height: 100%; padding: 0;")
        self._panels[binding.binding_id] = panel

    def _ensure_drawn(self, binding: EditorBinding) -> None:
        """Draw the binding's editor into its panel on first activation."""
        bid = binding.binding_id
        if bid in self._drawn:
            return
        panel = self._panels.get(bid)
        if panel is None:
            return
        try:
            instance = binding.ensure_instance()
            instance.draw(self._session.context, panel)
            self._drawn.add(bid)
        except Exception as exc:
            logger.error(f"Slot '{self.name}': draw failed for '{bid}': {exc}")
            with panel:
                ui.label(f"Error loading editor: {bid}").classes("hw-text-danger p-4")

    def _redraw(self, binding: EditorBinding) -> None:
        """Full redraw of one binding's panel (clear + draw)."""
        panel = self._panels.get(binding.binding_id)
        if panel is None:
            return
        panel.clear()
        self._drawn.discard(binding.binding_id)
        self._ensure_drawn(binding)

    # ------------------------------------------------------------------
    # Switching
    # ------------------------------------------------------------------

    def switch_to(self, editor_key: str, payload: Any = None) -> bool:
        """
        Change the active binding to the one matching ``(editor_key, payload)``.

        Re-renders the area on success. No-op if the target is already
        active. Logs a warning and returns ``False`` when no binding matches.
        Callers pre-dating multi-instance bindings omit ``payload``; see
        :meth:`find_binding` for the fallback rules.

        Returns:
            ``True`` iff the active binding actually changed.
        """
        target = self.find_binding(editor_key, payload)
        if target is None:
            logger.warning(
                f"Slot '{self.name}': switch_to({editor_key!r}, payload={payload!r}) — no matching binding"
            )
            return False

        if self._active is target:
            return False

        self._active = target
        logger.info(f"Slot '{self.name}': switched to '{target.binding_id}'")
        self._ensure_drawn(target)
        if self._area_container is not None:
            self._area_container.set_value(target.binding_id)
        return True

    def add_binding(self, binding: EditorBinding, activate: bool = False) -> None:
        """
        Append a new binding to the slot, creating its panel if the area
        has already been rendered.

        Used by main/bottom when a workspace tab opens at runtime (the
        left/right slots are seeded from the registry at construction).
        """
        self._bindings.append(binding)
        if self._area_container is not None:
            self._create_panel(binding)
        if activate:
            if self._active is None:
                self._active = binding
                self._ensure_drawn(binding)
                if self._area_container is not None:
                    self._area_container.set_value(binding.binding_id)
            else:
                self.switch_to(binding.editor_key, binding.payload)

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
                self._redraw(self._active)
        except Exception as exc:
            logger.error(f"Slot '{self.name}': poll/draw error for '{self._active.binding_id}': {exc}")

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
            self._redraw(binding)
            if self._active is binding:
                redrew = True
        return redrew

    def remove_binding(
        self,
        editor_key: str,
        payload: Any = None,
        cleanup: Callable[["BaseEditor"], None] | None = None,
    ) -> Optional[EditorBinding]:
        """
        Remove a single binding matching ``(editor_key, payload)``.

        Used by the shell to close one multi-instance tab without touching
        sibling tabs that share the same ``editor_key``. If the removed
        binding was active, the next binding in the list becomes active
        (falling back to the previous one if there is no next; ``None`` if
        the slot is now empty).

        Returns the removed binding, or ``None`` when no match was found.
        """
        target = self.find_binding(editor_key, payload)
        if target is None:
            return None

        if target.instance is not None and cleanup is not None:
            try:
                cleanup(target.instance)
            except Exception as exc:
                logger.warning(f"Slot '{self.name}': cleanup error for '{target.binding_id}': {exc}")

        panel = self._panels.pop(target.binding_id, None)
        if panel is not None:
            panel.delete()
        self._drawn.discard(target.binding_id)

        was_active = self._active is target
        idx = self._bindings.index(target)
        self._bindings.remove(target)

        if was_active:
            if self._bindings:
                next_idx = min(idx, len(self._bindings) - 1)
                self._active = self._bindings[next_idx]
                self._ensure_drawn(self._active)
                if self._area_container is not None:
                    self._area_container.set_value(self._active.binding_id)
            else:
                self._active = None
        return target

    def repayload_binding(
        self,
        editor_key: str,
        old_payload: Any,
        new_payload: Any,
    ) -> bool:
        """
        Re-key an existing binding's payload in-place.

        Used by the shell to track a graph whose haystack key changed (e.g.
        save-as moved an entry from ``__new_3__`` to an absolute path). The
        binding keeps its editor instance; only the identity used for
        ``find_binding`` / ``switch_to`` / ``binding_id`` changes.

        The ``ui.tab_panel`` DOM node also needs its name updated so
        ``ui.tab_panels.set_value`` still selects it. Returns ``False`` when
        no binding matches or when the new id collides with an existing one.
        """
        target = self.find_binding(editor_key, old_payload)
        if target is None:
            return False
        if target.payload == new_payload:
            return True

        new_id = f"{editor_key}::{new_payload}" if new_payload else editor_key
        if any(b is not target and b.binding_id == new_id for b in self._bindings):
            logger.warning(f"Slot '{self.name}': repayload collision — '{new_id}' already exists")
            return False

        old_id = target.binding_id
        target.payload = new_payload

        panel = self._panels.pop(old_id, None)
        if panel is not None:
            panel._props["name"] = new_id
            self._panels[new_id] = panel
        drawn = old_id in self._drawn
        self._drawn.discard(old_id)
        if drawn:
            self._drawn.add(new_id)
        if self._active is target and self._area_container is not None:
            self._area_container.set_value(new_id)
        return True

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
            panel = self._panels.pop(binding.binding_id, None)
            if panel is not None:
                panel.delete()
            self._drawn.discard(binding.binding_id)
        self._bindings = [b for b in self._bindings if b.editor_key != editor_key]
        if self._active in removed:
            self._active = self._bindings[0] if self._bindings else None
            if self._active is not None:
                self._ensure_drawn(self._active)
                if self._area_container is not None:
                    self._area_container.set_value(self._active.binding_id)
