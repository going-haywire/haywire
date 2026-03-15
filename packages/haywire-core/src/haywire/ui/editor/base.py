# packages/haywire-core/src/haywire/ui/editor_framework/base.py
"""
Abstract base class for all Haywire editor types.
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
    of the workspace layout. Each editor instance is per-session — when
    two browser windows are open, each has its own editor instances.

    Subclasses must implement:
        - render(container, context): Build the editor UI into the given container.
        - on_context_changed(event, context): React to context changes.

    Class attributes (set by @editor decorator):
        - class_identity: EditorIdentity with registry_key, label, icon, default_area.
        - class_library: LibraryIdentity of the owning library (None for builtins).
    """

    class_identity: ClassVar[EditorIdentity]

    @abstractmethod
    def render(self, container: 'Element', context: 'SessionContext') -> None:
        """
        Build the editor UI into the given NiceGUI container element.

        This is called once when the editor is first placed into an area,
        and again if the editor is swapped out and back in.

        Args:
            container: NiceGUI parent element (typically a ui.column or ui.card).
            context: The current session context.
        """
        ...

    @abstractmethod
    def on_context_changed(
        self, event: 'ContextChangedEvent', context: 'SessionContext'
    ) -> None:
        """
        Called when the SessionContext changes.

        The editor should re-evaluate which panels to show, update
        displayed data, etc.

        Args:
            event: Describes what changed.
            context: The updated session context.
        """
        ...

    def cleanup(self) -> None:
        """
        Optional cleanup when the editor is removed from an area.
        Override to release resources, unsubscribe from events, etc.
        """
        pass

    def get_tab_label(self, context: 'SessionContext') -> str:
        """
        Return the label to show in a tab header (for tabbed areas like Middle).
        Defaults to class_identity.label. Override for dynamic labels (e.g., graph name).
        """
        return self.class_identity.label
