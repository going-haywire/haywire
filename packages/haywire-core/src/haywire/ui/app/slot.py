"""
Slot and EditorWrapper — runtime containers for the AppShell's four slots.

A :class:`Slot` owns the editor wrappers that can be hosted in one of the
four shell slots (``left``, ``right``, ``main``, ``bottom``), the live area
container those editors draw into, and the currently active wrapper.

An :class:`EditorWrapper` pairs an editor class + binding_id with its live
instance and self-subscribes to the editor registry for hot-reload events.
The ``binding_id`` field enables multi-instance editors (e.g., a GraphEditor
per open graph file).

Relationship to AppShell:

* The shell owns the slot dict ``{"left": Slot, "right": Slot, ...}``.
* The shell renders bars (activity bar, context bar, main/bottom tab bars)
  because those are layout chrome outside the slot's area.
* The shell calls ``slot.render(parent)`` (or ``slot._render_area`` directly
  at existing call sites until Task 10) to mount each slot's container at
  the right spot in the layout.
* On user click (bar) or a ``Reveal`` lifecycle command, the shell calls
  ``slot.switch_to(key)`` and does its own follow-up (bar refresh).
  ``Slot._activate`` calls ``editor.on_focus`` for the newly-active
  wrapper. The slot handles everything inside its area — container
  clear, instance lazy-create, draw.
* On every ``ContextSignal``, the shell calls
  ``slot.handle_signal(signal)`` on each slot. The slot fans the
  signal to ``on_signal`` on every wrapper (side-effect channel,
  active or not), then calls ``redraw_on_signal`` on the active
  wrapper and redraws if it returns True.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import nullcontext
import logging
from typing import Any, Callable, ClassVar, Literal, Optional, TYPE_CHECKING

from nicegui import ui

from haywire.core.registry.lifecycle_event import LifeCycleEvent, LifeCycleEventType
from haywire.ui.editor.registry import EditorTypeRegistry
from haywire.ui.editor.wrapper import EditorWrapper

if TYPE_CHECKING:
    from haywire.core.session.signals_and_lifecycle import ContextSignal
    from haywire.ui.editor.base import BaseEditor
    from haywire.core.session.session import Session

logger = logging.getLogger(__name__)


class Slot(ABC):
    """
    Runtime manager for one of the four shell slots.

    Owns its editor wrappers, the currently active wrapper, its area
    container, and the slot's visibility state. Provides the switch,
    reveal, and poll/draw entry points used by the AppShell.

    Lifecycle:
        * Constructed by the shell once per slot. After construction,
          callers must call :meth:`populate_from_snapshot` or
          :meth:`add_binding` before any rendering.
        * ``render(parent)`` creates the slot's area container as a
          child of ``parent`` and draws the active wrapper.
        * ``switch_to(key)`` changes the active wrapper, clears the area,
          re-draws the new active wrapper's editor. Returns ``True`` only
          when the active key actually changed.
        * ``handle_signal(signal)`` runs ``on_signal`` on every wrapper
          (side-effect channel) and ``redraw_on_signal`` on the active
          wrapper, redrawing if the latter returns True.
        * ``set_visible(visible)`` toggles the area container visibility.

    Instance state:
        * The editor instance of a previously-active wrapper is kept in its
          :class:`EditorWrapper` so its Python-side state survives being
          hidden. The container DOM is cleared on switch and re-built on
          reactivation (``draw()`` runs on a fresh container).
    """

    def __init__(
        self,
        session: "Session",
        name: str,
        registry: EditorTypeRegistry,
        on_visibility_change: Optional[Callable[[bool], None]] = None,
        bar_place: Literal["left", "right", "top", "bottom"] = "left",
        show_fold_toggle: bool = False,
        visible: bool = True,
        size: int = 300,
    ):
        """
        Args:
            session: The owning session.
            name: Slot identifier — one of ``"left"``, ``"right"``,
                ``"main"``, ``"bottom"``.
            registry: Editor type registry; passed through to wrappers
                constructed via add_binding / populate_from_snapshot.
            on_visibility_change: Optional callback fired when the slot's
                visibility changes.
            bar_place: Where the bar renders relative to the area.
                ``"left"``/``"right"`` for icon slots (horizontal layout);
                ``"top"``/``"bottom"`` for tab slots (vertical layout).
            show_fold_toggle: Render a fold toggle on the bar. When ``True``
                the content box uses a fixed pixel size (resizable/foldable);
                when ``False`` it fills remaining space with ``flex: 1``.
            visible: Initial visibility of the slot's area container.
            size: Initial pixel size for the slot's content box (width for
                horizontal slots, height for vertical fold-toggle slots).

        After construction, callers must populate the slot via
        :meth:`populate_from_snapshot` or :meth:`add_binding` before any
        rendering. The slot is empty (no wrappers, no active wrapper) until
        populated.
        """
        self._session = session
        self.name = name
        self._registry: EditorTypeRegistry = registry
        self._bindings: list[EditorWrapper] = []
        self._active: Optional[EditorWrapper] = None
        self._visible: bool = visible
        self._size: int = size
        self._area_panel_container: Optional[ui.tab_panels] = None
        self._area_parent_box: Optional[ui.element] = None
        self._panels: dict[str, ui.element] = {}
        self._drawn: set[str] = set()
        self._on_visibility_change = on_visibility_change
        self._bar_place = bar_place
        self._show_fold_toggle = show_fold_toggle
        self._bar_container: Optional[ui.element] = None
        self._fold_button: Optional[ui.element] = None
        self._tab_client: Any = None
        self._registry.add_batch_event_subscriber(self._on_lifecycle_events)

    _ORIENTATION: ClassVar[Literal["horizontal", "vertical"]]

    @property
    def _is_horizontal(self) -> bool:
        return self._ORIENTATION == "horizontal"

    # ------------------------------------------------------------------
    # Serialising / Deserialising Slots
    # ------------------------------------------------------------------

    def to_snapshot(self) -> dict:
        """Serialize current slot state to a plain dict for persistence.

        REQUIRED editors are excluded — they are always re-injected from the
        registry at construction and don't need persisting.
        """
        from haywire.ui.editor.identity import OpenBehavior

        editors = []
        for wrapper in self._bindings:
            if wrapper.editor_cls is None:
                # Wrapper has no class loaded (registry miss); skip persisting.
                continue
            opens = getattr(wrapper.editor_cls.class_identity, "opens", OpenBehavior.REQUIRED)
            if opens is OpenBehavior.REQUIRED:
                continue
            entry: dict = {"key": wrapper.editor_key}
            if wrapper._binding_id is not None:
                entry["binding_id"] = wrapper._binding_id
            label = wrapper.label or getattr(wrapper.editor_cls.class_identity, "label", wrapper.editor_key)
            entry["label"] = label
            editors.append(entry)

        return {
            "active_key": self.active_binding_id,
            "visible": self._visible,
            "size": self._size,
            "editors": editors,
        }

    def populate_from_snapshot(self, data: dict) -> None:
        """Populate the slot's wrappers from a snapshot dict.

        Injects all REQUIRED editors for this slot from the registry first,
        then appends snapshot entries (ON_PAYLOAD / ON_CONTEXT). Resolves
        the active wrapper from data["active_key"]. Unknown editor keys
        in the snapshot are skipped with a log warning.

        Idempotent only on a fresh slot — call exactly once after __init__,
        before any rendering.
        """
        from haywire.ui.editor.identity import OpenBehavior

        # REQUIRED editors are always re-injected from the registry.
        # No label set — bar resolves dynamically from class_identity.
        for key, editor_cls in self._registry.get_by_default_slot(self.name).items():
            opens = getattr(editor_cls.class_identity, "opens", OpenBehavior.REQUIRED)
            if opens is OpenBehavior.REQUIRED:
                self.add_binding(
                    editor_key=key,
                    editor_cls=editor_cls,
                    binding_id=None,
                    activate=False,
                )

        # Snapshot entries — custom labels (e.g. graph filenames) are
        # restored via direct field assignment on the returned wrapper.
        for entry in data.get("editors", []):
            key = entry.get("key")
            if not key:
                continue
            snapshot_cls = self._registry.get_by_key(key)
            if snapshot_cls is None:
                logger.warning(f"Slot '{self.name}': snapshot editor '{key}' not in registry — skipping")
                continue
            wrapper = self.add_binding(
                editor_key=key,
                editor_cls=snapshot_cls,
                binding_id=entry.get("binding_id"),
                activate=False,
            )
            snapshot_label = entry.get("label", "")
            if snapshot_label:
                wrapper.label = snapshot_label

        # Apply visibility/size from snapshot if present
        if "visible" in data:
            self._visible = bool(data["visible"])
        if "size" in data:
            self._size = int(data["size"])

        # Resolve initial active wrapper
        active_key = data.get("active_key")
        if active_key is not None:
            key, binding_id = EditorWrapper.split_id(active_key)
            match = self.find_binding(key, binding_id)
            if match is not None:
                self._active = match
                return
        if self._bindings:
            self._active = self._bindings[0]

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    def _create_content_box(self) -> "ui.element":
        """Create the slot's outer content box.

        Size axis and flex behaviour are derived from ``_ORIENTATION`` and
        ``show_fold_toggle``:
        * horizontal + fold  → fixed ``width`` from ``self._size`` (default 300)
        * vertical   + fold  → fixed ``height`` from ``self._size`` (default 200)
        * vertical   no fold → ``flex: 1`` (fills remaining vertical space)

        A border is added on the bar side for horizontal slots.
        """
        if self._is_horizontal:
            border = f"border-{self._bar_place}: 1px solid var(--hw-border);"
            col = (
                ui.column()
                .classes("gap-0")
                .style(
                    f"width: {self._size}px; min-width: 150px; height: 100%; "
                    f"overflow: hidden; background: var(--hw-bg-page); {border}"
                )
            )
        elif self._show_fold_toggle:
            col = (
                ui.column()
                .classes("gap-0")
                .style(f"height: {self._size}px; min-height: 0; width: 100%; overflow: hidden;")
            )
        else:
            col = ui.column().classes("gap-0 w-full").style("flex: 1; min-height: 0; overflow: hidden;")

        col._props["id"] = f"hw-slot-{self.name}"
        return col

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @property
    def active_binding(self) -> Optional[EditorWrapper]:
        """The wrapper currently shown in the area, or ``None`` if empty."""
        return self._active

    @property
    def active_key(self) -> Optional[str]:
        """Registry key of the active wrapper, or ``None`` if empty."""
        return self._active.editor_key if self._active is not None else None

    @property
    def active_binding_id(self) -> Optional[str]:
        """Full wrapper id (``editor_key`` or ``editor_key::binding_id``) of the active wrapper."""
        return self._active.editor_binding_id if self._active is not None else None

    @property
    def visible(self) -> bool:
        """Whether the area container is currently visible."""
        return self._visible

    @property
    def bindings(self) -> list[EditorWrapper]:
        """Read-only view of the wrappers list."""
        return list(self._bindings)

    def find_binding(self, editor_key: str, binding_id: Optional[str] = None) -> Optional[EditorWrapper]:
        """
        Lookup a wrapper by ``(editor_key, binding_id)``.

        An exact match (both fields equal) always wins. When ``binding_id`` is
        ``None`` and no exact match exists, falls back to the first wrapper
        whose ``editor_key`` matches — this preserves the behavior every
        pre-multi-instance call site relied on.

        Warns on ambiguous matches so the multi-instance migration surfaces
        any call site that still looks up by key alone when duplicates exist.
        """
        exact = [b for b in self._bindings if b.editor_key == editor_key and b._binding_id == binding_id]
        if exact:
            if len(exact) > 1:
                logger.warning(
                    f"Slot '{self.name}': {len(exact)} wrappers match "
                    f"({editor_key!r}, binding_id={binding_id!r}); returning the first."
                )
            return exact[0]

        if binding_id is None:
            fuzzy = [b for b in self._bindings if b.editor_key == editor_key]
            if not fuzzy:
                return None
            if len(fuzzy) > 1:
                logger.warning(
                    f"Slot '{self.name}': {len(fuzzy)} wrappers match key '{editor_key}' "
                    "(binding_id-less lookup); returning the first. "
                    "Pass binding_id to disambiguate once multi-instance tabs land."
                )
            return fuzzy[0]
        return None

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    @abstractmethod
    def render(self, parent: "ui.element") -> None:
        """Render this slot into ``parent``."""
        pass

    def _render_bar_row(self) -> None:
        """Render the tab bar"""
        border_style = (
            "border-top: 1px solid var(--hw-border); border-bottom: 1px solid var(--hw-border);"
            if self._bar_place == "bottom"
            else "border-bottom: 1px solid var(--hw-border);"
        )
        self._bar_container = (
            ui.row()
            .classes("w-full items-center gap-0 flex-shrink-0 hw-slot-bar")
            .style(f"background: var(--hw-bg-surface); {border_style} min-height: 36px;")
        )
        with self._bar_container:
            self._render_bar_contents()

    def _render_bar_column(self) -> None:
        """Render the icon bar (fold toggle + per-wrapper icon buttons)."""
        border_style = (
            "border-right: 1px solid var(--hw-border);"
            if self._bar_place == "left"
            else "border-left: 1px solid var(--hw-border);"
        )
        self._bar_container = (
            ui.column()
            .classes("items-center justify-start gap-1 py-2")
            .style(
                "width: 48px; min-width: 48px; height: 100%; "
                "background: var(--hw-bg-sidebar); " + border_style + " overflow: hidden;"
            )
        )
        with self._bar_container:
            self._render_bar_contents()

    @abstractmethod
    def _render_bar_contents(self) -> None:
        pass

    def _refresh_bar(self) -> None:
        """Clear + re-render the bar so tab highlight and chevron stay in sync."""
        if self._bar_container is None:
            return
        self._bar_container.clear()
        with self._bar_container:
            self._render_bar_contents()

    def _capture_tab_client(self) -> None:
        """Snapshot the current NiceGUI Client (one per browser tab).

        Called from :meth:`_render_area_contents`, which runs inside the
        ``@ui.page`` handler chain — the only moment ``ui.context.client``
        is guaranteed valid. The reference is later used by :meth:`_redraw`
        to re-enter the client's context when invoked from a background
        thread (hot-reload via the watchdog file watcher), so NiceGUI calls
        inside an editor's ``draw()`` — including elements created outside
        a ``with container:`` block such as ``ui.timer`` — can find the
        right slot stack instead of silently misbehaving.
        """
        try:
            self._tab_client = ui.context.client
        except Exception as exc:
            logger.debug(f"Slot '{self.name}': could not capture client context: {exc}")
            self._tab_client = None

    def _render_area_contents(self, parent: "ui.element") -> None:
        """
        Create the area container (a headless ``ui.tab_panels``) as a child
        of ``parent`` and draw the active wrapper's editor into its panel.

        Each wrapper gets its own ``ui.tab_panel`` keyed by ``binding_id``.
        All panels live in the DOM simultaneously; switching toggles
        visibility via ``set_value`` rather than clearing and re-rendering.

        Called once during the slot's initial render. The container and
        per-wrapper panels are stored so ``switch_to`` can change the
        active panel without rebuilding anything.
        """
        self._capture_tab_client()
        initial_value = self._active.editor_binding_id if self._active is not None else None
        with parent:
            self._area_panel_container = (
                ui.tab_panels(value=initial_value, animated=False)
                .props("keep-alive")
                .classes("hw-panel")
                .style(
                    "width: 100%; height: 100%; background: var(--hw-bg-page); color: var(--hw-text-body);"
                )
            )
        self._area_panel_container.set_visibility(self._visible)

        for wrapper in self._bindings:
            self._create_panel(wrapper)

        if self._active is None and self._area_panel_container is not None:
            with self._area_panel_container:
                ui.label("No editor").classes("hw-text-muted p-4")
        elif self._active is not None:
            # Reset _active so _activate sees the correct transition
            # semantics (not-active → active) and fires on_focus.
            initial = self._active
            self._active = None
            self._activate(initial)

    def _create_panel(self, wrapper: EditorWrapper) -> None:
        """Create a ``ui.tab_panel`` shell for ``wrapper``. Draw is deferred."""
        if self._area_panel_container is None:
            return
        with self._area_panel_container:
            panel = ui.tab_panel(wrapper.editor_binding_id).style("width: 100%; height: 100%; padding: 0;")
        self._panels[wrapper.editor_binding_id] = panel

    def _ensure_drawn(self, wrapper: EditorWrapper) -> None:
        """Trigger first-time draw of the wrapper's panel."""
        bid = wrapper.editor_binding_id
        if bid in self._drawn:
            return
        panel = self._panels.get(bid)
        if panel is None:
            return
        wrapper.draw(panel)
        self._drawn.add(bid)

    def _redraw(self, wrapper: EditorWrapper) -> None:
        """Full redraw of one wrapper's panel and the bar.

        ``wrapper.draw(panel)`` owns the clear — it calls ``panel.clear()``
        internally and handles dead-client RuntimeErrors. The slot resets
        the drawn-set so draw() runs unconditionally, then calls
        ``panel.update()`` to push the new DOM over the live websocket
        (without it the new content stays invisible until browser refresh
        — matters chiefly for hot-reload), and ``_refresh_bar()`` so any
        bar element derived from the editor class (label, icon, can_close
        policy) re-renders with the new class.

        When invoked from a background thread (hot-reload), enters the
        captured tab client's context first so NiceGUI element/timer
        creation inside the editor's draw() can find a valid slot stack.
        See :meth:`_capture_tab_client`.
        """
        bid = wrapper.editor_binding_id
        panel = self._panels.get(bid)
        if panel is None:
            return
        client_ctx = self._tab_client if self._tab_client is not None else nullcontext()
        with client_ctx:
            self._drawn.discard(bid)
            wrapper.draw(panel)
            self._drawn.add(bid)
            try:
                panel.update()
            except Exception as exc:
                logger.debug(f"Slot '{self.name}': panel.update() raised (dead client?): {exc}")
            self._refresh_bar()

    def _activate(self, wrapper: EditorWrapper) -> None:
        """Make ``wrapper`` the active one and run its on_focus hook."""
        self._active = wrapper
        wrapper.on_focus()
        self._ensure_drawn(wrapper)
        if self._area_panel_container is not None:
            self._area_panel_container.set_value(wrapper.editor_binding_id)

    # ------------------------------------------------------------------
    # Switching
    # ------------------------------------------------------------------

    def switch_to(self, editor_key: str, binding_id: Optional[str] = None) -> bool:
        """
        Change the active wrapper to the one matching ``(editor_key, binding_id)``.

        Re-renders the area on success. No-op if the target is already
        active. Logs a warning and returns ``False`` when no wrapper matches.

        Returns:
            ``True`` iff the active wrapper actually changed.
        """
        target = self.find_binding(editor_key, binding_id)
        if target is None:
            logger.warning(
                f"Slot '{self.name}': switch_to({editor_key!r}, "
                f"binding_id={binding_id!r}) — no matching wrapper"
            )
            return False

        if self._active is target:
            return False

        logger.info(f"Slot '{self.name}': switched to '{target.editor_binding_id}'")
        self._activate(target)
        return True

    def add_binding(
        self,
        editor_key: str,
        editor_cls: "type[BaseEditor]",
        binding_id: Optional[str] = None,
        activate: bool = False,
    ) -> EditorWrapper:
        """Construct a wrapper, attach the redraw callback, and add it.

        Single wrapper-construction path — used by both populate_from_snapshot
        and TabSlot.open_tab. Creates the panel if the area has been
        rendered. Activates the new wrapper if requested.

        The wrapper's ``label`` defaults to empty so the bar resolves it
        dynamically from ``editor_cls.class_identity.label``. Callers with
        a custom label (e.g. graph filename) assign ``wrapper.label = ...``
        on the returned wrapper.

        Returns the newly-constructed wrapper.
        """
        wrapper = EditorWrapper(
            editor_key=editor_key,
            editor_cls=editor_cls,
            registry=self._registry,
            session=self._session,
            binding_id=binding_id,
            slot=self,
        )
        wrapper.set_redraw_callback(lambda w: self._redraw(w))
        self._bindings.append(wrapper)
        if self._area_panel_container is not None:
            self._create_panel(wrapper)
        if activate:
            if self._active is None:
                self._activate(wrapper)
            else:
                self.switch_to(wrapper.editor_key, wrapper._binding_id)
        return wrapper

    # ------------------------------------------------------------------
    # Visibility
    # ------------------------------------------------------------------

    def set_visible(self, visible: bool) -> None:
        """Show or hide the area container. Idempotent.

        Fires :attr:`on_visibility_change` only on actual state transitions so
        subscribers (e.g. the shell's divider + toggle button) aren't
        thrashed by no-op calls.
        """
        if visible == self._visible:
            return
        self._visible = visible
        if self._area_parent_box is not None:
            self._area_parent_box.set_visibility(visible)
        if self._area_panel_container is not None:
            self._area_panel_container.set_visibility(visible)
        if self._on_visibility_change is not None:
            self._on_visibility_change(visible)
        self._refresh_bar()

    def set_size(self, size_px: int) -> None:
        """Store the drag-resize result in ``self._size``."""
        self._size = int(size_px)

    # ------------------------------------------------------------------
    # Orchestrator hook
    # ------------------------------------------------------------------

    def handle_signal(self, signal: "ContextSignal") -> None:
        """Dispatch a signal across this slot's wrappers.

        Two channels:

        * ``on_signal`` fires on EVERY wrapper, active or not. Lets
          editors run side effects (close stale tabs, mark themselves
          stale for next focus, clear caches) even while backgrounded.
          Per-wrapper exceptions are absorbed by the wrapper's own
          error capture — one editor's failure can't block sibling
          delivery.
        * ``redraw_on_signal`` fires only on the active wrapper. If it
          returns True the slot redraws (clear container, draw again).
          Backgrounded wrappers don't redraw — they catch up on
          ``on_focus`` when the user reactivates them.
        """
        for wrapper in self._bindings:
            wrapper.on_signal(signal)

        if self._active is None or self._area_panel_container is None:
            return
        if self._active.redraw_on_signal(signal):
            self._redraw(self._active)

    # ------------------------------------------------------------------
    # Mutation methods
    # ------------------------------------------------------------------

    def remove_binding(
        self,
        editor_key: str,
        binding_id: Optional[str] = None,
    ) -> "Optional[EditorWrapper]":
        """Remove a single wrapper matching (editor_key, binding_id).

        Calls wrapper.cleanup() which unsubscribes from the registry and
        tears down the editor instance.
        """
        target = self.find_binding(editor_key, binding_id)
        if target is None:
            return None

        target.set_redraw_callback(None)
        target.cleanup()

        panel = self._panels.pop(target.editor_binding_id, None)
        if panel is not None:
            panel.delete()
        self._drawn.discard(target.editor_binding_id)

        was_active = self._active is target
        idx = self._bindings.index(target)
        self._bindings.remove(target)

        if was_active:
            if self._bindings:
                next_idx = min(idx, len(self._bindings) - 1)
                sibling = self._bindings[next_idx]
                self._active = None
                self._activate(sibling)
            else:
                self._active = None
        return target

    def repayload_binding(
        self,
        editor_key: str,
        old_payload: Optional[str],
        new_payload: Optional[str],
    ) -> bool:
        """Re-key an existing wrapper's binding_id in place.

        Slot owns collision detection and DOM-side housekeeping; the
        wrapper just exposes its binding_id as a mutable field via repayload().
        """
        target = self.find_binding(editor_key, old_payload)
        if target is None:
            return False
        if target._binding_id == new_payload:
            return True

        new_id = f"{editor_key}::{new_payload}" if new_payload else editor_key
        if any(b is not target and b.editor_binding_id == new_id for b in self._bindings):
            logger.warning(f"Slot '{self.name}': repayload collision — '{new_id}' already exists")
            return False

        old_id = target.editor_binding_id
        # Mutate the wrapper's field directly — the public wrapper.repayload()
        # delegates back to this slot, which would cause unbounded recursion.
        target._binding_id = new_payload

        panel = self._panels.pop(old_id, None)
        if panel is not None:
            panel._props["name"] = new_id
            self._panels[new_id] = panel
        drawn = old_id in self._drawn
        self._drawn.discard(old_id)
        if drawn:
            self._drawn.add(new_id)
        if self._active is target and self._area_panel_container is not None:
            self._area_panel_container.set_value(new_id)
        return True

    # ------------------------------------------------------------------
    # Registry batch events
    # ------------------------------------------------------------------

    def _on_lifecycle_events(self, events: list[LifeCycleEvent]) -> None:
        """React to registry lifecycle events at the slot level.

        RELOADED is handled entirely at the wrapper level (class swap +
        redraw callback) — the slot doesn't act on it.
        """
        from haywire.ui.editor.identity import OpenBehavior

        bar_dirty = False

        for event in events:
            event_type = event.event_type

            if event_type == LifeCycleEventType.CLASS_ADDED:
                cls = event.affected_class
                if cls is None:
                    continue
                if getattr(cls.class_identity, "default_slot", None) != self.name:
                    continue
                opens = getattr(cls.class_identity, "opens", OpenBehavior.REQUIRED)
                if opens is not OpenBehavior.REQUIRED:
                    continue
                if self.find_binding(event.registry_key) is not None:
                    continue
                self.add_binding(editor_key=event.registry_key, editor_cls=cls)
                bar_dirty = True

            elif event_type == LifeCycleEventType.CLASS_REMOVED:
                # Iterate a snapshot of payloads since remove_binding mutates
                # self._bindings underneath us.
                payloads = [
                    wrapper._binding_id
                    for wrapper in self._bindings
                    if wrapper.editor_key == event.registry_key
                ]
                for binding_id in payloads:
                    removed = self.remove_binding(event.registry_key, binding_id=binding_id)
                    if removed is not None:
                        bar_dirty = True
                        logger.info(
                            f"Slot '{self.name}': removed wrapper '{removed.editor_binding_id}' "
                            f"(CLASS_REMOVED for '{event.registry_key}')"
                        )

        if bar_dirty:
            self._refresh_bar()

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup(self) -> None:
        """Tear down all wrappers. Idempotent."""
        try:
            self._registry.remove_batch_event_subscriber(self._on_lifecycle_events)
        except Exception as exc:
            logger.warning(f"Slot '{self.name}': failed to unsubscribe lifecycle listener: {exc}")
        for wrapper in list(self._bindings):
            wrapper.set_redraw_callback(None)
            wrapper.cleanup()
        self._bindings.clear()
        self._active = None
