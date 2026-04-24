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
* The shell calls ``slot.render(parent)`` (or ``slot._render_area`` directly
  at existing call sites until Task 10) to mount each slot's container at
  the right spot in the layout.
* On user click (bar) or ``reveal_editor`` event, the shell calls
  ``slot.switch_to(key)`` and does its own follow-up (bar refresh,
  WORKSPACE_CHANGED broadcast). The slot handles everything inside its
  area — container clear, instance lazy-create, draw.
* On every ``ContextChangedEvent``, the shell calls
  ``slot.handle_context_event(event)`` on each slot to run the poll/draw
  gate on the active binding.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import logging
from dataclasses import dataclass
from typing import Any, Callable, ClassVar, Literal, Optional, TYPE_CHECKING

from nicegui import ui

from haywire.ui.editor.registry import EditorTypeRegistry

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

    @staticmethod
    def split_id(tab_id: str) -> tuple[str, Optional[str]]:
        """Inverse of :attr:`binding_id`.

        Decompose ``editor_key`` (single-instance) or ``editor_key::payload``
        (multi-instance) back into its components.
        """
        if "::" in tab_id:
            editor_key, payload = tab_id.split("::", 1)
            return editor_key, payload
        return tab_id, None

    @property
    def can_close(self) -> bool:
        """Whether the host UI should render a close button for this binding.

        Tabs whose editor class declares ``opens=REQUIRED`` are always-present
        singletons and have no close button. All other ``OpenBehavior`` values
        are closeable. Missing ``opens`` defaults to closeable (permissive —
        better to let the user remove a tab than strand it).
        """
        from haywire.ui.editor.identity import OpenBehavior

        opens = getattr(self.editor_cls.class_identity, "opens", None)
        return opens is not OpenBehavior.REQUIRED

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


class Slot(ABC):
    """
    Runtime manager for one of the four shell slots.

    Owns its editor bindings, the currently active binding, its area
    container, and the slot's visibility state. Provides the switch,
    reveal, and poll/draw entry points used by the AppShell.

    Lifecycle:
        * Constructed by the shell once per slot, seeded with the list of
          bindings appropriate for that slot (registry-derived for
          left/right; workspace-tabs-derived for main/bottom).
        * ``_render_area(parent)`` creates the slot's area container as a
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
        registry: EditorTypeRegistry,
        initial_bindings: list[EditorBinding],
        active_key: Optional[str] = None,
        slot_state: Optional[Any] = None,
        on_visibility_change: Optional[Callable[[bool], None]] = None,
        bar_place: Literal["left", "right", "top", "bottom"] = "left",
        show_fold_toggle: bool = False,
        persist_workspace: Optional[Callable[[], None]] = None,
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
            active_key: ``editor_key`` or composite ``editor_key::payload``
                of the initially active binding. A ``::``-containing value is
                automatically split so callers never need to call
                :meth:`EditorBinding.split_id` before construction. If the key
                has no matching binding, the first binding (if any) becomes
                active; if there are no bindings, the slot is inactive.
            slot_state: Reference to the workspace-state sub-object for this
                slot (``SlotState`` for left/right, ``MainSlotState`` /
                ``BottomSlotState`` for main/bottom). When set, the slot
                mirrors its active key / size / visibility onto this object
                so the persisted workspace tracks live state automatically.
                May be ``None`` in tests that don't care about persistence.
            on_visibility_change: Optional callback fired when the slot's
                visibility changes. Receives the new visibility state (bool).
                Not fired on idempotent calls (when the state doesn't change).
            bar_place: Where the bar renders relative to the area.
                ``"left"``/``"right"`` for icon slots (horizontal layout);
                ``"top"``/``"bottom"`` for tab slots (vertical layout).
            show_fold_toggle: Render a fold toggle on the bar. When ``True``
                the content box uses a fixed pixel size (resizable/foldable);
                when ``False`` it fills remaining space with ``flex: 1``.
            persist_workspace: TabSlot-only — callback invoked after tab
                mutations so the host can persist workspace state. Ignored
                by IconSlot.
        """
        self._session = session
        self.name = name
        self._registry: EditorTypeRegistry = registry
        self._bindings: list[EditorBinding] = list(initial_bindings)
        self._active: Optional[EditorBinding] = self._resolve_initial_active(active_key)
        self._visible: bool = True
        self._area_panel_container: Optional[ui.element] = None
        self._area_parent_box: Optional[ui.element] = None
        self._panels: dict[str, ui.element] = {}
        self._drawn: set[str] = set()
        self._slot_state = slot_state
        self._on_visibility_change = on_visibility_change
        self._bar_place = bar_place
        self._show_fold_toggle = show_fold_toggle
        self._persist_workspace = persist_workspace or (lambda: None)

        self._mirror_active_into_state()
        self._registry.add_batch_event_subscriber(self._on_editor_lifecycle)

        self._bar_container: Optional[ui.element] = None
        self._fold_button: Optional[ui.element] = None

    _ORIENTATION: ClassVar[Literal["horizontal", "vertical"]]

    @property
    def _is_horizontal(self) -> bool:
        return self._ORIENTATION == "horizontal"

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    def _resolve_initial_active(self, active_key: Optional[str]) -> Optional[EditorBinding]:
        """Pick the starting active binding from ``active_key`` or the first binding.

        ``active_key`` may be a plain ``editor_key`` or a composite
        ``editor_key::payload``; the ``::`` split is handled here so callers
        never need to do it before construction.
        """
        if active_key is not None:
            key, payload = EditorBinding.split_id(active_key)
            match = self.find_binding(key, payload)
            if match is not None:
                return match
        return self._bindings[0] if self._bindings else None

    def _mirror_active_into_state(self) -> None:
        """Reconcile the workspace slot_state's ``active_tab_key`` with the slot's resolved binding.

        A persisted key may point to a now-unregistered editor class;
        ``_resolve_initial_active`` silently falls back to the first binding.
        Without this mirror, the bar highlight would still read the stale key.
        No-op when ``slot_state`` is ``None`` (test mode).
        """
        if self._slot_state is None:
            return
        new_key = self._active.binding_id if self._active is not None else None
        # Tabbed slots persist composite tab_id; icon slots persist plain editor_key.
        # Decide by peeking at the slot_state dataclass via hasattr(tabs).
        if hasattr(self._slot_state, "tabs"):
            self._slot_state.active_tab_key = new_key
        else:
            self._slot_state.active_tab_key = self._active.editor_key if self._active else None

    def _create_content_box(self) -> "ui.element":
        """Create the slot's outer content box.

        Size axis and flex behaviour are derived from ``_ORIENTATION`` and
        ``show_fold_toggle``:
        * horizontal + fold  → fixed ``width`` from ``slot_state.size`` (default 300)
        * vertical   + fold  → fixed ``height`` from ``slot_state.size`` (default 200)
        * vertical   no fold → ``flex: 1`` (fills remaining vertical space)

        A border is added on the bar side for horizontal slots.
        """
        size = getattr(self._slot_state, "size", None) if self._slot_state is not None else None

        if self._is_horizontal:
            size = size if size is not None else 300
            border = f"border-{self._bar_place}: 1px solid var(--hw-border);"
            col = (
                ui.column()
                .classes("gap-0")
                .style(
                    f"width: {size}px; min-width: 150px; height: 100%; "
                    f"overflow: hidden; background: var(--hw-bg-page); {border}"
                )
            )
        elif self._show_fold_toggle:
            size = size if size is not None else 200
            col = (
                ui.column()
                .classes("gap-0")
                .style(f"height: {size}px; min-height: 0; width: 100%; overflow: hidden;")
            )
        else:
            col = ui.column().classes("gap-0 w-full").style("flex: 1; min-height: 0; overflow: hidden;")

        col._props["id"] = f"hw-slot-{self.name}"
        return col

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
        """Render the icon bar (fold toggle + per-binding icon buttons)."""
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

    def _render_area_contents(self, parent: "ui.element") -> None:
        """
        Create the area container (a headless ``ui.tab_panels``) as a child
        of ``parent`` and draw the active binding's editor into its panel.

        Each binding gets its own ``ui.tab_panel`` keyed by ``editor_key``.
        All panels live in the DOM simultaneously; switching toggles
        visibility via ``set_value`` rather than clearing and re-rendering.

        Called once during the slot's initial render. The container and
        per-binding panels are stored so ``switch_to`` can change the
        active panel without rebuilding anything.
        """
        initial_value = self._active.binding_id if self._active is not None else None
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

        for binding in self._bindings:
            self._create_panel(binding)

        if self._active is None and self._area_panel_container is not None:
            with self._area_panel_container:
                ui.label("No editor").classes("hw-text-muted p-4")
        elif self._active is not None:
            # Reset _active so _activate sees the correct transition
            # semantics (not-active → active) and fires on_focus.
            initial = self._active
            self._active = None
            self._activate(initial)

    def _create_panel(self, binding: EditorBinding) -> None:
        """Create a ``ui.tab_panel`` shell for ``binding``. Draw is deferred."""
        if self._area_panel_container is None:
            return
        with self._area_panel_container:
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
        """Full redraw of one binding's panel (clear + draw).

        Hot-reload fires this across every live ``AppShell`` — including
        shells whose browser client has already disconnected. NiceGUI raises
        ``RuntimeError`` when we touch elements owned by a dead client, so
        we drop the panel reference on that error rather than letting the
        reload propagate.
        """
        bid = binding.binding_id
        panel = self._panels.get(bid)
        if panel is None:
            return
        try:
            panel.clear()
        except RuntimeError as exc:
            logger.debug(f"Slot '{self.name}': skipping redraw of '{bid}' on dead client: {exc}")
            self._panels.pop(bid, None)
            self._drawn.discard(bid)
            return
        self._drawn.discard(bid)
        self._ensure_drawn(binding)

    def _activate(self, binding: EditorBinding) -> None:
        """Make ``binding`` the active one and run its on_focus hook.

        Single choke point for "binding transitions to active". Used by:

        * ``_render_area`` — on first render of the slot, for the initially
          active binding picked by ``_resolve_initial_active``.
        * ``switch_to`` — when the user clicks a different tab or a reveal
          swaps the active binding.
        * ``add_binding(activate=True)`` — when a new multi-instance tab is
          opened and made active in one step.

        Order of operations:
          1. Mark ``self._active = binding``.
          2. Ensure the instance exists (lazy-create) and call its
             ``on_focus(context)`` hook. Runs before ``draw`` so any context
             mutation the hook performs is visible to ``draw``.
          3. ``_ensure_drawn(binding)`` — first-time draw if needed.
          4. Flip the tab_panels visibility via ``set_value``.

        Exceptions raised by ``on_focus`` are logged and swallowed so a
        buggy editor can't wedge the slot.
        """
        self._active = binding
        instance = binding.ensure_instance()
        try:
            instance.on_focus(self._session.context)
        except Exception as exc:
            logger.error(f"Slot '{self.name}': on_focus error for '{binding.binding_id}': {exc}")
        self._ensure_drawn(binding)
        if self._area_panel_container is not None:
            self._area_panel_container.set_value(binding.binding_id)
        self._mirror_active_into_state()

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

        logger.info(f"Slot '{self.name}': switched to '{target.binding_id}'")
        self._activate(target)
        return True

    def add_binding(self, binding: EditorBinding, activate: bool = False) -> None:
        """
        Append a new binding to the slot, creating its panel if the area
        has already been rendered.

        Used by main/bottom when a workspace tab opens at runtime (the
        left/right slots are seeded from the registry at construction).
        """
        self._bindings.append(binding)
        if self._area_panel_container is not None:
            self._create_panel(binding)
        if activate:
            if self._active is None:
                self._activate(binding)
            else:
                self.switch_to(binding.editor_key, binding.payload)

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
        if self._slot_state is not None and hasattr(self._slot_state, "visible"):
            self._slot_state.visible = visible
        if self._on_visibility_change is not None:
            self._on_visibility_change(visible)

    def set_size(self, size_px: int) -> None:
        """Persist a drag-resize result into ``slot_state.size``.

        No-op when the slot_state has no ``size`` field (e.g. ``MainSlotState``
        which is the flex:1 filler and never stores an explicit size).
        """
        if self._slot_state is not None and hasattr(self._slot_state, "size"):
            self._slot_state.size = int(size_px)

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
        if self._active is None or self._area_panel_container is None:
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
                sibling = self._bindings[next_idx]
                # Reset _active so _activate sees a real transition
                # (not-active → active) and fires on_focus on the sibling.
                self._active = None
                self._activate(sibling)
            else:
                self._active = None
                self._mirror_active_into_state()
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
        save-as moved an entry from ``__unsaved_3__`` to an absolute path). The
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
        if self._active is target and self._area_panel_container is not None:
            self._area_panel_container.set_value(new_id)
        self._mirror_active_into_state()
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
            if self._bindings:
                sibling = self._bindings[0]
                # Reset _active so _activate sees a real transition
                # (not-active → active) and fires on_focus on the sibling.
                self._active = None
                self._activate(sibling)
            else:
                self._active = None
                self._mirror_active_into_state()

    # ------------------------------------------------------------------
    # Registry hot-reload (self-owned)
    # ------------------------------------------------------------------

    def _on_editor_lifecycle(self, events: list) -> None:
        """Apply hot-reload events to bindings owned by this slot.

        Delegates to :meth:`replace_class` / :meth:`remove_bindings`; filters
        out events for ``editor_key``s not present in this slot.
        """
        from haywire.core.registry.lifecycle_event import LifeCycleEventType

        def _cleanup(instance: "BaseEditor") -> None:
            try:
                instance.cleanup()
            except Exception as exc:
                logger.warning(f"Slot '{self.name}': cleanup error: {exc}")

        owned_keys = {b.editor_key for b in self._bindings}
        for evt in events:
            if evt.registry_key not in owned_keys:
                continue
            if evt.event_type == LifeCycleEventType.CLASS_RELOADED and evt.affected_class is not None:
                self.replace_class(evt.registry_key, evt.affected_class, cleanup_old=_cleanup)
            elif evt.event_type == LifeCycleEventType.CLASS_REMOVED:
                self.remove_bindings(evt.registry_key, cleanup=_cleanup)

    def teardown(self) -> None:
        """Detach from the registry. Safe to call more than once.

        Called by the shell when the session ends so the slot doesn't leak
        a subscriber reference into the registry across sessions.
        """
        if self._registry is not None:
            try:
                self._registry.remove_batch_event_subscriber(self._on_editor_lifecycle)
            except Exception:
                pass
            self._registry = None
