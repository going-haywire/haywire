# packages/haywire-core/src/haywire/ui/editor_framework/base.py
"""
Abstract base class for all Haywire editor types.

Editors follow a poll/draw lifecycle managed by an orchestrator (AppShell):

    1. On first assignment to a slot, the orchestrator calls draw()
       directly — no poll.
    2. On every ContextSignal, the orchestrator calls poll(). If it
       returns True the orchestrator clears the container and calls draw().
    3. On hot-reload of the editor class, the orchestrator evicts the cached
       instance, calls cleanup(), and re-instantiates + draw() if visible.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar, Optional

from .identity import EditorIdentity

if TYPE_CHECKING:
    from haywire.ui.editor.wrapper import EditorWrapper
    from haywire.core.session.context import SessionContext
    from haywire.core.session.context_signals import ContextSignal
    from nicegui.element import Element


class BaseEditor(ABC):
    """
    Abstract base class for all editor types.

    An editor is a self-contained UI module that renders into a slot
    of the workspace layout. Editor instances are lazily created and
    cached — when two browser windows are open, each session has its
    own editor instances.

    Subclasses must implement:
        - draw(context, container): Build the editor UI into the given container.

    Subclasses may override:
        - poll(context, signal): Return True when a full redraw is needed.
        - on_focus(context): Called when this wrapper becomes active.
        - cleanup(): Release resources when permanently removed.
        - get_tab_label(context): Dynamic tab label for tabbed slots.

    Class attributes (set by @editor decorator):
        - class_identity: EditorIdentity with registry_key, label, icon, default_slot.
        - class_library: LibraryIdentity of the owning library (None for builtins).
    """

    class_identity: ClassVar[EditorIdentity]

    #: The runtime wrapper this instance belongs to. Assigned by
    #: :meth:`EditorWrapper._instantiate` right after construction so the
    #: editor can read its own ``editor_key`` / ``payload`` at any point
    #: (draw, poll, event handlers) without the slot having to pass it
    #: through each entry point. Stays ``None`` only for instances created
    #: outside a wrapper (e.g. in direct unit tests).
    wrapper: "Optional[EditorWrapper]" = None

    def poll(self, context: "SessionContext", signal: "ContextSignal") -> bool:
        """
        Determine whether this editor needs a full redraw.

        Called by the orchestrator on every ContextSignal. If this
        returns True the orchestrator will clear the container and call
        draw(). The default implementation returns False (never redraw).

        Subclasses filter with plain ``isinstance(signal, SignalType)`` —
        no framework-side identity machinery (Q3A).

        Args:
            context: The current session context.
            signal: The ContextSignal describing what moved in the session.

        Returns:
            True if the editor needs a full redraw, False otherwise.
        """
        return False

    def on_focus(self, context: "SessionContext") -> None:
        """
        Called when this wrapper transitions from not-active to active
        in its slot.

        Fires on: initial slot render (first active wrapper), Slot.switch_to
        (programmatic reveal or user tab click), Slot.add_binding(activate=True).
        Does NOT fire when re-selecting the already-active wrapper.

        Runs before draw() on the newly-activated wrapper, so any context
        mutations this hook performs are visible to that draw() call and
        to any events this hook broadcasts.

        The default implementation is a no-op. Editors that own session
        state (via a library-supplied SessionState — e.g., a graph editor
        whose library owns an ``active_graph`` field on its SessionState)
        override this to update the state and broadcast the corresponding
        event.

        Read ``self.wrapper.payload`` for this instance's identity.

        Args:
            context: The current session context.
        """
        pass

    @abstractmethod
    def draw(self, context: "SessionContext", container: "Element") -> None:
        """
        Build the editor UI into the given NiceGUI container element.

        The orchestrator clears the container before calling this method.
        Called once on first assignment to a slot, and again whenever
        poll() returns True.

        Multi-instance editors (e.g. GraphEditor) read their own identity
        from :attr:`wrapper` (set by the slot at instance-creation time);
        the ``wrapper`` carries the ``editor_key`` and ``payload`` that
        disambiguate this instance from other tabs of the same class.

        Args:
            context: The current session context.
            container: NiceGUI parent element (cleared by orchestrator).
        """
        ...

    def cleanup(self) -> None:
        """
        Optional cleanup when the editor is permanently removed.
        Override to release resources, cancel timers, etc.
        """
        pass

    async def handle_close_request(self) -> bool:
        """Decide whether to allow this editor's tab to close.

        Called when the user clicks the X on the tab (the slot awaits this
        before removing the wrapper). Override to show a save / discard /
        cancel dialog when the editor has unsaved content; await the user's
        choice; return True to allow the close, False to veto.

        The default implementation always allows close. Editors that don't
        track dirty state can ignore this method entirely.

        Read ``self.wrapper.state.is_dirty`` to check whether to prompt.
        Editors are responsible for their own dialog UI — the framework
        provides the gate but no default dialog.
        """
        return True

    def get_tab_label(self, context: "SessionContext") -> str:
        """
        Return the label to show in a tab header (for tabbed slots — main, bottom).
        Defaults to class_identity.label. Override for dynamic labels (e.g., graph name).
        """
        return self.class_identity.label
