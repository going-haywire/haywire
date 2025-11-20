"""
Base widget classes for the Haywire widget system
"""

from typing import Any, Dict, Optional

class UINodeCard:
    """
    Container for a rendered node's UI elements and widget instances.

    Holds the NiceGUI card element and mappings to all widget instances
    for easy access and management.
    """

    def __init__(self, ui_card, ui_elements: Dict[str, Any]):
        """
        Initialize UINodeCard with UI elements.

        Args:
            ui_card: The main NiceGUI card element
            ui_elements: Mapping of element IDs to UI elements
            widget_instances: Mapping of element IDs to widget instances
        """
        self.ui_card = ui_card
        self.ui_elements = ui_elements

    def get_ui_element(self, element_id: str) -> Optional[Any]:
        """Get a UI element by element ID."""
        return self.ui_elements.get(element_id)





