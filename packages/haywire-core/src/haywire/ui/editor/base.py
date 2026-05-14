# packages/haywire-core/src/haywire/ui/editor_framework/base.py
"""
Abstract base class for all Haywire editor types.

Editors react to ContextSignals through the typed event bus: methods
decorated with ``@redraw_on(...)`` / ``@react_on(...)`` from
:mod:`haywire.core.session.handlers` are auto-subscribed at editor
instantiation. ``@redraw_on`` triggers ``wrapper.redraw()`` after the
handler returns; ``@react_on`` is the pure side-effect channel.

Lifecycle outside the bus channel:

    * On first assignment to a slot, the orchestrator calls draw()
      directly — no handler runs first.
    * On hot-reload of the editor class, the orchestrator evicts the
      cached instance, calls cleanup(), and re-instantiates + draw() if
      visible.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

from .identity import EditorIdentity

if TYPE_CHECKING:
    from haywire.ui.editor.wrapper import EditorWrapper
    from haywire.core.session.context import SessionContext
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
        - on_focus(context): Called when this wrapper becomes active.
        - cleanup(): Release resources when permanently removed.
        - get_tab_label(context): Dynamic tab label for tabbed slots.

    Event-bus subscriptions are declared per-method via
    ``@redraw_on(...)`` / ``@react_on(...)`` decorators from
    :mod:`haywire.core.session.handlers`. The framework auto-subscribes
    decorated methods at editor instantiation, and additionally
    subscribes the editor to any ``redraw_on=`` events declared by
    panels whose action contract this editor satisfies — resolved via
    the session's ``context.app.library_service.get_panel_registry()``.
    See ``internals/speculatives/event_bus_redesign.md``.

    Class attributes (set by @editor decorator):
        - class_identity: EditorIdentity with registry_key, label, icon, default_slot.
        - class_library: LibraryIdentity of the owning library (None for builtins).
    """

    class_identity: ClassVar[EditorIdentity]

    def __init__(self, wrapper: "EditorWrapper") -> None:
        """Construct the editor and bind it to its runtime wrapper.

        The wrapper is the editor's gateway to identity (``editor_key`` /
        ``binding_id``), session state, and slot mutators (``force_close``,
        ``repayload``). Always set; the framework constructs editors via
        :meth:`EditorWrapper._instantiate`, which passes ``self`` here.

        Subclasses overriding ``__init__`` must accept ``wrapper`` and call
        ``super().__init__(wrapper)``.
        """
        self.wrapper: "EditorWrapper" = wrapper

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

        Read ``self.wrapper.binding_id`` for this instance's identity.

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
        the ``wrapper`` carries the ``editor_key`` and ``binding_id`` that
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
