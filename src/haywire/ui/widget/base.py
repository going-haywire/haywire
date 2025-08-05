"""
Base widget classes for the Haywire widget system
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from nicegui import ui

from haywire.core.data.fields import DataField

class BaseWidget(ABC):
    """Abstract base class for all widgets"""
    
    def __init__(self, element_id: str, data_field: DataField, ui_props: Dict[str, Any]):
        self.element_id = element_id
        self.data_field = data_field
        self.ui_props = ui_props
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

