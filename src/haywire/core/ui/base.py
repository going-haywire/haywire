"""
Base widget classes for the Haywire widget system
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from haywire.core.node.node import NodeErrorInfo

from haywire.core.data.fields import DataField
from haywire.core.node.elements import ConfigurableElement

class UINodeCard:
    """
    Container for a rendered node's UI elements and widget instances.

    Holds the NiceGUI card element and mappings to all widget instances
    for easy access and management.
    """

    def __init__(self, ui_card, ui_elements: Dict[str, Any], widget_instances: Dict[str, Any]):
        """
        Initialize UINodeCard with UI elements.

        Args:
            ui_card: The main NiceGUI card element
            ui_elements: Mapping of element IDs to UI elements
            widget_instances: Mapping of element IDs to widget instances
        """
        self.ui_card = ui_card
        self.ui_elements = ui_elements
        self.widget_instances = widget_instances

    def get_widget_instance(self, element_id: str) -> Optional[Any]:
        """Get a widget instance by element ID."""
        return self.widget_instances.get(element_id)

    def get_ui_element(self, element_id: str) -> Optional[Any]:
        """Get a UI element by element ID."""
        return self.ui_elements.get(element_id)

    def update_element_value(self, element_id: str, new_value: Any) -> bool:
        """
        Update an element's value through its widget.

        Args:
            element_id: ID of the element to update
            new_value: New value to set

        Returns:
            True if update was successful, False otherwise
        """
        widget_instance = self.widget_instances.get(element_id)
        if widget_instance and hasattr(widget_instance, 'update_value'):
            try:
                widget_instance.update_value(new_value)
                return True
            except Exception as e:
                print(f"Failed to update element {element_id}: {e}")
                return False
        return False


class BaseWidget(ABC):
    """Abstract base class for all widgets"""
    
    def __init__(self, element: ConfigurableElement):
        self.element: ConfigurableElement = element 
        self.element_id: str = element.id
        self.data_field: DataField = element.data
        self.ui_properties: Dict[str, Any] = element.ui.get('properties', {}) if hasattr(element, 'ui') else {}
        self.ui_element = None
    
    @abstractmethod
    def create_element(self) -> Any:
        """Create and return the NiceGUI element"""
        pass
    
    def update_value(self, new_value: Any):
        """Update the data field value"""
        self.data_field.set_value(new_value)
    
    def get_value(self) -> Any:
        """Get the current data field value"""
        return self.data_field.get_value()
    
    def render(self) -> Any:
        """Render the widget and return the UI element"""
        if self.ui_element is None:
            self.ui_element = self.create_element()
        return self.ui_element

