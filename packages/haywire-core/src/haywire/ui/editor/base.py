# packages/haywire-core/src/haywire/ui/editor_framework/base.py
"""
Abstract base class for all Haywire editor types.

Editors follow a poll/draw lifecycle managed by an orchestrator (AppShell):

    1. On first assignment to an area slot, the orchestrator calls draw()
       directly — no poll.
    2. On every ContextChangedEvent, the orchestrator calls poll(). If it
       returns True the orchestrator clears the container and calls draw().
    3. On hot-reload of the editor class, the orchestrator evicts the cached
       instance, calls cleanup(), and re-instantiates + draw() if visible.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

from .identity import EditorIdentity

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext
    from haywire.ui.context_events import ContextChangedEvent
    from nicegui.element import Element


class BaseEditor(ABC):
    """
    Abstract base class for all editor types.

    An editor is a self-contained UI module that renders into an Area
    of the workspace layout. Editor instances are lazily created and
    cached — when two browser windows are open, each session has its
    own editor instances.

    Subclasses must implement:
        - draw(context, container): Build the editor UI into the given container.

    Subclasses may override:
        - poll(context, event): Return True when a full redraw is needed.
        - cleanup(): Release resources when permanently removed.
        - get_tab_label(context): Dynamic tab label for tabbed areas.

    Class attributes (set by @editor decorator):
        - class_identity: EditorIdentity with registry_key, label, icon, canvas_area.
        - class_library: LibraryIdentity of the owning library (None for builtins).
    """

    class_identity: ClassVar[EditorIdentity]

    def poll(self, context: "SessionContext", event: "ContextChangedEvent") -> bool:
        """
        Determine whether this editor needs a full redraw.

        Called by the orchestrator on every ContextChangedEvent. If this
        returns True the orchestrator will clear the container and call
        draw(). The default implementation returns False (never redraw).

        Args:
            context: The current session context.
            event: Describes what changed.

        Returns:
            True if the editor needs a full redraw, False otherwise.
        """
        return False

    @abstractmethod
    def draw(self, context: "SessionContext", container: "Element") -> None:
        """
        Build the editor UI into the given NiceGUI container element.

        The orchestrator clears the container before calling this method.
        Called once on first assignment to an area, and again whenever
        poll() returns True.

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

    def get_tab_label(self, context: "SessionContext") -> str:
        """
        Return the label to show in a tab header (for tabbed areas like Middle).
        Defaults to class_identity.label. Override for dynamic labels (e.g., graph name).
        """
        return self.class_identity.label
