import logging
from typing import Dict, Optional

from haywire.ui.widget.base import BaseWidget

class UINodeCard():
    """
    Container for a rendered node's UI elements and widget instances.

    Holds the NiceGUI card element and mappings to all widget instances
    for easy access and management.
    """

    def __init__(self, ui_card, widget_instances: Dict[str, BaseWidget]):
        """
        Initialize UINodeCard with UI elements and widget instances.

        Args:
            ui_card: The main NiceGUI card element
            ui_elements: Mapping of element IDs to UI elements
            widget_instances: Mapping of element IDs to widget instances
        """
        self.ui_card = ui_card
        self.widget_instances = widget_instances

    def get_widget_instance(self, element_id: str) -> Optional['BaseWidget']:
        """Get a widget instance by element ID."""
        return self.widget_instances.get(element_id)

    def cleanup(self):
        """Clean up all widget instances by calling their cleanup methods."""
        for element_id, widget in self.widget_instances.items():
            if widget and hasattr(widget, 'cleanup'):
                try:
                    widget.cleanup()
                except Exception as e:
                    logging.error(f"Error cleaning up widget {element_id}: {e}")