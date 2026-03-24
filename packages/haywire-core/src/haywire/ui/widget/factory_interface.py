from abc import ABC, abstractmethod
import nicegui.ui as ui

from haywire.core.types import DataPort
from haywire.ui.widget.base import BaseWidget


class IWidgetFactory(ABC):
    """
    Interface for Widget Factory classes.
    """

    @abstractmethod
    def render_widget(
        self, registry_key: str, port: DataPort, node_id: str
    ) -> tuple[BaseWidget | None, ui.element]:
        """Render a widget for the given inlet and return the widget instance.

        Note: The UI element is automatically added to the current NiceGUI context.

        Args:
            registry_key: The registry key of the widget to render
            port: The data port to render a widget for
            node_id: ID of the node containing this inlet
        Returns:
            BaseWidget instance or None if widget creation failed
        """
        pass
