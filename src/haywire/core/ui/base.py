"""
Base widget classes for the Haywire widget system
"""

import logging
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from haywire.core.ui.base_widget import BaseWidget

class UINodeCard:
    """
    Container for a rendered node's UI elements and widget instances.

    Holds the NiceGUI card element and mappings to all widget instances
    for easy access and management.
    """

    def __init__(self, ui_card, ui_elements: Dict[str, Any], widget_instances: Dict[str, 'BaseWidget']):
        """
        Initialize UINodeCard with UI elements and widget instances.

        Args:
            ui_card: The main NiceGUI card element
            ui_elements: Mapping of element IDs to UI elements
            widget_instances: Mapping of element IDs to widget instances
        """
        self.ui_card = ui_card
        self.ui_elements = ui_elements
        self.widget_instances = widget_instances

    def get_ui_element(self, element_id: str) -> Optional[Any]:
        """Get a UI element by element ID."""
        return self.ui_elements.get(element_id)
    
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





