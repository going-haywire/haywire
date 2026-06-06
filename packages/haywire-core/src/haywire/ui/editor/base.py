# packages/haywire-core/src/haywire/ui/editor_framework/base.py
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar, Literal

from nicegui import ui

from .identity import EditorIdentity

if TYPE_CHECKING:
    from haywire.ui.editor.wrapper import EditorWrapper
    from haywire.core.session.context import SessionContext
    from haywire.core.library.identity import LibraryIdentity
    from nicegui.element import Element


class BaseEditor(ABC):
    """
    Abstract base class for all editor types.

    An editor is a self-contained UI module that renders into a slot of the
    workspace layout, one instance per session.

    Methods decorated with ``@redraw_on(...)`` / ``@react_on(...)`` from
    :mod:`haywire.core.session.handlers` are auto-subscribed to the signal bus at
    instantiation; the editor is also subscribed to ``redraw_on=`` signals declared
    by panels whose action contract it satisfies.
    """

    class_identity: ClassVar[EditorIdentity]
    # Set by the @editor decorator at registration time.
    class_library: ClassVar["LibraryIdentity"]

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
        Called when this wrapper transitions from not-active to active in its slot
        (not when re-selecting the already-active wrapper).

        Runs before draw() on the newly-activated wrapper, so context mutations here
        are visible to that draw() and to signals this hook emits. Default is a no-op;
        override to update owned SessionState and emit the corresponding signal.

        Args:
            context: The current session context.
        """
        pass

    @abstractmethod
    def draw(self, context: "SessionContext", container: "Element") -> None:
        """
        Build the editor UI into the given NiceGUI container element.

        The orchestrator clears the container before calling this method.

        Multi-instance editors (e.g. GraphEditor) read their own identity
        from :attr:`wrapper` (set by the slot at instance-creation time);
        the ``wrapper`` carries the ``editor_key`` and ``binding_id`` that
        disambiguate this instance from other tabs of the same class.

        Args:
            context: The current session context.
            container: NiceGUI parent element (cleared by orchestrator).
        """
        ...

    def draw_tab(
        self,
        context: "SessionContext",
        *,
        orientation: Literal["horizontal", "vertical"],
    ) -> None:
        """Render the inner content of this editor's bar representation.

        Called by the owning slot while building the bar

        Override to customise the tab's appearance — a badge, a colored
        icon, a thumbnail, a two-line label.

        The framework draws the dirty marker and close button around this
        content, so an override never needs to reproduce them.

        Args:
            context: The current session context.
            orientation: ``"horizontal"`` for tab slots, ``"vertical"`` for
                icon slots.
        """
        label = self.wrapper.label or self.class_identity.label
        if orientation == "vertical":
            ui.icon(self.class_identity.icon).tooltip(self.class_identity.label)
        else:
            ui.label(label)

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
