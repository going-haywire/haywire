# packages/haywire-core/src/haywire/ui/panel/base.py
"""
Abstract base class and layout helper for Haywire panels.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar, Any

from .identity import PanelIdentity

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext


class PanelLayout:
    """
    Layout helper passed to panel draw() methods.

    Wraps NiceGUI layout primitives and provides convenience methods
    for adding widgets, rows, columns, labels, separators, etc.

    This abstraction isolates panel authors from direct NiceGUI API
    calls, enabling potential backend swaps and consistent styling.
    """

    def __init__(self, container: Any):
        """
        Args:
            container: NiceGUI parent element to render into.
        """
        self._container = container

    def label(self, text: str, **kwargs) -> Any:
        """Add a text label."""
        from nicegui import ui

        with self._container:
            return ui.label(text)

    def row(self) -> Any:
        """Return a NiceGUI row context manager."""
        from nicegui import ui

        return ui.row()

    def column(self) -> Any:
        """Return a NiceGUI column context manager."""
        from nicegui import ui

        return ui.column().classes("w-full gap-0")

    def separator(self) -> None:
        """Add a visual divider."""
        from nicegui import ui

        with self._container:
            ui.separator()

    def button(self, text: str, on_click=None, **kwargs) -> Any:
        """Add a button."""
        from nicegui import ui

        with self._container:
            return ui.button(text, on_click=on_click)

    def expansion(self, title: str, icon: str = None) -> Any:
        """Return a collapsible sub-section context manager."""
        from nicegui import ui

        with self._container:
            return ui.expansion(title, icon=icon)

    def widget(self, widget_key: str, port: Any, **config) -> Any:
        """Render a registered widget into the panel.

        Args:
            widget_key: Registry key of the widget type to render.
            port: The DataPort to bind the widget to.
            **config: Additional widget configuration.
        """
        from nicegui import ui

        with self._container:
            return ui.label(f"[widget: {widget_key}]")  # placeholder; wired in Phase 5


class BasePanel(ABC):
    """
    Abstract base class for all panels.

    A panel is a collapsible section that appears inside an editor,
    filtered by context. Panels are the primary extension point for
    library developers to add custom UI.

    Class attributes (set by @panel decorator via class_identity):
        - class_identity.registry_key: Unique registry key.
        - class_identity.editor_key: Which editor type this panel belongs to.
        - class_identity.context: Context filter string.
        - class_identity.label: Display label shown in the panel header.
        - class_identity.icon: Optional Material icon.
        - class_identity.order: Sort priority (lower = higher in the list).
        - class_identity.default_open: Whether the panel starts expanded.

    Lifecycle:
        1. Editor receives ContextChangedEvent.
        2. Editor queries PanelRegistry for panels matching its editor_key.
        3. For each panel, editor calls poll(context).
        4. If poll() returns True, editor calls draw(context, layout).
        5. If poll() returns False, panel is hidden.
    """

    class_identity: ClassVar[PanelIdentity]

    @classmethod
    def poll(cls, context: "SessionContext") -> bool:
        """
        Determine if this panel should be visible given the current context.

        Called every time the context changes. Should be fast — avoid
        expensive computation here.

        Args:
            context: Current session context.

        Returns:
            True if the panel should be shown, False to hide it.
        """
        return True

    @abstractmethod
    def draw(self, context: "SessionContext", layout: PanelLayout) -> None:
        """
        Render the panel contents.

        Called when poll() returns True and the panel needs to display.
        Use the layout helper to add widgets and UI elements.

        Args:
            context: Current session context.
            layout: PanelLayout helper for building the UI.
        """
        ...

    def on_context_changed(self, context: "SessionContext", layout: PanelLayout) -> None:
        """
        Optional incremental update when context changes without full redraw.

        Override for panels that can update in-place rather than fully
        re-rendering. If not overridden, the editor will clear and re-call draw().
        """
        pass
