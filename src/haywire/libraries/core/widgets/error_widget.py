"""
Base widget classes for the Haywire widget system
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from nicegui import ui

from haywire.core.data.fields import DataField
from haywire.core.ui.base import BaseWidget
from haywire.core.node.elements import ConfigurableElement
from haywire.core.inventory.registry.widget_reg import widget

@widget(
    is_error_widget=True, 
    description="Widget displayed when no appropriate widget is found")
class ErrorWidget(BaseWidget):
    """Widget displayed when no appropriate widget is found"""
    
    def __init__(self, element: ConfigurableElement):
        super().__init__(element)
        self.requested_widget = element.widget
    
    def create_element(self) -> Any:
        """Create an error display widget"""
        error_msg = f"Widget not found: '{self.requested_widget}'" if self.requested_widget else "No widget available"
        
        with ui.column().classes('w-full p-2 border border-red-500 bg-red-50'):
            ui.icon('error', color='red').classes('text-lg')
            ui.label(error_msg).classes('text-red-700 text-sm font-bold')
            ui.label(f"Data type: {self.data_field.type}").classes('text-red-600 text-xs')
            ui.label(f"Element ID: {self.element_id}").classes('text-red-600 text-xs')
            
            # Show current value as read-only
            current_value = self.get_value()
            ui.label(f"Value: {current_value}").classes('text-red-600 text-xs')
        
        return ui.column().classes('w-full')
