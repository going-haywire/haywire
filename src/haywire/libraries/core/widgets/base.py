"""
Base widget classes for the Haywire widget system
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from nicegui import ui

import sys
import os
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..'))
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

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


class ErrorWidget(BaseWidget):
    """Widget displayed when no appropriate widget is found"""
    
    def __init__(self, element_id: str, data_field: DataField, ui_props: Dict[str, Any], 
                 requested_widget: Optional[str] = None):
        super().__init__(element_id, data_field, ui_props)
        self.requested_widget = requested_widget
    
    def create_element(self) -> Any:
        """Create an error display widget"""
        error_msg = f"Widget not found: '{self.requested_widget}'" if self.requested_widget else "No widget available"
        
        with ui.column().classes('w-full p-2 border border-red-500 bg-red-50'):
            ui.icon('error', color='red').classes('text-lg')
            ui.label(error_msg).classes('text-red-700 text-sm font-bold')
            ui.label(f"Data type: {self.data_field.type.value}").classes('text-red-600 text-xs')
            ui.label(f"Element ID: {self.element_id}").classes('text-red-600 text-xs')
            
            # Show current value as read-only
            current_value = self.get_value()
            ui.label(f"Value: {current_value}").classes('text-red-600 text-xs')
        
        return ui.column().classes('w-full')
