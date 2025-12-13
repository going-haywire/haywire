

from abc import ABC, abstractmethod
import nicegui.ui as ui

from haywire.core.types.ports import PortInlet
from haywire.ui.widget.base import BaseWidget


class IWidgetFactory(ABC):
    """
    Interface for Widget Factory classes.
    """
    
    @abstractmethod
    def render_widget(
        self,
        inlet: PortInlet,
        node_id: str
    ) -> tuple[BaseWidget | None, ui.element] :
        """Render a widget for the given inlet and return the widget instance.
        
        Note: The UI element is automatically added to the current NiceGUI context.
        
        Args:
            inlet: The inlet port to render a widget for
            node_id: ID of the node containing this inlet
        Returns:
            BaseWidget instance or None if widget creation failed
        """
        pass