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

from haywire.core.errors.haywire_exception import HaywireException
from nicegui import ui

if TYPE_CHECKING:
    from haywire.ui.editor.base import BaseEditor
    from haywire.ui.editor.registry import EditorTypeRegistry
    from haywire.core.session.session import Session
    from haywire.ui.app.slot import Slot
    from haywire.core.registry.lifecycle_event import LifeCycleEvent
    from nicegui.element import Element

logger = logging.getLogger(__name__)


@dataclass
class EditorWrapperState:
    """Lifecycle state of an EditorWrapper and its editor instance.

    Mirrors the shape of NodeWrapperState but with editor-specific phases.
    Editors have no init/structural/test phases — only import, instantiate,
    and runtime (covering draw/on_focus/poll).
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
        editor_cls: "Optional[type[BaseEditor]]",
        registry: "EditorTypeRegistry",
        session: "Session",
        payload: Optional[str] = None,
        label: str = "",
        slot: "Optional[Slot]" = None,
    ):
        """
        Args:
            editor_key: Registry key of the editor class.
            editor_cls: The editor class. None when the registry has no entry
                for editor_key — error_import is populated and the wrapper
                renders a placeholder until a successful hot-reload arrives.
            registry: Editor registry for self-subscription.
            session: Owning session — held for the wrapper's lifetime.
            payload: Optional disambiguator (e.g., file path string for
                multi-instance editors). None for single-instance editors.
            label: Tab label for tabbed slots. Defaults to empty; resolved
                lazily at draw time when empty.
            slot: Owning slot — used by close/force_close/repayload to call
                back into slot mutators. None for detached wrappers (e.g.
                unit tests); those paths fall back to direct field updates.
        """
        self.editor_key = editor_key
        self.editor_cls = editor_cls
        self.payload = payload
        self.label = label
        self._registry = registry
        self._session: "Session" = session
        self._instance: "Optional[BaseEditor]" = None
        self._redraw_callback: Optional[Callable[["EditorWrapper"], None]] = None
        self._state: EditorWrapperState = EditorWrapperState()
        self._slot: "Optional[Slot]" = slot

        # Cleanup flag — signals cleanup() has run; callers must not access
        # the wrapper's fields after that. Mirrors Settings._cleaned_up.
        self._cleaned_up: bool = False

        # Subscribe per-key for hot-reload events
        self._registry.add_event_subscriber(self.editor_key, self._on_lifecycle_event)

        # Eager import phase: validate the class exists
        if self.editor_cls is None:
            self._state.is_imported = False
            self._state.error_import = HaywireException.create(
                f"Editor class '{self.editor_key}' is not available in the registry."
            ).enrich(
                operation="Editor Import",
                category="Editor Not Found",
                registry_key=self.editor_key,
                suggestions=[
                    "Ensure the providing library is installed and loaded.",
                    "Check for typos in the editor registry key.",
                ],
            )

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
    def binding_id(self) -> str:
        """Stable identity. ``editor_key`` for single-instance wrappers;
        ``editor_key::payload`` when a payload is present."""
        return f"{self.editor_key}::{self.payload}" if self.payload else self.editor_key

    @staticmethod
    def split_id(tab_id: str) -> tuple[str, Optional[str]]:
        """Inverse of :attr:`binding_id`."""
        if "::" in tab_id:
            editor_key, payload = tab_id.split("::", 1)
            return editor_key, payload
        return tab_id, None

    @property
    def can_close(self) -> bool:
        """Whether the host UI should render a close button.

        REQUIRED editors have no close button; everything else is closeable.
        Missing identity defaults to closeable. A wrapper with no editor_cls
        (broken state) is closeable so the user can dismiss it.
        """
        from haywire.ui.editor.identity import OpenBehavior

        if self.editor_cls is None:
            return True
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

        Called internally on first runtime entry point (draw/on_focus/poll)
        in Task 6. Captures construction errors into state.error_instantiate.

        Returns:
            True on success, False if editor_cls is None or construction raised.
        """
        if self.editor_cls is None:
            return False
        try:
            self._instance = self.editor_cls()
            self._instance.wrapper = self
            self._state.error_instantiate = None
            return True
        except Exception as exc:
            self._state.error_instantiate = HaywireException.from_exception(
                exception=exc,
                operation="Instantiate Editor",
                message=(
                    f"Failed to instantiate editor '{self.editor_key}' (class {self.editor_cls.__name__})"
                ),
            ).enrich(registry_key=self.editor_key)
            self._instance = None
            return False

    # ------------------------------------------------------------------
    # Runtime entry points (called by Slot)
    # ------------------------------------------------------------------

    def draw(self, panel: "Element") -> None:
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
            self._state.error_runtime = HaywireException.from_exception(
                exception=exc,
                operation="Editor Draw",
                message=f"draw() raised in editor '{self.editor_key}'",
            ).enrich(registry_key=self.editor_key)

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

    def poll(self, event: Any) -> bool:
        """Ask the editor whether it needs a redraw.

        Returns False if no instance exists or poll raised. Errors are
        captured into state.error_runtime.
        """
        if self._instance is None:
            return False
        try:
            return bool(self._instance.poll(self._session.context, event))
        except Exception as exc:
            self._state.error_runtime = HaywireException.from_exception(
                exception=exc,
                operation="Editor Poll",
                message=f"poll() raised in editor '{self.editor_key}'",
            ).enrich(registry_key=self.editor_key)
            return False

    async def request_close(self) -> bool:
        """Ask the editor whether it allows closing.

        Returns True if the close should proceed, False if the editor
        vetoed (e.g. user cancelled at a save dialog).

        No-op-allows when there's no instance — a broken or unloaded
        wrapper has nothing to ask. If ``handle_close_request`` raises,
        the error is captured into ``state.error_runtime`` (consistent
        with draw/on_focus/poll) and the close is allowed — better to
        lose veto than strand the user with an unclosable tab.
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
        — no-op if the wrapper isn't attached to a slot. The slot is
        expected to be a TabSlot (or duck-typed equivalent providing
        ``close_tab``); non-tab slots have no closable tab semantics.
        """
        if self._slot is None:
            logger.debug(
                f"EditorWrapper '{self.editor_key}': force_close called but no slot attached; nothing to do."
            )
            return
        self._slot.close_tab(self.editor_key, self.payload)  # type: ignore[attr-defined]

    def repayload(self, new_payload: Optional[str], new_label: Optional[str] = None) -> None:
        """Update the payload (and optional label) in place.

        When attached to a TabSlot, delegates to ``slot.repayload_tab`` for
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
            self.payload = new_payload
            if new_label is not None:
                self.label = new_label
            return
        self._slot.repayload_tab(  # type: ignore[attr-defined]
            self.editor_key,
            self.payload,
            new_payload,
            new_label,
        )

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
        if self._instance is not None:
            try:
                self._instance.cleanup()
            except Exception as exc:
                logger.warning(f"EditorWrapper '{self.editor_key}': instance.cleanup() raised: {exc}")
            self._instance = None
        self._redraw_callback = None
        self._slot = None
        self._cleaned_up = True
