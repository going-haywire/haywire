"""
EditorWrapper — complete lifecycle management for Haywire editors.

Mirrors NodeWrapper's philosophy: the wrapper owns the editor instance,
captures errors per phase into EditorWrapperState, self-subscribes to the
editor registry for hot-reload events, and is the source of truth for
"is this editor healthy?".
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Optional
from nicegui import ui

from haywire.core.errors.haywire_exception import HaywireException
from haywire.core.session.handlers import discover_handlers
from haywire.core.session.signals import Signal
from haywire.core.registry.lifecycle_event import LifeCycleEvent

from haywire.ui.editor.identity import OpenBehavior

if TYPE_CHECKING:
    from haywire.ui.editor.base import BaseEditor
    from haywire.ui.editor.registry import EditorTypeRegistry
    from haywire.core.session.session import Session
    from haywire.ui.app.slot import Slot

logger = logging.getLogger(__name__)


@dataclass
class EditorWrapperState:
    """Lifecycle state of an EditorWrapper and its editor instance.

    Mirrors the shape of NodeWrapperState but with editor-specific phases.
    Editors have no init/structural/test phases — only import, instantiate,
    and runtime (covering draw / on_focus and any @redraw_on / @react_on
    decorated handler calls).
    """

    is_imported: bool = True
    """True when the editor class is available in the registry."""

    error_import: Optional[HaywireException] = None
    """Error from registry lookup (CLASS_REMOVED, CLASS_NOT_FOUND, reload failure)."""

    error_instantiate: Optional[HaywireException] = None
    """Error from constructing the editor instance."""

    error_runtime: Optional[HaywireException] = None
    """Error from a runtime call (draw, on_focus, poll, redraw)."""

    is_dirty: bool = False
    """True when the editor's in-memory content differs from disk.

    Editors set this via :meth:`EditorWrapper.set_dirty` to drive the tab's
    dirty badge and the close-consent gate. Framework clears it automatically
    on hot-reload class swap (the new instance starts fresh)."""

    def is_valid(self) -> bool:
        """True iff the editor is imported and instantiation has not failed.

        Runtime errors do not invalidate the wrapper — the instance may still
        be usable on the next call (best-effort recovery).
        """
        return self.is_imported and self.error_instantiate is None

    def get_errors(self) -> Optional[list[HaywireException]]:
        """Return all populated error slots as a list, or None if no errors."""
        errors = []
        if self.error_import is not None:
            errors.append(self.error_import)
        if self.error_instantiate is not None:
            errors.append(self.error_instantiate)
        if self.error_runtime is not None:
            errors.append(self.error_runtime)
        return errors if errors else None

    def _clear_errors(self) -> None:
        """Clear runtime and instantiate errors. error_import is preserved
        and only cleared explicitly on successful hot-reload."""
        self.error_instantiate = None
        self.error_runtime = None


class EditorWrapper:
    """Manages the complete lifecycle of an editor instance.

    Responsibilities:
    - Self-subscribe to EditorTypeRegistry for per-key hot-reload events
    - Lazy-instantiate the editor class on first runtime call (Task 4)
    - Capture errors per phase (import/instantiate/runtime) into state
    - Notify the slot via redraw_callback when state changes require a redraw

    The wrapper holds a session reference for its lifetime — runtime methods
    read context via self._session.context internally so the slot can call
    them with minimal arguments.
    """

    def __init__(
        self,
        editor_key: str,
        editor_cls: "type[BaseEditor]",
        registry: "EditorTypeRegistry",
        session: "Session",
        binding_id: Optional[str] = None,
        label: str = "",
        slot: "Optional[Slot]" = None,
    ):
        """
        Args:
            editor_key: Registry key of the editor class.
            editor_cls: The editor class.
            registry: Editor registry for self-subscription.
            session: Owning session — held for the wrapper's lifetime.
            binding_id: Optional disambiguator (e.g., file path string for
                multi-instance editors). Stored as ``_binding_id``; the
                public ``binding_id`` property exposes the composite
                ``editor_key::disambiguator`` form. None for single-instance editors.
            label: Tab label for tabbed slots. Defaults to empty; resolved
                lazily at draw time when empty.
            slot: Owning slot — used by close/force_close/repayload to call
                back into slot mutators. None for detached wrappers (e.g.
                unit tests); those paths fall back to direct field updates.
        """
        self.editor_key = editor_key
        self.editor_cls = editor_cls
        self._binding_id = binding_id
        self.label = label
        self._registry = registry
        self._session: "Session" = session
        self._instance: "Optional[BaseEditor]" = None
        self._redraw_callback: Optional[Callable[["EditorWrapper"], None]] = None
        self._state: EditorWrapperState = EditorWrapperState()
        self._slot: "Optional[Slot]" = slot

        # Bus-subscription teardown handles for the editor's own
        # ``@redraw_on`` / ``@react_on`` decorated methods. Populated by
        # ``_subscribe_event_handlers`` after a successful ``_instantiate``;
        # drained by ``_unsubscribe_event_handlers`` on hot-reload and
        # ``cleanup``.
        #
        # Panel-driven event subscriptions (the union of
        # ``redraw_on=`` declarations across panels registered against
        # the editor's action Protocol) are NOT managed here. Editors
        # that host panels — currently only ``PropertiesEditor`` — own
        # their own panel-bus wiring and tear it down in their
        # ``cleanup``. Keeps the wrapper agnostic of the panel system.
        self._bus_unsubscribes: list[Callable[[], None]] = []

        # Cleanup flag — signals cleanup() has run; callers must not access
        # the wrapper's fields after that. Mirrors Settings._cleaned_up.
        self._cleaned_up: bool = False

        # Subscribe per-key for hot-reload events
        self._registry.add_event_subscriber(self.editor_key, self._on_lifecycle_event)

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def state(self) -> EditorWrapperState:
        return self._state

    @property
    def instance(self) -> "Optional[BaseEditor]":
        return self._instance

    @property
    def editor_binding_id(self) -> str:
        """Stable composite identity. ``editor_key`` for single-instance wrappers;
        ``editor_key::_binding_id`` when a ``_binding_id`` disambiguator is present."""
        return f"{self.editor_key}::{self._binding_id}" if self._binding_id else self.editor_key

    @staticmethod
    def split_id(tab_id: str) -> tuple[str, Optional[str]]:
        """Inverse of :attr:`binding_id`."""
        if "::" in tab_id:
            editor_key, _binding_id = tab_id.split("::", 1)
            return editor_key, _binding_id
        return tab_id, None

    @property
    def can_close(self) -> bool:
        """Whether the host UI should render a close button.

        REQUIRED editors have no close button; everything else is closeable.
        Missing identity defaults to closeable.
        """
        opens = getattr(self.editor_cls.class_identity, "opens", None)
        return opens is not OpenBehavior.REQUIRED

    # ------------------------------------------------------------------
    # Wiring
    # ------------------------------------------------------------------

    def set_redraw_callback(self, callback: Optional[Callable[["EditorWrapper"], None]]) -> None:
        """Set or clear the redraw callback.

        The slot calls this immediately after construction (in add_binding),
        and again with None during cleanup. The callback is invoked when
        wrapper state changes require a panel redraw — chiefly after a
        successful hot-reload that swaps the editor class.
        """
        self._redraw_callback = callback

    def redraw(self) -> None:
        """Ask the owning slot to redraw this wrapper.

        Public entry point used by the event-bus dispatch path: a closure
        wrapping an ``@redraw_on``-decorated handler calls this after the
        handler returns. No-op if the wrapper isn't attached to a slot
        (detached wrappers — e.g., unit tests — have no surface to
        redraw into).

        Slot semantics ensure the redraw is safe even when the wrapper
        is backgrounded — Quasar ``ui.tab_panels`` with keep-alive keeps
        the DOM mounted, so a redraw on a hidden tab is invisible work
        that pays off the moment the user focuses the tab.
        """
        if self._redraw_callback is not None:
            self._redraw_callback(self)

    def set_dirty(self, value: bool) -> None:
        """Mark the wrapped editor's content as dirty (or not).

        Called by editors when in-memory state diverges from disk. The
        tab bar reads ``state.is_dirty`` on its next render to show the
        unsaved-work badge — no immediate refresh is triggered (lazy
        update is acceptable since the next user action repaints the bar).
        """
        self._state.is_dirty = bool(value)

    # ------------------------------------------------------------------
    # Lifecycle event handling (placeholder — implemented in Task 5)
    # ------------------------------------------------------------------

    def _on_lifecycle_event(self, event: "LifeCycleEvent") -> None:
        """Handle a registry lifecycle event for our editor_key.

        Mirrors NodeWrapper._on_node_lifecycle_event:
        - Warning events (CLASS_REMOVED, CLASS_NOT_FOUND, reload failures):
          keep instance + class reference alive; populate error_import.
        - Successful events (CLASS_RELOADED, CLASS_ADDED with affected_class):
          swap class, clear instance so next draw lazy-instantiates with
          the new class, clear error_import.

        Always fires the redraw callback (if set) so the slot can repaint
        any state-dependent UI (e.g. tab badges, error placeholders).
        """
        logger.info(f"EditorWrapper '{self.editor_key}': lifecycle event {event.event_type.value}")

        if event.is_warning_event():
            if event.is_removal():
                self._state.error_import = HaywireException.create(
                    message=(
                        f"Editor '{self.editor_key}' has been removed from "
                        f"the registry and can no longer be used."
                    ),
                ).enrich(
                    operation="Editor Removed",
                    registry_key=self.editor_key,
                    module_name=getattr(event, "module_name", None),
                    library_identity=getattr(event, "library_identity", None),
                    suggestions=[
                        "Re-add the editor class to the registry.",
                    ],
                )
            else:
                self._state.error_import = event.error
            self._state.is_imported = False
            # Keep self._instance and self.editor_cls alive (NodeWrapper-style)
            if self._redraw_callback is not None:
                self._redraw_callback(self)
            return

        # Successful event with new class
        if event.affected_class is not None:
            self.editor_cls = event.affected_class
            self._state.is_imported = True
            self._state.error_import = None
            self._state.is_dirty = False
            # Drop bus subscriptions bound to the old instance before
            # tearing it down. The next _instantiate() re-subscribes the
            # new instance against the (possibly reloaded) class's freshly-
            # computed handler index.
            self._unsubscribe_event_handlers()
            # Clear instance so next draw lazy-instantiates with new class
            if self._instance is not None:
                try:
                    self._instance.cleanup()
                except Exception as exc:
                    logger.warning(
                        f"EditorWrapper '{self.editor_key}': instance.cleanup() raised during reload: {exc}"
                    )
                self._instance = None
            if self._redraw_callback is not None:
                self._redraw_callback(self)

    # ------------------------------------------------------------------
    # Build phase
    # ------------------------------------------------------------------

    def _instantiate(self) -> bool:
        """Lazy-instantiate the editor instance from editor_cls.

        Called internally on first runtime entry point (draw / on_focus /
        any decorated handler invocation). Captures construction errors
        into state.error_instantiate.

        On success, also subscribes the new instance's ``@redraw_on`` and
        ``@react_on`` decorated methods to the session's event bus. Those
        subscriptions live until the next hot-reload (which calls
        ``_unsubscribe_event_handlers`` before clearing ``_instance``) or
        wrapper cleanup.

        Returns:
            True on success, False if editor_cls is None or construction raised.
        """
        try:
            self._instance = self.editor_cls(self)
            self._state.error_instantiate = None
        except Exception as exc:
            error = HaywireException.from_exception(
                exception=exc,
                operation="Instantiate Editor",
                message=(
                    f"Failed to instantiate editor '{self.editor_key}' (class {self.editor_cls.__name__})"
                ),
            ).enrich(registry_key=self.editor_key)
            error.log(logger)
            self._state.error_instantiate = error
            self._instance = None
            return False

        self._subscribe_event_handlers()
        return True

    def _subscribe_event_handlers(self) -> None:
        """Subscribe the live editor instance's decorated methods to the session bus.

        Walks the editor class's handler index (cached on the class by
        :func:`haywire.core.session.handlers.discover_handlers`) and wires
        each ``(event_type, method)`` binding through a per-binding closure.
        The closure resolves the method by name on ``self._instance`` so
        subclass overrides hit; calls it with ``(ctx, event)``; and — if
        the binding's kind is ``"redraw_on"`` — calls ``self.redraw()``
        after the handler returns. Handler exceptions are captured into
        ``state.error_runtime``; the next handler still fires because
        :class:`SignalBus` is error-isolated per handler.

        Idempotent in the sense that callers may call it after a successful
        ``_instantiate``; not idempotent if called twice without a matching
        ``_unsubscribe_event_handlers`` (each call adds fresh subscriptions).
        """
        if self._instance is None:
            return
        index = discover_handlers(self.editor_cls)
        if not index:
            return
        bus_subscribe = self._session.subscribe
        ctx = self._session.context
        for event_type, bindings in index.items():
            for binding in bindings:
                unsub = bus_subscribe(
                    event_type,
                    self._make_handler_closure(binding.method_name, binding.kind, ctx),
                )
                self._bus_unsubscribes.append(unsub)

    def _make_handler_closure(
        self,
        method_name: str,
        kind: str,
        ctx: Any,
    ) -> Callable[[Signal], None]:
        """Build the per-binding closure registered on the bus.

        Pulled out as a method (not an inline ``def``) so each closure
        captures only ``method_name`` / ``kind`` — not whatever loop
        variables Python's late-binding would otherwise smuggle in from
        the caller. Each closure is its own subscription; ``ctx`` is read
        from the session at subscribe time so hot-reload picks up any new
        session-context wiring on re-subscription.
        """

        def _dispatch(event: Signal) -> None:
            instance = self._instance
            if instance is None:
                # Hot-reload between subscribe and publish — drop silently;
                # next instantiate will re-subscribe.
                return
            method = getattr(instance, method_name, None)
            if method is None:
                logger.warning(
                    f"EditorWrapper '{self.editor_key}': handler '{method_name}' "
                    f"vanished from instance before dispatch — skipping."
                )
                return
            try:
                method(ctx, event)
            except Exception as exc:
                self._state.error_runtime = HaywireException.from_exception(
                    exception=exc,
                    operation=f"Editor {kind}",
                    message=(f"{kind} handler '{method_name}' raised in editor '{self.editor_key}'"),
                ).enrich(registry_key=self.editor_key)
                # Do not redraw on failure: the redraw would re-run draw()
                # with stale or invalid state. Author sees the error via
                # the standard error placeholder on next natural redraw.
                return
            if kind == "redraw_on":
                self.redraw()

        return _dispatch

    def _unsubscribe_event_handlers(self) -> None:
        """Drop every decorator-derived bus subscription this wrapper owns.

        Idempotent. Called from the hot-reload path (before ``_instance``
        is cleared so the next ``_instantiate`` re-subscribes against the
        new class) and from ``cleanup``. Panel-driven subscriptions live
        on the editor instance (``self._instance.cleanup`` for
        panel-hosting editors); the wrapper doesn't touch them.
        """
        for unsub in self._bus_unsubscribes:
            try:
                unsub()
            except Exception as exc:
                logger.warning(f"EditorWrapper '{self.editor_key}': bus unsubscribe raised: {exc}")
        self._bus_unsubscribes.clear()

    # ------------------------------------------------------------------
    # Runtime entry points (called by Slot)
    # ------------------------------------------------------------------

    def draw(self, panel: ui.element) -> None:
        """Render the editor into ``panel``.

        Lazy-instantiates the editor if needed. If instantiation fails (or
        editor_cls is None), renders a minimal placeholder pointing the
        user to the error log; the rich error info is published via
        HaywireException's error queue.

        Runtime exceptions in the editor's draw() are captured into
        state.error_runtime; nothing is rendered after the exception.
        """
        try:
            panel.clear()
        except Exception as exc:
            logger.debug(f"EditorWrapper '{self.editor_key}': panel.clear() raised (dead client?): {exc}")
            return

        if self._instance is None:
            if not self._instantiate():
                with panel:
                    ui.label(f"'{self.editor_key}' unavailable — see error log").classes("hw-text-muted p-4")
                return

        try:
            assert self._instance is not None
            self._instance.draw(self._session.context, panel)
        except Exception as exc:
            error = HaywireException.from_exception(
                exception=exc,
                operation="Editor Draw",
                message=f"draw() raised in editor '{self.editor_key}'",
            ).enrich(registry_key=self.editor_key)
            error.log(logger)
            self._state.error_runtime = error

    def on_focus(self) -> None:
        """Notify the editor that it became active.

        Lazy-instantiates the editor if needed so first-activation always
        fires on_focus before draw — editors rely on this ordering to set
        up session context (e.g., a graph editor updates its
        library-supplied SessionState). No-op if instantiation fails
        (placeholder will render on draw).
        """
        if self._instance is None:
            if not self._instantiate():
                return
        try:
            assert self._instance is not None
            self._instance.on_focus(self._session.context)
        except Exception as exc:
            self._state.error_runtime = HaywireException.from_exception(
                exception=exc,
                operation="Editor Focus",
                message=f"on_focus() raised in editor '{self.editor_key}'",
            ).enrich(registry_key=self.editor_key)

    async def request_close(self) -> bool:
        """Ask the editor whether it allows closing.

        Returns True if the close should proceed, False if the editor
        vetoed (e.g. user cancelled at a save dialog).

        No-op-allows when there's no instance — a broken or unloaded
        wrapper has nothing to ask. If ``handle_close_request`` raises,
        the error is captured into ``state.error_runtime`` (consistent
        with draw / on_focus) and the close is allowed — better to lose
        veto than strand the user with an unclosable tab.
        """
        if self._instance is None:
            return True
        try:
            return bool(await self._instance.handle_close_request())
        except Exception as exc:
            self._state.error_runtime = HaywireException.from_exception(
                exception=exc,
                operation="Editor Close Request",
                message=f"handle_close_request() raised in editor '{self.editor_key}'",
            ).enrich(registry_key=self.editor_key)
            return True

    async def close(self) -> bool:
        """User-initiated close. Asks consent, closes if allowed.

        Returns True if the close happened, False if the editor vetoed.
        Use :meth:`force_close` for programmatic closes that should skip
        the consent gate.
        """
        if not await self.request_close():
            return False
        self.force_close()
        return True

    def force_close(self) -> None:
        """Programmatic close. Skips the consent gate.

        For editor self-initiated paths where the data source vanished
        or the editor has already decided. Calls into the slot directly
        — no-op if the wrapper isn't attached to a slot.
        """
        if self._slot is None:
            logger.debug(
                f"EditorWrapper '{self.editor_key}': force_close called but no slot attached; nothing to do."
            )
            return
        self._slot.close_binding(self)

    def repayload(self, new_payload: Optional[str], new_label: Optional[str] = None) -> None:
        """Update the disambiguator (and optional label) in place.

        When attached to a slot, delegates to ``slot.repayload`` for
        DOM-side housekeeping (panel name, set_value, bar refresh, collision
        detection). When detached (e.g. unit tests with no slot), updates
        the wrapper's fields directly so identity helpers like
        ``binding_id`` reflect the change.

        Editor authors call this from save-as / rename flows. The slot
        owns collision detection — if ``new_payload`` collides with another
        wrapper's binding_id, the slot logs a warning and the call is a
        no-op.
        """
        if self._slot is None:
            self._binding_id = new_payload
            if new_label is not None:
                self.label = new_label
            return
        self._slot.repayload(self, new_payload, new_label)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup(self) -> None:
        """Tear down the wrapper. Idempotent.

        Callers must not access the wrapper's fields after cleanup() returns —
        the contract is signalled by ``self._cleaned_up = True``.
        """
        if self._cleaned_up:
            return
        try:
            self._registry.remove_event_subscriber(self.editor_key, self._on_lifecycle_event)
        except Exception as exc:
            logger.warning(f"EditorWrapper '{self.editor_key}': failed to unsubscribe from registry: {exc}")
        # Drop bus subscriptions before tearing the instance down so the
        # closures we registered no longer reach into a half-dead wrapper.
        self._unsubscribe_event_handlers()
        if self._instance is not None:
            try:
                self._instance.cleanup()
            except Exception as exc:
                logger.warning(f"EditorWrapper '{self.editor_key}': instance.cleanup() raised: {exc}")
            self._instance = None
        self._redraw_callback = None
        self._slot = None
        self._cleaned_up = True
